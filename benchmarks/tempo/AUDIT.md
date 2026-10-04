# TEMPO evaluation audit

This is an internal normal-query retrieval evaluation, not an independently
validated leaderboard entry or final-answer evaluation. The complete query
inventory had been used during earlier Jylus development and evaluation. The
current run is fresh API measurement of the recorded build, not a newly blind
held-out cohort. Official labels and prior failures informed earlier analysis;
labels are never passed to the runtime retrieval service.

## Sequence and scope

The original corpus revision was ingested before this run. The subsequent
official protocol revision adds per-query exclusions; its query text and source
identity mapping were checked against the existing inventory. Prior runs and
the lightweight guard preceded this full measurement. Neither is substituted
for a fresh full-run result.

The full cohort was requested on October 4, 2026 after the live build was already
active. Runtime code remained unchanged. Requests originate on the deployment
host and pass through the ordinary public HTTPS API using the tenant's API key.
The local controller's SSH result transfer is excluded from HTTP timing. The
host is shared with ordinary production traffic; ingest continues, and no other
benchmark is run concurrently.

Before and after retrieval, three source chunks in each of thirteen collections
are compared with immutable source controls. These 39 checks are sampled source
controls, not a cryptographic proof of every corpus byte. Every returned source
ID is independently checked against its immutable same-domain inventory;
exclusions, source event identity, contiguous evidence ranks and compiler proof
order are validated for every measured response. Active service images, process
starts, restart counts, health and available RAM are monitored during the run.

Scoring opens official gold labels only after retrieval is complete. All 1,730
queries and any failures remain in the denominator. Empty failures score zero;
missing identities cannot be silently removed. The saved full response receipts
remain private because they include source text and operational information.
The public export contains only benchmark IDs, ranks, source scores, statuses
and timing measurements. Relevance is binary membership in official `gold_ids`.

No inference model, embedding model, trained reranker, query-specific stored
answer packet, supplied gold, step plan or paid temporal judge is used by this
retrieval client. The `vector.text` API field contains the entire original
question; it is not an external embedding supplied by the evaluator. The native
service implementation remains proprietary and is excluded from this package.

## Interpretation and reproduction limits

NDCG@10 measures retrieval ranking. It does not establish Temporal Precision,
Temporal Coverage, answer accuracy, hallucination rate or universal superiority.
The question mean and domain macro use different denominators. Compare the
domain macro with the official domain-macro leaderboard, rather than comparing
the full question mean with those rows.

HTTP response timings include request transmission, response read and JSON
decoding on the host client. Request-cache bypass does not flush existing source
caches. These are mixed warm-cache measurements, not cold-start or uniform
millisecond guarantees. Ingestion time and query batch runtime are separate;
no complete ingestion-to-ready time or monetary cost comparison is claimed.

The provider's exact corpus profile and service version are required for fresh
API reproduction. A clean saved-ranking rescore is reproducible independently,
but a fresh full-corpus API re-ingest has not been shown to reproduce this
result. That limitation must remain visible to leaderboard reviewers.

Dataset download URLs and input checksums are supplied instead of redistributing
the official corpus/query/answer files. The dataset card states CC BY 4.0;
credit the TEMPO authors and retain the upstream attribution. Credentials,
customer records, private deployment addresses and proprietary service code
are excluded from all public artifacts.

## Recorded evaluator correction

The original full-run harness rejected 2 responses under a new requirement
that every ranked retrieval document have a retained compiler proof. The
previously used contract checks the order of the actual retained proof prefix.
Both retrieval and that existing contract were valid in these cases. After
retrieval finished, all 1,730 saved receipts were revalidated consistently, with
no API repetition, ranking change or removal of difficult questions. Original
failure records remain preserved privately. The published score uses all actual
rankings, and the bounded-prefix counts are in the measurement manifest.
