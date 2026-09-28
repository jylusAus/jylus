# Frozen 256-question results

> Internal evaluation. These are retrieval-ranking results, not answer accuracy.

The unchanged upstream MultiHop-RAG retrieval protocol scored 236 answerable questions and excluded 20 `null_query` questions.

| System | MAP@10 | Hits@10 | Hits@4 | MRR@10 |
| --- | ---: | ---: | ---: | ---: |
| Jylus | **45.831414%** | **100.000000%** | **88.983051%** | **78.078760%** |
| NVIDIA-style agentic RAG | 39.299937% | 98.728814% | 86.016949% | 70.661320% |

Jylus MAP@10 lead: **+6.531477 points**. Paired 100,000-resample bootstrap 95% interval: **+3.749106 to +9.320886 points**. One-sided paired sign-test: **p = 1.6082831e-05** (140 Jylus wins, 18 ties, 78 baseline wins).

## Question type

| Type | Questions | Jylus MAP@10 | Baseline MAP@10 |
| --- | ---: | ---: | ---: |
| `comparison_query` | 95 | 50.880535% | 42.910888% |
| `inference_query` | 87 | 38.274456% | 36.272312% |
| `temporal_query` | 54 | 49.123800% | 37.825176% |

## Null questions

All 20 null questions were retained in the run. The upstream evaluator excludes them. Both systems returned ten documents for 20/20; neither arm produced a valid answerability decision, so no null-answer accuracy is reported.

## Timing

These timings are descriptive and are not a controlled same-hardware comparison.

| Measurement | Mean | P50 | P95 |
| --- | ---: | ---: | ---: |
| Jylus client wall time (Perth to live API and back) | 1858.4 ms | 1878.9 ms | 2209.7 ms |
| Jylus reported server processing | 1421.6 ms | 1443.9 ms | 1753.1 ms |
| Baseline local wall time | 3354.9 ms | 3551.8 ms | 4406.6 ms |

Jylus ingestion: 609 documents in 21 verified batches, 39.169 seconds. Query batch runtime: Jylus 238.671 seconds; baseline 859.180 seconds.

A combined end-to-end wall-clock duration is not reported because the two arms overlapped and the orchestrator's exact overall start time was not retained.

No cost comparison is reported because energy, hardware depreciation, Jylus account pricing and shared service costs were not measured on a common basis.

## Claim boundary

Jylus retrieved better evidence than this NVIDIA-style agentic baseline on this frozen cohort. No final generated answers were evaluated.

This was not an official NVIDIA benchmark, did not compare against NVIDIA's best possible deployment, and did not measure generated-answer correctness.
