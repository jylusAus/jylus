"""Evaluate frozen ranked document IDs without access to retriever internals.

Run only after retrieval has finished. TREC scores encode the supplied rank;
stage-specific relevance scores are retained in input but must not reorder the
system's final evidence order. No source bodies or credentials are required.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import importlib.metadata
import json
import math
import statistics
from pathlib import Path

import numpy as np
import pytrec_eval

METRICS = ("recall_5", "recall_100", "recall_1000", "ndcg_cut_10")


def checksum(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_results(path: Path, qids: list[str]) -> dict[str, list[str]]:
    result = {}
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as source:
        lines = source.read().splitlines()
    for line in lines:
        if not line.strip():
            continue
        row = json.loads(line)
        qid = str(row["query_id"])
        if qid in result:
            raise ValueError(f"duplicate query ID: {qid}")
        docs = row["documents"]
        if [int(doc["rank"]) for doc in docs] != list(range(1, len(docs) + 1)):
            raise ValueError(f"non-contiguous ranked output: {qid}")
        ids = [str(doc["document_id"]) for doc in docs]
        if len(set(ids)) != len(ids) or any(not d or any(c.isspace() for c in d) for d in ids):
            raise ValueError(f"invalid/duplicate document identity: {qid}")
        result[qid] = ids
    if set(result) != set(qids):
        raise ValueError(f"incomplete cohort: {len(result)}/{len(qids)} queries")
    return result


def evaluate(qids: list[str], rankings: dict[str, list[str]], qrels_path: Path):
    with qrels_path.open(encoding="utf-8") as source:
        all_qrels = pytrec_eval.parse_qrel(source)
    if not set(qids) <= set(all_qrels):
        raise ValueError("qrels do not cover the entire cohort")
    qrels = {q: all_qrels[q] for q in qids}
    # These supplied qrels are binary. Fail rather than silently applying an
    # exponential-gain formula to a future differently graded protocol.
    if any(v not in (0, 1) for row in qrels.values() for v in row.values()):
        raise ValueError("this protocol requires binary relevance labels")
    scores = {q: {d: float(1000 - i) for i, d in enumerate(rankings[q][:1000])} for q in qids}
    engine = pytrec_eval.RelevanceEvaluator(qrels, set(METRICS))
    measured = engine.evaluate(scores)
    # Include empty runs explicitly as zero; no query is excluded.
    values = {q: measured.get(q, {m: 0.0 for m in METRICS}) for q in qids}
    details = []
    for q in qids:
        gold = {d for d, v in qrels[q].items() if v > 0}
        if not gold:
            raise ValueError(f"no positive qrels: {q}")
        docs = rankings[q]
        direct = {f"recall_{k}": len(gold.intersection(docs[:k])) / len(gold) for k in (5, 100, 1000)}
        ideal = sum(1 / math.log2(i + 2) for i in range(min(10, len(gold))))
        direct["ndcg_cut_10"] = sum(1 / math.log2(i + 2) for i, d in enumerate(docs[:10]) if d in gold) / ideal
        if any(abs(values[q][m] - direct[m]) > 1e-12 for m in METRICS):
            raise ValueError(f"TREC/formula disagreement: {q}")
        details.append({"query_id": q, **values[q], "returned_documents": len(docs),
                        "relevant_documents": len(gold),
                        "admitted_recall_ceiling": len(gold.intersection(docs)) / len(gold),
                        "missing_from_returned_field": sorted(gold.difference(docs)),
                        "returned_below_1000": [d for d in docs[1000:] if d in gold]})
    return ({m + "_percent": 100 * statistics.mean(values[q][m] for q in qids) for m in METRICS}, details)


def paired_statistics(qids: list[str], before: list[dict], after: list[dict], seed: int):
    left = {r["query_id"]: r for r in before}
    right = {r["query_id"]: r for r in after}
    rng = np.random.default_rng(seed)
    report = {}
    for metric in METRICS:
        delta = np.array([100 * (right[q][metric] - left[q][metric]) for q in qids])
        boot = np.concatenate([delta[rng.integers(0, len(delta), size=(500, len(delta)))].mean(axis=1)
                               for _ in range(20)])
        report[metric] = {"delta_points": float(delta.mean()),
                          "paired_bootstrap_95_percent_interval_points": np.quantile(boot, [0.025, 0.975]).tolist(),
                          "improved_queries": int((delta > 1e-12).sum()),
                          "regressed_queries": int((delta < -1e-12).sum()),
                          "unchanged_queries": int((np.abs(delta) <= 1e-12).sum())}
    return {"method": "paired query bootstrap; percentile interval; descriptive, unadjusted for tuning",
            "seed": seed, "resamples": 10000, "metrics": report}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--queries", type=Path, required=True)
    p.add_argument("--results", type=Path, required=True)
    p.add_argument("--evidence-qrels", type=Path, required=True)
    p.add_argument("--gold-qrels", type=Path, required=True)
    p.add_argument("--reference", type=Path)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--expected-queries", type=int, default=830)
    p.add_argument("--seed", type=int, default=20261002)
    args = p.parse_args()
    with args.queries.open(encoding="utf-8") as f:
        qids = [row[0] for row in csv.reader(f, delimiter="\t") if row]
    if len(qids) != args.expected_queries or len(set(qids)) != len(qids):
        raise ValueError("unexpected query inventory")
    rankings = load_results(args.results, qids)
    reference = load_results(args.reference, qids) if args.reference else None
    report = {"schema": "retrieval-only-frozen-results.v1", "questions": len(qids),
              "averaging": "unweighted mean over every query in the specified complete cohort",
              "scoring": "binary qrels; TREC recall and nDCG; supplied final rank retained",
              "retrieval_only": True, "answer_accuracy_measured": False,
              "evaluator": {"pytrec-eval-terrier": importlib.metadata.version("pytrec-eval-terrier")},
              "input_checksums": {"queries": checksum(args.queries), "results": checksum(args.results),
                                  "evidence_qrels": checksum(args.evidence_qrels), "gold_qrels": checksum(args.gold_qrels)},
              "empty_query_results": sum(not rankings[q] for q in qids), "metrics": {}}
    if args.reference:
        report["input_checksums"]["reference"] = checksum(args.reference)
    detail_rows = {q: {"query_id": q} for q in qids}
    for label, qrels in (("evidence", args.evidence_qrels), ("gold", args.gold_qrels)):
        metrics, details = evaluate(qids, rankings, qrels)
        ceiling = 100 * statistics.mean(r["admitted_recall_ceiling"] for r in details)
        block = {"candidate": metrics, "macro_admission_ceiling_percent": ceiling,
                 "gap_diagnosis": {
                     "relevant_pairs_missing_from_returned_field": sum(len(r["missing_from_returned_field"]) for r in details),
                     "relevant_pairs_returned_below_1000": sum(len(r["returned_below_1000"]) for r in details),
                     "questions_missing_relevant_sources": sum(bool(r["missing_from_returned_field"]) for r in details),
                     "ranking_only_ceiling_gain_points": ceiling - metrics["recall_1000_percent"],
                     "ceiling_is_oracle_diagnostic_not_achieved_score": True}}
        for row in details:
            detail_rows[row["query_id"]][label] = row
        if reference is not None:
            old, old_details = evaluate(qids, reference, qrels)
            block["reference"] = old
            block["paired_statistics"] = paired_statistics(qids, old_details, details, args.seed)
        report["metrics"][label] = block
    args.out.mkdir(parents=True, exist_ok=True)
    trec = args.out / "rank-order.trec"
    with trec.open("w", encoding="utf-8", newline="\n") as f:
        for q in qids:
            for i, d in enumerate(rankings[q][:1000], 1):
                f.write(f"{q} Q0 {d} {i} {1001-i} frozen-native\n")
    with trec.open(encoding="utf-8") as f:
        reloaded = pytrec_eval.parse_run(f)
    for q in qids:
        if sorted(reloaded.get(q, {}), key=lambda d: -reloaded[q][d]) != rankings[q][:1000]:
            raise ValueError(f"TREC serialization changed ranked order: {q}")
    report["rank_order_trec_sha256"] = checksum(trec)
    per_question = args.out / "per-question-metrics.jsonl"
    per_question.write_text("".join(json.dumps(detail_rows[q], sort_keys=True) + "\n" for q in qids), encoding="utf-8")
    report["per_question_metrics_sha256"] = checksum(per_question)
    (args.out / "summary.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
