"""Explicit, NATS-backed ordinary tenant API ingestion; no runtime code."""
import argparse, concurrent.futures, datetime, gzip, hashlib, json, os, random, time
from pathlib import Path
import urllib.error, urllib.request
MAX_CHUNK_BYTES=32000
MAX_BATCH_EVENTS=100
MAX_BATCH_BYTES=900000
API_URL='https://api.jylus.ai/api/v1/events'
CORPUS=None
NAMESPACE=None
STREAM='browsecomp-plus'
SITE='browsecomp-plus-official'
SOURCE='api_public.browsecomp-plus'
OCCURRED_AT='2026-09-28T04:15:00Z'
def split_utf8(text: str) -> list[str]:
    encoded = text.encode("utf-8")
    if len(encoded) <= MAX_CHUNK_BYTES:
        return [text]
    chunks: list[str] = []
    start = 0
    while start < len(encoded):
        end = min(start + MAX_CHUNK_BYTES, len(encoded))
        while end < len(encoded) and end > start and encoded[end] & 0xC0 == 0x80:
            end -= 1
        if end < len(encoded):
            minimum = start + MAX_CHUNK_BYTES * 4 // 5
            for marker in (b"\n\n", b"\n", b" "):
                position = encoded.rfind(marker, minimum, end)
                if position >= minimum:
                    end = position + len(marker)
                    break
        if end <= start:
            raise RuntimeError("unable to split UTF-8 document")
        chunks.append(encoded[start:end].decode("utf-8"))
        start = end
    return chunks

def event_rows():
    with gzip.open(CORPUS, "rt", encoding="utf-8") as source:
        for line in source:
            row = json.loads(line)
            docid = str(row["docid"])
            parts = split_utf8(str(row["text"]))
            for index, content in enumerate(parts):
                yield {
                    "id": f"bcp-{docid}-chunk-{index:04d}",
                    "type": "public.document",
                    "occurred_at": OCCURRED_AT,
                    "data": {
                        "document": {
                            "id": docid,
                            "benchmark": "browsecomp-plus",
                            "url": str(row.get("url") or ""),
                            "content": content,
                            "chunk_index": index,
                            "chunk_count": len(parts),
                        }
                    },
                }

def batches():
    base = {
        "stream": STREAM,
        "namespace": NAMESPACE,
        "site_id": SITE,
        "source_id": SOURCE,
    }
    prefix_bytes = len(json.dumps({**base, "events": []}, ensure_ascii=False, separators=(",", ":")).encode("utf-8")) - 2
    current: list[dict] = []
    current_bytes = prefix_bytes + 2
    for event in event_rows():
        event_bytes = len(json.dumps(event, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
        separator_bytes = 1 if current else 0
        if current and (len(current) >= MAX_BATCH_EVENTS
                        or current_bytes + separator_bytes + event_bytes > MAX_BATCH_BYTES):
            yield {**base, "events": current}
            current = [event]
            current_bytes = prefix_bytes + 2 + event_bytes
        else:
            current.append(event)
            current_bytes += separator_bytes + event_bytes
    if current:
        yield {**base, "events": current}

def send(batch_index: int, payload: dict, api_key: str) -> dict:
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    started = time.perf_counter()
    last_error: Exception | None = None
    for attempt in range(1, 9):
        request = urllib.request.Request(
            API_URL,
            data=body,
            method="POST",
            headers={
                "Authorization": "Bearer " + api_key,
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Idempotency-Key": f"bcp-b27b02bc-{batch_index}",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                value = json.loads(response.read().decode("utf-8"))
                accepted = int(value.get("accepted") or 0)
                duplicates = int(value.get("duplicates") or 0)
                if accepted + duplicates != len(payload["events"]):
                    raise RuntimeError("incomplete durable API acknowledgement")
                return {
                    "events": len(payload["events"]),
                    "accepted": accepted,
                    "duplicates": duplicates,
                    "wall_ms": round((time.perf_counter() - started) * 1000, 3),
                    "receipt_state": (value.get("receipt") or {}).get("state"),
                }
        except urllib.error.HTTPError as error:
            last_error = RuntimeError(f"HTTP {error.code}")
            if error.code not in (429, 500, 502, 503, 504):
                raise last_error
        except Exception as error:
            last_error = error
        time.sleep(min(10.0, 0.25 * (2 ** (attempt - 1))) * (0.9 + random.random() * 0.2))
    raise last_error or RuntimeError("ingest request failed")

def main():
    global CORPUS,NAMESPACE,API_URL
    p=argparse.ArgumentParser()
    p.add_argument('--corpus',type=Path,required=True)
    p.add_argument('--namespace',required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--api-root',default='https://api.jylus.ai')
    p.add_argument('--max-batches',type=int)
    p.add_argument('--execute',action='store_true',help='Submit real tenant events; without this only validate batches.')
    a=p.parse_args();CORPUS=a.corpus;NAMESPACE=a.namespace;API_URL=a.api_root.rstrip('/')+'/api/v1/events'
    if a.out.exists():raise ValueError('Use a new report path; do not replay blindly.')
    key=os.environ.get('JYLUS_API_KEY','').strip()
    if a.execute and not key:raise ValueError('Set JYLUS_API_KEY.')
    started=time.perf_counter(); count=0; events=0; accepted=0; duplicates=0
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        iterator=iter(batches())
        while True:
            window=[]
            for offset in range(2):
                if a.max_batches is not None and count+len(window)>=a.max_batches:break
                try:window.append(next(iterator))
                except StopIteration:break
            if not window:break
            if a.execute:
                # Bind idempotency to this requested collection, not another ingestion.
                base=int(hashlib.sha256(NAMESPACE.encode()).hexdigest()[:12],16)
                results=[f.result() for f in [pool.submit(send,base+count+i,b,key) for i,b in enumerate(window)]]
                accepted+=sum(r['accepted'] for r in results);duplicates+=sum(r['duplicates'] for r in results)
            count+=len(window);events+=sum(len(b['events']) for b in window)
            if count%100==0:print(json.dumps({'batches':count,'events':events}),flush=True)
    report={'batches':count,'events':events,'accepted':accepted,'duplicates':duplicates,
        'submitted':a.execute,'elapsed_seconds':time.perf_counter()-started,
        'acknowledgment_is_query_readiness':False,'concurrency':2}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
