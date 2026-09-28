# MultiHop-RAG: Jylus vs NVIDIA-style agentic RAG

This folder publishes an **internal retrieval evaluation** on a frozen 256-question subset of [MultiHop-RAG](https://github.com/yixuantt/MultiHop-RAG). It supports this bounded result:

> Jylus retrieved better evidence than this NVIDIA-style agentic baseline on this frozen cohort.

It does not measure final generated-answer accuracy, establish universal superiority, or represent an official NVIDIA benchmark.

## What was tested

The cohort was selected before ranking by taking the 256 lowest values of:

```text
SHA-256("multihop-rag-frozen-v1\0" + question_text)
```

It contains 236 answerable questions and 20 `null_query` questions. Ranking inputs contained no gold evidence.

**Jylus** received all 609 corpus articles through the authenticated public API, then handled each question through the ordinary `/api/v1/analyze` endpoint. Data lived in a dedicated benchmark namespace inside an existing account. The measured service ran in Sydney; the client ran in Perth. Two requests ran concurrently.

**NVIDIA-style agentic RAG** was a local adaptation, not NVIDIA's complete product or best system. It used the planner prompts from the [NVIDIA RAG Blueprint](https://github.com/NVIDIA-AI-Blueprints/rag/blob/cc84e6ac93801acb758570e3415ce355b550cf36/src/nvidia_rag/rag_server/agentic_rag/prompt.py), local `nemotron-3-nano:4b`, BGE-M3 embeddings, up to three planned queries, dense top-20 retrieval per lane and reciprocal-rank fusion (`k=60`) into a top ten. It ran sequentially.

The prompt wording was unchanged. Our adaptation supplied a blank scope section, inserted the question and initial top-20 context into the upstream planner template, limited the plan to three tasks, removed duplicate queries, executed dense retrieval for each lane and fused the ranks. It did not use NVIDIA-hosted models, NVIDIA NIM deployment, a reranker, answer synthesis or verification.

## Primary results

The unchanged upstream evaluator ignores `null_query` records and scores 236 questions. Values below are macro means over those 236 questions.

| System | MAP@10 | Hits@10 | Hits@4 | MRR@10 |
| --- | ---: | ---: | ---: | ---: |
| Jylus | **45.831414%** | **100.000000%** | **88.983051%** | **78.078760%** |
| NVIDIA-style agentic RAG | 39.299937% | 98.728814% | 86.016949% | 70.661320% |

The paired MAP@10 lead was **+6.531477 points**. A 100,000-resample paired bootstrap with seed 42 produced a 95% interval of **+3.749106 to +9.320886 points**. Jylus had higher per-question AP on 140 questions, tied on 18 and was lower on 78; the one-sided paired sign-test was **p = 0.00001608**.

The [generated result report](RESULTS.md) includes type breakdowns, supplementary exact-document metrics and measured timings. Its numbers are generated from [`results/per-question.jsonl`](results/per-question.jsonl) and [`results/run-metadata.json`](results/run-metadata.json).

## The remaining 20 questions

The 20 `null_query` questions were retained and are present in the per-question files. The upstream retrieval evaluator excludes them. Both systems returned ten documents on all 20 questions. The baseline made no answerability decision, and the Jylus completeness field was also false on every answerable request, so it was not a valid null classifier. No null-answer accuracy is claimed.

## Retrieval ranking versus answer accuracy

MAP@10, Hits@10, Hits@4 and MRR@10 describe the ranking of retrieved evidence. They do not show whether a language model would generate the correct final answer. No answer generator or answer judge ran in this evaluation.

## Files

- [`REPRODUCING.md`](REPRODUCING.md): clean installation and exact commands.
- [`CONFIGURATION.md`](CONFIGURATION.md): frozen models, prompts, settings, resources and build identity.
- [`AUDIT.md`](AUDIT.md): sequence, checksums, development exposure and limitations.
- [`benchmark.py`](benchmark.py): dataset preparation, ingestion and both ranking arms.
- [`evaluate.py`](evaluate.py): upstream-compatible MAP@10 matching, exact-document diagnostics, exclusions, failure handling and paired statistics.
- [`generate_report.py`](generate_report.py): generates `RESULTS.md` only from saved results.
- [`results/rankings.jsonl`](results/rankings.jsonl): ranked document IDs and timings for all 256 questions.
- [`results/per-question.jsonl`](results/per-question.jsonl): ranked IDs, timings and question-level scores for both systems.
- [`results/weak-cases.jsonl`](results/weak-cases.jsonl): null questions, baseline wins and Jylus AP below 0.25.
- [`frozen/cohort_ids.txt`](frozen/cohort_ids.txt) and [`frozen/document_ids.txt`](frozen/document_ids.txt): exact public identifiers.

Raw per-document similarity or internal ranking scores were not retained by both arms, so none are invented here. The published `scores` are evaluator scores for each question.

## Data licence

The Hugging Face dataset card labels MultiHop-RAG as [ODC-By](https://huggingface.co/datasets/yixuantt/MultiHopRAG). This repository does not redistribute the corpus, question text, answers or gold facts. The preparation command downloads the pinned dataset directly and builds local ignored files. Upstream code and prompts are linked and cloned at fixed revisions rather than copied here.

