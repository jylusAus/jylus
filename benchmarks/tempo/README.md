# Jylus: full TEMPO normal-query retrieval

Internal evaluation of the native Jylus stack on all **1,730 normal queries**
across **13 domains**, measured through the ordinary authenticated public API
on October 4, 2026. Corpus: **1,654,055 official documents** in independent
domain collections. No LLM agent, supplied embedding, reasoning-query dataset,
step plan or answer model was used.

| Averaging method | NDCG@10 (%) |
| --- | ---: |
| Unweighted question mean, all 1,730 queries | 41.900433465 |
| Unweighted mean of 13 domain means | 41.364618174 |
| Domain macro using upstream's per-domain and final rounding | 41.365000 |

Use the **domain macro** for comparison with the official domain-macro
leaderboard. The question mean weights domains by query count; these are
different metrics. TP@10 and TC@10 are **not measured**. NDCG is retrieval
ranking accuracy and does not establish temporal coverage or final answer
accuracy. This is a submission for maintainer review, not accepted independent
validation or a claim of universal superiority.

| Domain | Queries | NDCG@10 (%) |
| --- | ---: | ---: |
| bitcoin | 100 | 29.455991 |
| cardano | 51 | 46.938802 |
| economics | 83 | 44.089361 |
| genealogy | 115 | 43.916857 |
| history | 801 | 39.778590 |
| hsm | 150 | 57.858876 |
| iota | 10 | 53.935044 |
| law | 35 | 42.975922 |
| monero | 65 | 13.921310 |
| politics | 150 | 64.019287 |
| quant | 34 | 22.520583 |
| travel | 100 | 27.501401 |
| workplace | 36 | 50.828011 |

## Evidence and reproduction

- [Saved rankings](results/rankings.jsonl.gz): every official query and ranked
  document ID, source scores, HTTP status and timing.
- [TREC rankings](results/rank-order.trec.gz): final rank encoded as `11-rank`.
- [Summary](results/summary.json), [per-query metrics](results/per-question-metrics.jsonl)
  and [measurement manifest](results/run-manifest.json).
- [Frozen configuration](config.json), [scoring code](evaluate.py),
  [API client](retrieve.py), [download code](download_data.py),
  [reproduction instructions](REPRODUCTION.md), [audit](AUDIT.md)
  and [file checksums](SHA256SUMS).

The saved results were rescored in a clean environment using freshly downloaded
official labels, with independent NDCG verified against TREC. Fresh full-corpus
API re-ingest parity has **not been demonstrated**; a matching provider corpus
profile and proprietary service version are required for a fresh API run.
The runtime implementation, credentials, source text and customer data are not
published. All dataset files are obtained separately from upstream.

All 1,730 final HTTP requests returned 200 and retained their rankings. The new
full-run evaluator initially rejected 2 valid responses because it required
ten compiler proofs even when the Context Pack retained a shorter, correctly
ordered prefix. The existing API contract permits this bounded prefix.
Every saved receipt was revalidated consistently under that established rule;
original failed checks remain in the private audit. No service, request,
retrieved ranking or gold-dependent selection was changed, and no API requests
were repeated to replace those results.

## Query timings

On-host public HTTPS HTTP elapsed, including request transmission, response
download and JSON decoding: median **6.267 s**,
p95 **8.811 s**; two-worker query batch
**5541.143 s**. Timing excludes SSH result
transfer to the controller and ingestion. Percentiles use linear interpolation.
These are mixed warm-source-cache measurements with request-cache bypass, not
cold-start or uniform millisecond guarantees. No ingestion-speed or monetary
cost comparison is claimed.

## Official references

[TEMPO benchmark and submission route](https://tempo-bench.github.io/),
[pinned evaluation code](https://github.com/tempo-bench/Tempo/tree/8731487254e0988eaf2ca4ae3e93ff587fec64d0),
[dataset](https://huggingface.co/datasets/tempo26/Tempo),
[paper and author attribution](https://arxiv.org/abs/2601.09523).
The dataset card specifies CC BY 4.0. Development used this cohort previously;
this run is internal evaluation, not a blind held-out test.
