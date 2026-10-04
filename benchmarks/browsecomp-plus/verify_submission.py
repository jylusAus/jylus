"""Check the submission schema and rescore the public TREC export locally."""
import argparse
import datetime
import gzip
import hashlib
import json
import math
import statistics
from pathlib import Path

import pytrec_eval

METRICS={'nDCG@10':'ndcg_cut_10','Recall@5':'recall_5',
         'Recall@100':'recall_100','Recall@1000':'recall_1000'}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--directory',type=Path,default=Path(__file__).resolve().parent)
    parser.add_argument('--evidence-qrels',type=Path,required=True)
    parser.add_argument('--gold-qrels',type=Path,required=True)
    args=parser.parse_args();base=args.directory
    submission=json.loads((base/'leaderboard-submission.json').read_text())
    required={'Retriever','Link','Evaluation Date'}|{
        label+' '+metric for label in ['Evidence','Gold']for metric in METRICS}
    if set(submission)!=required:
        raise ValueError('Submission must contain exactly the official retrieval-only fields.')
    datetime.date.fromisoformat(submission['Evaluation Date'])
    if not submission['Retriever'] or not submission['Link'].startswith('https://'):
        raise ValueError('Retriever name and public model-card link are required.')
    config=json.loads((base/'config.json').read_text())
    qids=(base/'query-ids.tsv').read_text().splitlines()
    if len(qids)!=830 or len(set(qids))!=830:
        raise ValueError('Complete official 830-query inventory required.')
    with gzip.open(base/'results/jylus-live.jsonl.gz','rt',encoding='utf-8')as stream:
        rows=[json.loads(line)for line in stream]
    if len(rows)!=830 or {str(r['query_id'])for r in rows}!=set(qids):
        raise ValueError('Ranked results do not cover all 830 questions.')
    rankings={str(r['query_id']):[str(d['document_id'])for d in r['documents']]for r in rows}
    with gzip.open(base/'results/rank-order.trec.gz','rt',encoding='utf-8')as stream:
        run=pytrec_eval.parse_run(stream)
    if set(run)!=set(qids):
        raise ValueError('TREC export does not cover all 830 questions.')
    for qid in qids:
        ranked=sorted(run[qid],key=lambda doc:-run[qid][doc])
        if ranked!=rankings[qid][:1000]:
            raise ValueError('TREC export changed the public supplied ranking.')
        if any(run[qid][doc]!=1001-rank for rank,doc in enumerate(ranked,1)):
            raise ValueError('TREC score must encode final rank, not a different score order.')
    summary=json.loads((base/'results/summary.json').read_text())
    measured={}
    for label,path in [('Evidence',args.evidence_qrels),('Gold',args.gold_qrels)]:
        expected=config['dataset']['qrels_sha256'][label.lower()+'_qrels']
        if hashlib.sha256(path.read_bytes()).hexdigest()!=expected:
            raise ValueError('Obtain the exact frozen official relevance labels.')
        with path.open(encoding='utf-8')as stream:
            qrels=pytrec_eval.parse_qrel(stream)
        if not set(qids)<=set(qrels):
            raise ValueError('Official relevance labels do not cover all queries.')
        scores=pytrec_eval.RelevanceEvaluator({q:qrels[q]for q in qids},set(METRICS.values())).evaluate(run)
        if set(scores)!=set(qids):
            raise ValueError('Evaluator excluded a question.')
        for display,metric in METRICS.items():
            name=label+' '+display
            value=statistics.mean(scores[q][metric]for q in qids)
            published=summary['metrics'][label.lower()]['candidate'][metric+'_percent']/100
            entered=submission[name]
            if isinstance(entered,bool)or not isinstance(entered,(int,float))or not math.isfinite(entered)or not 0<=entered<=1:
                raise ValueError('Submission metrics must be finite TREC values between zero and one.')
            if abs(value-published)>1e-12 or abs(value-entered)>1e-12:
                raise ValueError('TREC score, saved summary and submission JSON disagree.')
            measured[name]=value
    print(json.dumps({'passed':True,'questions':830,'metric_units':'0-1 TREC values',
                      'trec_rank_order_preserved':True,'eight_metrics_match':measured,
                      'live_api_calls':0,'leaderboard_submission_sent':False},indent=2))


if __name__=='__main__':main()
