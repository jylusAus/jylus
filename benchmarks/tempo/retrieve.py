"""Fresh API retrieval only; query loader never opens gold or answer columns."""
import argparse
import concurrent.futures
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import threading
import time

import pyarrow.parquet as pq
import requests

LOCAL=threading.local()


def normalized(source):return 'tempo-doc-'+hashlib.sha256(source.encode('utf-8')).hexdigest()[:24]


def doc_id(row):
    document=(row.get('payload')or{}).get('document')or{}
    for source in (document.get('id'),row.get('source_id'),row.get('container'),row.get('id')):
        text=re.sub(r'^evt(?:-v3)?-','',str(source or''))
        text=re.sub(r'-chunk-\d{4}$','',text)
        if text.startswith('tempo-doc-'):return text
    return ''


def session():
    if not getattr(LOCAL,'session',None):
        key=os.environ['JYLUS_API_KEY'].strip()
        if len(key)<24 or any(c.isspace()for c in key):raise ValueError('Invalid API key')
        LOCAL.session=requests.Session();LOCAL.session.headers.update({'Authorization':'Bearer '+key,
            'Content-Type':'application/json','Accept':'application/json','X-Jylus-Cache-Bypass':'receipt-verification'})
    return LOCAL.session


def one(item,config):
    domain,query=item;scope=config['collection_prefix']+domain;attempts=[]
    prefix=query['query'].encode('utf-16-le')[:1000].decode('utf-16-le',errors='ignore')
    excluded=[normalized(s)for s in query['negative_ids']if s!='NA']
    payload={'source':'history','where':{'namespace':{'eq':config['namespace']},'container':{'eq':scope},
        'timestamp':{'gte':config['timestamp_lower_bound']}},'text':prefix,'vector':{'text':query['query']},
        'context':config['request']['context'],'limit':10,'scan_limit':20000,'excluded_document_ids':excluded}
    out={'domain':domain,'query_id':query['id'],'id_format':'sha256-normalized','document_ids':[],
        'attempts':attempts,'request_sha256':hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':')).encode()).hexdigest()}
    try:
        for attempt in range(4):
            started=time.perf_counter();response=session().post(config['api_url'],json=payload,timeout=180)
            value=response.json();elapsed=(time.perf_counter()-started)*1000
            attempts.append({'http_status':response.status_code,'http_elapsed_ms':elapsed,
                'server_ms':response.headers.get('X-Jylus-Server-Ms')})
            if response.status_code!=200:raise ValueError('HTTP '+str(response.status_code))
            rows=sorted(value.get('results')or[],key=lambda r:int(r.get('evidence_rank',-1)))
            if any(r.get('namespace')!=config['namespace']or r.get('container')!=scope for r in rows):raise ValueError('Scope mismatch')
            if [r.get('evidence_rank')for r in rows]!=list(range(1,len(rows)+1)):raise ValueError('Invalid evidence ranks')
            ids=[doc_id(r)for r in rows]
            if any(not r.startswith('tempo-doc-')for r in ids)or len(set(ids))!=len(ids):raise ValueError('Invalid source identities')
            if set(ids)&set(excluded):raise ValueError('Protocol exclusion failure')
            proofs=(value.get('context')or{}).get('proof',{}).get('event_ids',[])
            proof_ids=[doc_id({'id':p})for p in proofs[:10]]
            if ids[:len(proof_ids)]!=proof_ids:raise ValueError('Compiler proof order mismatch')
            if len(ids)>=10:
                out['document_ids']=ids[:10];out['evidence_scores']=[r.get('relevance')for r in rows[:10]];break
            time.sleep(0.5*(attempt+1))
        if len(out['document_ids'])!=10:raise ValueError('Incomplete ranked top ten')
    except Exception as error:out['failure']=str(error)if isinstance(error,ValueError)else type(error).__name__
    return out


def main():
    p=argparse.ArgumentParser();p.add_argument('--data',type=Path,default=Path('data'))
    p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    config=json.loads(Path(__file__).with_name('config.json').read_text());items=[]
    for info in config['dataset_files']:
        if info['kind']!='examples':continue
        path=a.data/info['relative_path']
        if hashlib.sha256(path.read_bytes()).hexdigest()!=info['sha256']:raise ValueError('Input checksum mismatch')
        for query in pq.read_table(path,columns=['id','query','negative_ids']).to_pylist():items.append((info['domain'],query))
    if len(items)!=1730:raise ValueError('All 1730 normal queries are required')
    if a.out.exists():raise ValueError('Fresh output required; do not overwrite prior results')
    a.out.parent.mkdir(parents=True,exist_ok=True);opener=gzip.open if a.out.suffix=='.gz' else open
    with opener(a.out,'wt',encoding='utf-8')as out,concurrent.futures.ThreadPoolExecutor(max_workers=2)as pool:
        jobs=[pool.submit(one,item,config)for item in items]
        for f in concurrent.futures.as_completed(jobs):out.write(json.dumps(f.result())+'\n');out.flush()
    print(json.dumps({'queries':1730,'output':str(a.out),'workers':2,'model_calls':0}))


if __name__=='__main__':main()
