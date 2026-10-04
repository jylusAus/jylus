"""Score all 1,730 saved normal-query rankings against pinned official labels."""
import argparse
import gzip
import hashlib
import json
import math
from pathlib import Path

import pyarrow.parquet as pq
import pytrec_eval


def normalized(source):return 'tempo-doc-'+hashlib.sha256(source.encode('utf-8')).hexdigest()[:24]


def evaluate(result_file,data_dir,config):
    opener=gzip.open if result_file.suffix=='.gz' else open
    with opener(result_file,'rt',encoding='utf-8')as stream:rows=[json.loads(line)for line in stream if line.strip()]
    rankings={};examples={};per_domain={};per_question=[]
    for row in rows:
        key=(row['domain'],row['query_id'])
        if key in rankings:raise ValueError('Duplicate query result')
        ids=row['document_ids']
        if len(ids)>10 or len(set(ids))!=len(ids):raise ValueError('Duplicate or excess ranked document IDs')
        rankings[key]=row
    for info in config['dataset_files']:
        if info['kind']!='examples':continue
        path=data_dir/info['relative_path']
        if hashlib.sha256(path.read_bytes()).hexdigest()!=info['sha256']:raise ValueError('Official input hash mismatch')
        for row in pq.read_table(path,columns=['id','gold_ids','negative_ids']).to_pylist():examples[info['domain'],row['id']]=row
    if len(examples)!=1730 or set(rankings)!=set(examples):raise ValueError('Must retain every official query exactly once')
    for domain in config['domains']:
        qrels={};scored={};keys=sorted(k for k in examples if k[0]==domain)
        for key in keys:
            row=rankings[key];example=examples[key];ids=row['document_ids']
            native=row.get('id_format')=='sha256-normalized'
            convert=normalized if native else str
            relevant={convert(i):1 for i in example['gold_ids']}
            negatives={convert(i)for i in example['negative_ids']if i!='NA'}
            if set(ids)&negatives:raise ValueError('Protocol-excluded document in rankings')
            qrels[key[1]]=relevant
            scored[key[1]]={doc:float(11-rank)for rank,doc in enumerate(ids,1)}
        official=pytrec_eval.RelevanceEvaluator(qrels,{'ndcg_cut.10'}).evaluate(scored)
        domain_values=[]
        for key in keys:
            row=rankings[key];example=examples[key];ids=row['document_ids']
            relevant={normalized(i)if row.get('id_format')=='sha256-normalized' else i for i in example['gold_ids']}
            ideal=sum(1/math.log2(r+2)for r in range(min(10,len(relevant))))
            value=sum(1/math.log2(r+2)for r,doc in enumerate(ids)if doc in relevant)/ideal if ideal else 0.0
            trec=official.get(key[1],{}).get('ndcg_cut_10',0.0)
            if abs(value-trec)>1e-12:raise ValueError('Independent NDCG disagrees with TREC')
            failed=bool(row.get('failure')) or not ids
            per_question.append({'domain':domain,'query_id':key[1],'ndcg_at_10':value,'failed':failed})
            domain_values.append(value)
        per_domain[domain]={'queries':len(keys),'ndcg_at_10_percent':100*sum(domain_values)/len(keys),
            'upstream_rounded_ndcg_at_10':round(sum(domain_values)/len(keys),5)}
    mean=100*sum(row['ndcg_at_10']for row in per_question)/1730
    macro=sum(d['ndcg_at_10_percent']for d in per_domain.values())/13
    upstream=100*round(sum(d['upstream_rounded_ndcg_at_10']for d in per_domain.values())/13,5)
    return {'questions':1730,'domains':13,'track':'normal query','question_mean_ndcg_at_10_percent':mean,
        'domain_macro_ndcg_at_10_percent':macro,'upstream_rounded_domain_macro_ndcg_at_10_percent':upstream,
        'per_domain':per_domain,'failed_questions':sum(r['failed']for r in per_question),
        'averaging':'question mean: all 1730 queries; domain macro: unweighted mean of 13 domain means',
        'label_source':'official pinned binary gold_ids; no answer/temporal judgment',
        'tp_at_10':None,'tc_at_10':None},per_question


def main():
    p=argparse.ArgumentParser();p.add_argument('--results',type=Path,default=Path('results/rankings.jsonl.gz'))
    p.add_argument('--data',type=Path,default=Path('data'));p.add_argument('--out',type=Path,default=Path('rescored'))
    a=p.parse_args();config=json.loads(Path(__file__).with_name('config.json').read_text())
    report,rows=evaluate(a.results,a.data,config);a.out.mkdir(parents=True,exist_ok=True)
    (a.out/'summary.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
    (a.out/'per-question-metrics.jsonl').write_text(''.join(json.dumps(row)+'\n'for row in rows),encoding='utf-8',newline='\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
