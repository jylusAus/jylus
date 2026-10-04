# Audit and limitations

This is an internal retrieval-only evaluation. It has not been independently
validated and is not an official NVIDIA, Hornet or BrowseComp-Plus evaluation.
There is no agent, answer model, prompt or answer judge in this Jylus run.

## Actual sequence

1. On September 28–29, pinned corpus shards/IDs were downloaded, verified and
   ingested through the normal tenant API, backed by NATS. An initial native
   retrieval/scoring preview preceded later candidate evaluation. Runtime
   query inputs never included labels or expected answers.
2. On September 30, the retained v30 full-830 reference was measured. A
   deterministic 100-question cohort (lowest SHA-256 of query ID) and offline
   failure analyses were used to investigate candidate changes.
3. On October 1–2, multiple candidates were compared on that development cohort.
   Tail-reordering and rarity experiments were rejected for recall/ranking
   regressions. The retained v31 variant was selected and measured over all 830
   on October 2. Thus the full cohort had previously been scored too; this is
   not a newly untouched held-out set.
4. On October 3, an execution-only source lookup improvement was tested before
   the final run. No scoring or model-based reranking change was included in it.
5. On October 4 at 01:12:24 UTC, the tested build became the active public API
   version. API authentication and source/proof checks passed before this run.
6. The final 830 public HTTPS run used frozen runtime code and the same benchmark
   corpus generation; no candidate tuning occurred during it. All original
   questions, difficult cases and returned rankings are retained. The output
   directory creation/completion times and duration are in the run manifest.
7. Only after retrieval completed were the saved rankings scored against both
   official qrel sets. The sanitized published output was independently rescored
   in a fresh Python virtual environment. Report tables are generated from it.

## Scope and resource differences

The current run used ordinary API-key authentication on the live public HTTPS
path, with HTTP requests originating on the deployment host. The controller
transport is private and excluded from reported HTTP timings. The historical
v30 reference and October 2 v31 check were isolated-instance runs using a
different transport. Quality metrics are comparable; their timing is not a
controlled comparison. Published competitor rows are upstream results, not
fresh runs on our server. No competitor latency, cost, final-answer or resource
equivalence claim is made.

The historical reference allowed up to eight bridge-recovery attempts after
specific transport interruptions; the current measured client made one attempt
per question. The old bridge-attempt count is not completely measured. Final
HTTP statuses are retained, and no timing, cost or failure-rate advantage is
claimed from that differently instrumented reference.

The 100-question selection was independent of qrels, but subsequent development
used those qrels and results. Bootstrap intervals are descriptive and do not
adjust for repeated candidate selection. Per-question results include weak
rankings. Full response source/proof checks were made during release canaries;
the full 830 retrieval export checks scope, document identities and evidence
rank. It does not independently certify every downstream generated claim.

The benchmark collection used a provider-side ingestion profile. Its proprietary
implementation is not distributed, and freshly ingesting the entire corpus
into a new account has not been shown to reproduce the recorded result. Use the
matching provider-provisioned version/profile for a comparable API run. Generic
API client, ingestion, scoring and record-format instructions are supplied.
No saved question-to-answer packet or qrel data is deployed as runtime code.

## Failures, data and verification

Earlier rejected BrowseComp candidates and failed retrieval attempts were
retained privately and were not relabeled as the final measured result.
Final full-cohort query failures, retries and timing coverage are reported in
the results manifest. Missing queries are a scorer error; empty failed outputs
score zero, never disappear from the denominator.

The corpus card and upstream software identify MIT licensing. The dataset also
requests that decrypted benchmark plaintext stay off the public web. We publish
document/question IDs, numeric rankings and aggregate metrics, but no corpus
text, question text, answers, raw qrels, customer data, credentials, private
addresses or proprietary service implementation. Obtain labels directly from
upstream. The corpus shard checksums and all publication file checksums are
included; checksums alone do not constitute independent validation.

Clean-environment validation covers dependency installation, fresh download and
checksum verification of all seven corpus shards, conversion of all 100,195
documents, and offline batching of 169,904 source events into 3,773 batches.
That batching was a dry run and submitted no events. Request semantics,
scope/rank rejection, rank-preserving deduplication, empty-query handling and
complete saved-result scoring were also verified. It does **not** cover an
independent full service rebuild or fresh full-corpus API ingestion. The
leaderboard submission file is prepared in
upstream's 0–1 metric units; no submission email is sent by this publication.
