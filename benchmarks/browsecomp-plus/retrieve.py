"""Portable API client for the measured request/scoring contract.

This client has no qrel input. The original measured transport executed HTTP
from the deployment host; this client's elapsed time is from wherever it runs.
"""
import argparse, concurrent.futures, csv, datetime, hashlib, json, os, re, time
from pathlib import Path
from typing import Any
import requests
NAMESPACE = None
CONTAINER = 'api_public.browsecomp-plus'
TIMESTAMP_GTE = '2026-09-28T04:14:00Z'
def truncate_utf16(value: str, maximum_units: int = 500) -> str:
    output: list[str] = []
    units = 0
    for character in value:
        width = 2 if ord(character) > 0xFFFF else 1
        if units + width > maximum_units:
            break
        output.append(character)
        units += width
    return "".join(output)

def request_payload(query: str) -> dict[str, Any]:
    return {
        "source": "history",
        "where": {
            "namespace": {"eq": NAMESPACE},
            "container": {"eq": CONTAINER},
            "timestamp": {"gte": TIMESTAMP_GTE},
        },
        "deep_scan": True,
        # The public lexical contract is 500 UTF-16 units.  The complete long
        # query remains in the vector field, matching Jylus's public contract.
        "text": truncate_utf16(query),
        "vector": {"text": query},
        "context": {
            "mode": "decision",
            "token_budget": 8_000,
            "max_facts": 10,
            "max_timeline": 20,
            "max_contradictions": 12,
            "include_documents": False,
        },
        "scan_limit": 50_000,
        "limit": 1_536,
        "include_results": True,
    }

def official_document_id(result: dict[str, Any]) -> str | None:
    document = (result.get("payload") or {}).get("document") or {}
    for value in (document.get("id"), result.get("source_id"), result.get("id")):
        text = str(value or "")
        match = re.fullmatch(r"bcp-(.+)-chunk-\d{4}", text)
        if match:
            return match.group(1)
        if text and not text.startswith("bcp-"):
            return text
    return None

def compact_results(value: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    results = value.get("results") or []
    if not isinstance(results, list):
        raise TypeError("analyze results was not a list")
    chunk_rows: list[dict[str, Any]] = []
    missing_rank = 0
    missing_docid = 0
    outside_scope = 0
    for index, result in enumerate(results):
        if not isinstance(result, dict):
            continue
        if result.get("namespace") != NAMESPACE or result.get("container") != CONTAINER:
            outside_scope += 1
        document_id = official_document_id(result)
        if document_id is None:
            missing_docid += 1
            continue
        try:
            rank = int(result["evidence_rank"])
        except (KeyError, TypeError, ValueError):
            missing_rank += 1
            rank = 1_000_000 + index
        relevance = result.get("relevance") or {}
        chunk_rows.append({
            "rank": rank,
            "document_id": document_id,
            "event_id": str(result.get("id") or ""),
            "score": relevance.get("score"),
        })
    if outside_scope or missing_docid or missing_rank:
        raise RuntimeError({
            "outside_scope": outside_scope,
            "missing_document_id": missing_docid,
            "missing_evidence_rank": missing_rank,
        })
    chunk_rows.sort(key=lambda row: row["rank"])
    document_rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in chunk_rows:
        if row["document_id"] in seen:
            continue
        seen.add(row["document_id"])
        document_rows.append({
            "rank": len(document_rows) + 1,
            "document_id": row["document_id"],
            "score": row["score"],
        })
    probe = {
        "success": value.get("success"),
        "complete": value.get("complete"),
        "execution_mode": value.get("execution_mode"),
        "scanned": value.get("scanned"),
        "filtered": value.get("filtered"),
        "matched": value.get("matched"),
        "returned_chunks": len(chunk_rows),
        "returned_documents": len(document_rows),
    }
    return document_rows, probe

def main():
    global NAMESPACE
    p=argparse.ArgumentParser()
    p.add_argument('--queries',type=Path,required=True)
    p.add_argument('--query-ids',type=Path,default=Path('query-ids.tsv'))
    p.add_argument('--namespace',required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--api-root',default='https://api.jylus.ai')
    p.add_argument('--workers',type=int,choices=[1,2],default=2)
    p.add_argument('--limit',type=int,default=830)
    a=p.parse_args();NAMESPACE=a.namespace
    key=os.environ.get('JYLUS_API_KEY','').strip()
    if not key: raise ValueError('Set JYLUS_API_KEY; never commit it.')
    if a.out.exists(): raise ValueError('Use a new output directory for every run.')
    raw=dict(csv.reader(a.queries.open(encoding='utf-8'),delimiter='\t'))
    ids=a.query_ids.read_text().splitlines()
    if len(ids)!=830 or len(set(ids))!=830 or set(ids)!=set(raw):
        raise ValueError('Complete official 830-query inventory required.')
    if not 1<=a.limit<=830: raise ValueError('Invalid cohort limit.')
    ids=ids[:a.limit];a.out.mkdir(parents=True)
    headers={'authorization':'Bearer '+key,'content-type':'application/json',
        'accept':'application/json','x-jylus-cache-bypass':'receipt-verification'}
    started_at=datetime.datetime.now(datetime.timezone.utc).isoformat()
    started=time.perf_counter()
    def one(qid):
        begin=time.perf_counter(); statuses=[]
        try:
            r=requests.post(a.api_root.rstrip('/')+'/api/v1/analyze',
                headers=headers,json=request_payload(raw[qid]),timeout=180)
            statuses.append(r.status_code)
            r.raise_for_status();documents,probe=compact_results(r.json())
            if not documents: raise ValueError('No ranked documents returned.')
            return {'query_id':qid,'documents':documents,'status':'completed',
                'complete':probe.get('complete'),'http_statuses':statuses,
                'timings':{'wall_ms':1000*(time.perf_counter()-begin),
                    'server_ms':float(r.headers['X-Jylus-Server-Ms']) if r.headers.get('X-Jylus-Server-Ms') else None}}
        except Exception as e:
            # Do not persist response text, credentials or customer records.
            return {'query_id':qid,'documents':[],'status':'failed',
                'failure_type':type(e).__name__,'http_statuses':statuses,
                'timings':{'wall_ms':1000*(time.perf_counter()-begin)}}
    rows={}
    with concurrent.futures.ThreadPoolExecutor(max_workers=a.workers) as pool:
        for row in pool.map(one,ids):
            rows[row['query_id']]=row
            (a.out/(row['query_id']+'.json')).write_text(json.dumps(row)+'\n')
    result=a.out/'results.jsonl'
    result.write_text(''.join(json.dumps(rows[q],separators=(',',':'))+'\n' for q in ids))
    failures=sum(rows[q]['status']=='failed' for q in ids)
    manifest={'started_at':started_at,'finished_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'elapsed_seconds':time.perf_counter()-started,'questions':len(ids),'failures':failures,
        'workers':a.workers,'qrels_opened':False,'model_calls':0,
        'results_sha256':hashlib.sha256(result.read_bytes()).hexdigest(),
        'timing_definition':'HTTP plus response download/JSON parse at this client; not the original on-host timing',
        'retries':0}
    (a.out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps(manifest,indent=2))
    raise SystemExit(2 if failures else 0)

if __name__=='__main__':main()
