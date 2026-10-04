# Reproducing the TEMPO normal-query evaluation

The saved-result evaluation needs Python 3.12, approximately 10 MB of pinned
official query/label Parquet files, and the packages below. It needs no Jylus
account, GPU, model or paid judge.

```sh
git clone https://github.com/jylusAus/jylus.git
cd jylus/benchmarks/tempo
python -m venv .venv
# Linux/macOS: source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python download_data.py --out data
python evaluate.py --data data --results results/rankings.jsonl.gz --out rescored
```

Compare `rescored/summary.json` and its per-domain values with the published
summary. The scorer checks all 1,730 identities, input hashes, duplicate ranks,
protocol exclusions and an independent NDCG calculation against TREC. Failed
queries remain in the denominator with zero score; missing queries are errors.

The data comes from [tempo26/Tempo](https://huggingface.co/datasets/tempo26/Tempo),
licensed CC BY 4.0. Corpus inputs are pinned to
`f9df06c05688225e37701974d23c8e3c5d4efaf6`; examples, gold labels and the official
paper/leaderboard exclusions are pinned to its subsequent protocol revision
`1dba7027d0afa628993c6dd794e9b68c657a6fac`. Every file hash is in `config.json`.
No corpus, query text, gold answers or labels are redistributed here.

## Fresh Jylus API retrieval

Fresh requests require an API key authorized for the benchmark corpus, a
provider-provisioned copy of all 1,654,055 official documents in the thirteen
configured collections, and the matching service build/profile. Each collection
is scoped independently. The measured build is identified in `config.json`;
its proprietary service implementation is not downloadable.

The corpus itself can be downloaded and verified with:

```sh
python download_data.py --out data --documents
```

Provisioning the matching provider ingestion/index profile is an access
requirement. This publication has not demonstrated that generic ingestion into a
new account reproduces the existing collection's ranking. It does not provide a
standalone server rebuild or promise that the currently available service has
the identical historical build. Request the recorded profile/build from Jylus
before treating a fresh request as a reproduction of this result.

After obtaining that access, set `JYLUS_API_KEY` locally without adding it to Git,
then run:

```sh
python retrieve.py --data data --out fresh-results.jsonl.gz
python evaluate.py --data data --results fresh-results.jsonl.gz --out fresh-score
```

The client uses the ordinary authenticated public `v1/analyze` API, two workers,
original normal queries and official exclusions. It reads only query ID, query
text and exclusion columns during retrieval. It takes final `evidence_rank`
order, verifies source/collection scope and compiler proof order, and does not
sort by source relevance scores. It records failures and up to four attempts
for an incomplete top ten. No agent, prompt expansion, reasoning-query dataset,
step-wise retrieval or gold-guided runtime selection is used.

The published ranking IDs are official document IDs. The public API client's
fresh output uses the service's documented hash projection; the scorer supports
both formats and applies the same projection to downloaded official labels.

## Official evaluator comparison

The upstream [`run.py`](https://github.com/tempo-bench/Tempo/blob/8731487254e0988eaf2ca4ae3e93ff587fec64d0/run.py)
calls the TREC evaluator independently for each domain, then averages thirteen
domain means. This package reports that domain macro and the unweighted mean
across all 1,730 queries separately. It also reports the upstream rounding
sequence separately; percentages and 0–1 values are explicitly labeled.

Temporal Precision and Temporal Coverage require the separate temporal judging
protocol. No TP@10 or TC@10 is inferred from this retrieval score, and none is
included in this submission.
