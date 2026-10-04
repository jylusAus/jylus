# Retrieval-only leaderboard submission

Requirements were checked on 2026-10-04 against the official
[retrieval-only submission instructions](https://github.com/texttron/BrowseComp-Plus#submitting-retrieval-only-results-to-the-leaderboard).
The authors ask for a JSON with the retriever name, eight retrieval metrics,
a public model-card link and the evaluation date. Send that JSON to
**s42chen@uwaterloo.ca** for maintainer review.

This package is prepared for submission. Publishing it on GitHub does not
submit it to the leaderboard, establish acceptance or independently validate
the result. No submission email has been sent.

## Submission files

- [leaderboard-submission.json](leaderboard-submission.json): the exact eleven
  official fields, generated from the complete saved result. Metrics use the
  TREC evaluator's 0–1 values; the README displays the same values as percentages.
- [README.md](README.md): the public service/model card linked by the JSON,
  measured results, retrieval-only scope and interpretation.
- [results/rank-order.trec.gz](results/rank-order.trec.gz): all 830 questions,
  1,000 ranked document IDs per question, standard six-column TREC format.
  Scores encode supplied final rank as `1001 - rank`. Source relevance scores
  remain in the JSONL export and must not be used to reorder final evidence.
- [results/jylus-live.jsonl.gz](results/jylus-live.jsonl.gz): IDs, final ranks,
  source scores, HTTP status and timings for every question, including weak cases.
- [results/summary.json](results/summary.json),
  [per-question metrics](results/per-question-metrics.jsonl),
  [config.json](config.json), [REPRODUCTION.md](REPRODUCTION.md),
  [AUDIT.md](AUDIT.md) and [SHA256SUMS](SHA256SUMS): scoring evidence,
  frozen inputs, access requirements, limitations and file integrity.
- [submission-email.txt](submission-email.txt): ready-to-send review request.

## Reviewer verification

After installing `requirements.txt` and obtaining the pinned official qrels as
described in [REPRODUCTION.md](REPRODUCTION.md), run:

```sh
python verify_submission.py --evidence-qrels upstream/topics-qrels/qrel_evidence.txt --gold-qrels upstream/topics-qrels/qrel_golds.txt
```

This checks the official schema, all 830 queries, exact official label hashes,
TREC-versus-JSONL rank identity and all eight submission values against the
saved summary. It makes no API calls and needs no Jylus account or GPU.

For the upstream TREC evaluator command, after installing its Pyserini/Java
requirements separately:

```sh
gzip -dc results/rank-order.trec.gz > rank-order.trec
python -m pyserini.eval.trec_eval -c -m recall.5,100,1000 -m ndcg_cut.10 upstream/topics-qrels/qrel_evidence.txt rank-order.trec
python -m pyserini.eval.trec_eval -c -m recall.5,100,1000 -m ndcg_cut.10 upstream/topics-qrels/qrel_golds.txt rank-order.trec
```

The pinned repository uses `qrel_golds.txt`; its README spells the filename
`qrel_gold.txt`. Both evaluations retain every official question.

## Scope for the maintainers

Submit to the **retrieval-only** category. This native service run has no
LLM agent, generated answers, answer accuracy or answer judge. The agent
submission format on the main leaderboard is a separate protocol and its
answer-accuracy fields must not be fabricated for this result.

This is an internal evaluation; the development cohort and full cohort had
been used during prior analysis. It is not blind independent validation.
The matching proprietary service build/profile is not downloadable, and fresh
full-corpus API re-ingest parity has not been demonstrated. Saved-result
scoring is reproducible without service access. Those limitations are disclosed
in the linked model card and audit for the maintainers to assess.

Corpus/question/answer plaintext and raw qrels are not redistributed. Download
official labels directly from upstream. Only benchmark clients, numeric results,
IDs and methodology are published; proprietary service code, credentials,
customer records and private deployment addresses are excluded.
