# Reproduction and access limits

The saved rankings can be rescored without a Jylus account. Querying Jylus needs
an API key and a workspace provisioned for this corpus and the recorded service
version. The proprietary Jylus stack and historical collection profile are not
downloadable from this repository. Exact historical re-ingest parity has **not**
been demonstrated. These scripts reproduce the public request and scoring
contract; access to the matching provisioned service is an additional requirement.

## Install and obtain the official data locally

Use Python 3.12. Commands below are POSIX shell syntax; on Windows use the venv's
`Scripts/python.exe` instead of `python` after activation. Keep decrypted data
outside this repository and do not upload it.

```sh
python -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
python -m pip install pyarrow==21.0.0 datasets==4.1.1
git clone https://github.com/texttron/BrowseComp-Plus.git upstream
git -C upstream checkout 046949032b0328319cc9a02663a759ec601d9402
python -c "from pathlib import Path; Path('data').mkdir(exist_ok=True)"
python upstream/scripts_build_index/decrypt_dataset.py --output data/browsecomp_plus_decrypted.jsonl --generate-tsv data/queries.tsv
python verify_inputs.py --queries data/queries.tsv --evidence-qrels upstream/topics-qrels/qrel_evidence.txt --gold-qrels upstream/topics-qrels/qrel_golds.txt
python download_corpus.py --directory data
python prepare_corpus.py --directory data
```

Hugging Face login may be required for the obfuscated queries. The official
repository supplies `topics-qrels/qrel_evidence.txt` and `qrel_golds.txt` at this
commit (the README's singular `qrel_gold.txt` spelling differs from the file).
The corpus is 100,195 documents; download size is about 1.76 GB. Leave ample disk
space for parquet, decompressed text, the query response logs and any local index.
The gzip container checksum can change with its timestamp; shard checksums and
document text, not the gzip timestamp, establish corpus equivalence.

## Rescore the published output — no API calls

```sh
python evaluate.py --queries query-ids.tsv --results results/jylus-live.jsonl.gz --evidence-qrels upstream/topics-qrels/qrel_evidence.txt --gold-qrels upstream/topics-qrels/qrel_golds.txt --reference results/jylus-v30-reference.jsonl.gz --out rescored --expected-queries 830
```

This preserves supplied rank, verifies contiguous ranks/unique IDs, includes
every question and calculates the eight official retrieval metrics. Native
floating-point scores must not be used to reorder results. Empty rankings score
zero; missing or duplicate questions cause an error instead of an exclusion.
`report.py` generates the summary directly from these outputs.

```sh
python report.py --summary rescored/summary.json --manifest results/run-manifest.json --out reproduced-report.md
```

The input verifier accepts Windows CRLF or LF line endings, but requires the
exact frozen question and label contents. The upstream query downloader does
not pin a dataset revision internally; this checksum gate rejects changed data.

## Ingest through the ordinary API, then query

Obtain a key from Jylus. Set `JYLUS_API_KEY` in your shell without adding it to a
file in Git. Ask Jylus for the benchmark service build/profile in `config.json`
and sufficient workspace capacity before submitting this corpus. Use your own
new namespace. The following first command validates event batching without
sending data. The second sends real records via the NATS-backed public API.

```sh
python ingest.py --corpus data/browsecomp-plus-corpus.jsonl.gz --namespace my-browsecomp-run --out dry-run.json
python ingest.py --corpus data/browsecomp-plus-corpus.jsonl.gz --namespace my-browsecomp-run --out ingest-report.json --execute
python retrieve.py --queries data/queries.tsv --query-ids query-ids.tsv --namespace my-browsecomp-run --out my-query-run --workers 2
python evaluate.py --queries query-ids.tsv --results my-query-run/results.jsonl --evidence-qrels upstream/topics-qrels/qrel_evidence.txt --gold-qrels upstream/topics-qrels/qrel_golds.txt --out my-scores --expected-queries 830
```

Durable event acknowledgement is not proof of query readiness: wait for the
provider's collection-readiness check before retrieval. Ingestion sends source
text/IDs only; retrieval never opens qrels or answers. The portable client makes
one request per question, retains failures as empty rankings and exits nonzero
if any fail. It uses direct HTTP rather than the original private transport
bridge. Its latency is measured at your client and is not the published on-host
latency. It has no deployment/admin controls and cannot change the live release.
Neither a model nor a GPU is used by this retrieval-only Jylus arm.

## Published baseline rows

Upstream baseline rows are published results, not fresh head-to-head runs.
Reproduce them using the exact upstream retrieval/indexing implementation and
hardware instructions linked from the pinned BrowseComp-Plus repository:

- [Tevatron BrowseComp-Plus example](https://github.com/texttron/tevatron/tree/main/examples/BrowseComp-Plus)
- [Pre-built index downloads at the pinned commit](https://github.com/texttron/BrowseComp-Plus/blob/046949032b0328319cc9a02663a759ec601d9402/scripts_build_index/download_indexes.sh)
- [Official retrieval-only scoring protocol](https://github.com/texttron/BrowseComp-Plus/blob/046949032b0328319cc9a02663a759ec601d9402/README.md#evaluating-retrieval-only-results)

No competitor timing/cost/answer accuracy is claimed. The historical Jylus v30
reference is included for paired quality analysis; that service image is also
not distributed and its old transport differs from today's public HTTPS path.
