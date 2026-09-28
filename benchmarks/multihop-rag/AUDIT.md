# Audit sequence and limitations

## Evaluation sequence

All times are UTC on 28 September 2026.

1. **00:20:02.944** — the 256-question cohort and 609-document corpus manifest were frozen. Selection used only question text hashes. Runtime inputs excluded gold.
2. **00:26:13** — the dedicated Jylus namespace was created in an existing authenticated account. An attempted disposable benchmark route returned HTTP 404, so the successful run used namespace isolation and recorded that limitation.
3. **00:26:52** — ingestion completed: 609 documents, 21/21 verified batches, 39.169 seconds.
4. **00:31:25** — all 256 Jylus rankings were frozen. Query batch runtime was 238.671 seconds at two concurrent requests.
5. After the Jylus rankings froze, a Jylus-only scoring preview was viewed while the already-configured baseline run was still in progress. The preview's exact timestamp was not retained. No cohort, prompt, model, retrieval setting, service build or frozen Jylus output changed after the preview.
6. **00:38:17** — all 256 baseline rankings were frozen. Query batch runtime was 859.180 seconds, sequentially.
7. **00:39:42** — evaluator inputs for both frozen outputs were exported.
8. **00:40:53** — the unchanged upstream retrieval evaluator completed. The paired analysis then used the frozen per-question outputs.

The timestamps above come from the saved manifest contents and file modification times. The absence of a separately timestamped preview receipt is retained as a limitation.

SHA-256 values for the original frozen arm outputs, official score, paired analysis and evaluator output are recorded in [`results/run-metadata.json`](results/run-metadata.json). Hashes for every published file are in [`results/checksums.sha256`](results/checksums.sha256); text is normalized to LF before hashing so Windows and Unix checkouts verify identically.

## Development exposure

This is an internal evaluation, not a blind or independent validation. Jylus had been developed and evaluated on other retrieval and reasoning datasets before this run. This exact SHA-256 cohort was selected before ranking and was not used to change the deployed Jylus build. The Jylus-only preview occurred only after its output and the baseline configuration were frozen. The baseline output was still running, so the final paired result was not available at preview time.

## Failures and exclusions

- Both arms produced result records for 256/256 questions; recorded execution failures: 0.
- The official evaluator scored 236 answerable questions.
- All 20 `null_query` questions were retained but excluded by the upstream evaluator.
- No result was removed for latency, low score or difficulty.
- Weak cases are published using a fixed rule: every null question, every baseline AP win and every answerable question where Jylus official AP@10 was below 0.25.

## Metric definitions

The primary metrics reproduce `retrieval_evaluate.py` from the MultiHop-RAG repository at revision `c1c1287`. It removes spaces and newlines from retrieved text and gold facts, then counts a gold fact when its normalized text is contained in a retrieved document. MAP@10 is the macro mean across non-null questions. Hits@10, Hits@4 and MRR@10 follow the same matches.

Supplementary exact-document MAP, recall, NDCG and complete-evidence values compare stable document IDs derived from dataset URLs. They are not the upstream primary metric.

## Timing and cost limitations

- Jylus client wall time includes the Perth-to-Sydney network path.
- Jylus server time is the service-reported processing header.
- Baseline wall time is local Windows process time.
- The systems used different hardware and deployment resources.
- Ingestion time, per-query time and total batch runtime are reported separately.
- No cost comparison is published because energy, hardware depreciation, account pricing and shared-service costs were not measured on a common basis.

## Reproducibility limitation

The dataset, evaluator logic, cohort, baseline code path and saved rankings are public and reproducible. The measured Jylus build is a proprietary hosted service and is identified only by an opaque build ID. It cannot be installed from this repository; rerunning against a later public service version tests that later version.

## Publication boundary

This repository contains benchmark code, stable public dataset identifiers and sanitized outputs. It does not contain credentials, customer data, dataset text, answers, gold facts, server addresses, private paths or Jylus implementation details.
