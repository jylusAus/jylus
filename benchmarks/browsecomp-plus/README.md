# Jylus: BrowseComp-Plus native retrieval

Internal evaluation of the **Jylus stack**, using all 830 official questions and
100,195 corpus documents. These are **retrieval rankings**, not generated-answer
accuracy, agent performance or an official/independent benchmark endorsement.
One ordinary authenticated public API request per question; no LLM, embedding
model or learned reranker was used by the Jylus arm.

## Complete public API result — 2026-10-04

| Labels | nDCG@10 | Recall@5 | Recall@100 | Recall@1000 |
| --- | ---: | ---: | ---: | ---: |
| Evidence | 16.178227% | 11.648577% | 23.990705% | 64.178741% |
| Gold | 13.464559% | 12.932922% | 24.902897% | 65.824154% |

All metrics are unweighted means over all **830 questions**. No question is
excluded. Failures: **0**. The full run occurred after production
was switched to build **0913e75e61cded6ec0f82e6f54ddf5ec7ac26dc1**.
API `complete: true` responses: **0/830**. That flag
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

| Labels / metric | Change vs historical v30 (points) | Paired 95% interval | Improved / worse / same queries |
| --- | ---: | --- | --- |
| evidence / ndcg_cut_10 | +0.611200 | [+0.068348, +1.131387] | 179 / 98 / 553 |
| evidence / recall_100 | +0.585530 | [+0.121485, +1.057950] | 71 / 42 / 717 |
| evidence / recall_1000 | +0.499722 | [+0.125843, +0.885010] | 55 / 29 / 746 |
| evidence / recall_5 | +0.048866 | [-0.516316, +0.583127] | 54 / 44 / 732 |
| gold / ndcg_cut_10 | -0.156614 | [-0.950481, +0.597026] | 103 / 65 / 662 |
| gold / recall_100 | -0.129853 | [-0.967062, +0.658458] | 25 / 22 / 783 |
| gold / recall_1000 | +0.576831 | [+0.021513, +1.165824] | 25 / 12 / 793 |
| gold / recall_5 | -0.836345 | [-1.847415, +0.145582] | 26 / 33 / 771 |

Intervals use 10,000 paired query-bootstrap samples, seed 20261002. They are
descriptive and unadjusted for development/tuning. This is not blind validation.
The historical v30 run used an isolated instance and a different transport;
these paired quality comparisons do not establish a paired latency improvement.
Its complete rankings are in
[results/jylus-v30-reference.jsonl.gz](results/jylus-v30-reference.jsonl.gz).

## Time and cost definitions

On-host public HTTPS HTTP elapsed: median **5.148 s**, p95 **8.463 s**, maximum **13.050 s**. Two-worker batch runtime: **4751.669 s**. Percentiles use linear interpolation at (N−1)p. HTTP elapsed includes request transmission, response download and JSON decoding at the host HTTP client. It excludes the SSH bridge transfer to the controller. This is a warm mixed-cache production workload, not a cold-start latency guarantee.

The service shared its host with production traffic. Ingestion/collection
preparation happened before this query run and is not included in query elapsed
or batch runtime. No complete ingestion-to-ready timing or per-query monetary
cost was established for this release; no cost or ingestion-speed comparison is
reported. There are no competitor latency measurements in this evaluation.

## Limits and release guards

The first 100 questions were selected by lowest SHA-256(query ID) and used for
development and candidate selection. The complete 830 includes those questions.
Qrels were not opened by the retrieval client, but were used in earlier offline
analysis. Query-only previews and rejected candidates are recorded in the audit.
This result does not prove universal superiority or better final answers.

Separately, this live release retained QASPER test retrieval at **51.162602%
nDCG@10 / 75.881019% Recall@10** (1,335 queries), native FinQA official execution
at **39.843069%** / program **34.612031%** (1,147 cases), and a **251-question**
TEMPO NDCG guard at **40.670800%**. The TEMPO result is a lightweight regression
check, not the full benchmark or a temporal-consistency judgment.

The official data is downloaded separately; corpus text, decrypted questions,
answers and qrels are not redistributed here. See the upstream
[BrowseComp-Plus protocol](https://github.com/texttron/BrowseComp-Plus/tree/046949032b0328319cc9a02663a759ec601d9402)
and [corpus card](https://huggingface.co/datasets/Tevatron/browsecomp-plus-corpus).
