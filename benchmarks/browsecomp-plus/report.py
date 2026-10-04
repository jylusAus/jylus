"""Generate the benchmark report and submission metrics from saved scoring."""
import argparse
import json
from pathlib import Path


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--summary',type=Path,required=True)
    p.add_argument('--manifest',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    score=json.loads(a.summary.read_text());run=json.loads(a.manifest.read_text())
    if score['questions']!=830 or run['questions']!=830 or run['failures']:
        raise ValueError('Only the complete successful 830 run may be published.')
    candidate={k:score['metrics'][k]['candidate']for k in ['evidence','gold']}
    table=['| Labels | nDCG@10 | Recall@5 | Recall@100 | Recall@1000 |',
           '| --- | ---: | ---: | ---: | ---: |']
    for label in ['evidence','gold']:
        row=candidate[label]
        table.append('| '+label.title()+' | '+' | '.join(f'{row[k]:.6f}%'for k in ['ndcg_cut_10_percent','recall_5_percent','recall_100_percent','recall_1000_percent'])+' |')
    rows=['| Labels / metric | Change vs historical v30 (points) | Paired 95% interval | Improved / worse / same queries |',
          '| --- | ---: | --- | --- |']
    for label in ['evidence','gold']:
        for metric,s in score['metrics'][label]['paired_statistics']['metrics'].items():
            ci=s['paired_bootstrap_95_percent_interval_points']
            rows.append(f"| {label} / {metric} | {s['delta_points']:+.6f} | [{ci[0]:+.6f}, {ci[1]:+.6f}] | {s['improved_queries']} / {s['regressed_queries']} / {s['unchanged_queries']} |")
    wall=run['latency_ms']
    latency='Unavailable: response timing coverage was incomplete.'
    if run['timing_coverage']['wall_ms']==830:
        latency=(f"On-host public HTTPS HTTP elapsed: median **{wall['wall_p50']/1000:.3f} s**, "
                 f"p95 **{wall['wall_p95']/1000:.3f} s**, maximum **{wall['wall_max']/1000:.3f} s**. "
                 f"Two-worker batch runtime: **{run['elapsed_seconds']:.3f} s**. "
                 "Percentiles use linear interpolation at (N−1)p. HTTP elapsed includes request transmission, "
                 "response download and JSON decoding at the host HTTP client. It excludes the SSH "
                 "bridge transfer to the controller. This is a warm mixed-cache production workload, "
                 "not a cold-start latency guarantee.")
    text='''# Jylus: BrowseComp-Plus native retrieval

Internal evaluation of the **Jylus stack**, using all 830 official questions and
100,195 corpus documents. These are **retrieval rankings**, not generated-answer
accuracy, agent performance or an official/independent benchmark endorsement.
One ordinary authenticated public API request per question; no LLM, embedding
model or learned reranker was used by the Jylus arm.

## Complete public API result — 2026-10-04

'''+'\n'.join(table)+f'''

All metrics are unweighted means over all **830 questions**. No question is
excluded. Failures: **{run['failures']}**. The full run occurred after production
was switched to build **0913e75e61cded6ec0f82e6f54ddf5ec7ac26dc1**.
API `complete: true` responses: **{run['complete_responses']}/830**. That flag
is retained for inspection and is not used as a relevance or answerability
label. No answerability or final-answer evaluation was performed.
Final ranked IDs, scores, HTTP status and timings for every question are in
[results/jylus-live.jsonl.gz](results/jylus-live.jsonl.gz).

## What ran

The native Jylus stack retrieves source-backed evidence from the ingested
collection and returns ordered records plus a Context Pack. Scoring uses its
returned `evidence_rank`, maps source chunks to official document IDs and keeps
the first occurrence of each document. Scores are preserved for inspection;
they do not replace the supplied final rank. Evidence qrels label documents
needed to answer; gold qrels also require the final answer to be present.

[Reproduction](REPRODUCTION.md), [frozen configuration](config.json) and
[audit/limitations](AUDIT.md) describe corpus ingestion, scope, request budgets,
software, resource differences and service access. Only benchmark client and
evaluation code are public; the proprietary service is not distributed.
The [leaderboard submission guide](SUBMISSION.md) links the official JSON,
standard TREC export and reviewer verification command.

## Historical internal reference — quality only

'''+'\n'.join(rows)+'''

Intervals use 10,000 paired query-bootstrap samples, seed 20261002. They are
descriptive and unadjusted for development/tuning. This is not blind validation.
The historical v30 run used an isolated instance and a different transport;
these paired quality comparisons do not establish a paired latency improvement.
Its complete rankings are in
[results/jylus-v30-reference.jsonl.gz](results/jylus-v30-reference.jsonl.gz).

## Time and cost definitions

'''+latency+'''

The service shared its host with production traffic. Ingestion/collection
preparation happened before this query run and is not included in query elapsed
or batch runtime. No complete ingestion-to-ready timing or per-query monetary
cost was established for this release; no cost or ingestion-speed comparison is
reported. There are no competitor latency measurements in this evaluation.

## Evaluation limits

The first 100 questions were selected by lowest SHA-256(query ID) and used for
development and candidate selection. The complete 830 includes those questions.
Qrels were not opened by the retrieval client, but were used in earlier offline
analysis. Query-only previews and rejected candidates are recorded in the audit.
This result does not prove universal superiority or better final answers.

The official data is downloaded separately; corpus text, decrypted questions,
answers and qrels are not redistributed here. See the upstream
[BrowseComp-Plus protocol](https://github.com/texttron/BrowseComp-Plus/tree/046949032b0328319cc9a02663a759ec601d9402)
and [corpus card](https://huggingface.co/datasets/Tevatron/browsecomp-plus-corpus).
'''
    a.out.write_text(text,encoding='utf-8',newline='\n')
    submission={'Retriever':'Jylus native stack (0913e75)',
        'Link':'https://github.com/jylusAus/jylus/tree/main/benchmarks/browsecomp-plus',
        'Evaluation Date':'2026-10-04'}
    for label in ['evidence','gold']:
        for display,key in [('nDCG@10','ndcg_cut_10_percent'),('Recall@5','recall_5_percent'),('Recall@100','recall_100_percent'),('Recall@1000','recall_1000_percent')]:
            submission[label.title()+' '+display]=candidate[label][key]/100
    (a.out.parent/'leaderboard-submission.json').write_text(json.dumps(submission,indent=2)+'\n')
    print(json.dumps({'questions':830,'report_generated':True,'submission_sent':False}))


if __name__=='__main__':main()
