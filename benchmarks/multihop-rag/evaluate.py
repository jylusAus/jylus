#!/usr/bin/env python3
"""Score frozen rankings with the published MultiHop-RAG retrieval protocol."""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import math
import statistics
from pathlib import Path
from typing import Any

import numpy as np
from datasets import load_dataset


DATASET = "yixuantt/MultiHopRAG"
DATASET_REVISION = "71ac0d0bd1f951d2d6b70311f7d2ae404e1ffa82"
SELECTION_SALT = "multihop-rag-frozen-v1\0"
ARMS = ("jylus", "nvidia_style_agentic_rag")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def stable_id(prefix: str, value: str) -> str:
    return f"{prefix}-{hashlib.sha256(value.encode('utf-8')).hexdigest()[:40]}"


def corpus_text(row: dict[str, Any]) -> str:
    metadata = "\n".join(
        f"{key}: {row.get(key)}"
        for key in ("title", "source", "author", "published_at", "category")
        if row.get(key)
    )
    return metadata + "\n\n" + str(row.get("body") or "")


def official_question_metrics(retrieved: list[str], gold: list[str]) -> dict[str, float]:
    """Exact per-question form of upstream retrieval_evaluate.py."""
    normalized_gold = [item.replace(" ", "").replace("\n", "") for item in gold]
    normalized_retrieved = [item.replace(" ", "").replace("\n", "") for item in retrieved]
    hit10 = False
    hit4 = False
    average_precision_sum = 0.0
    first_relevant_rank: int | None = None
    found: list[str] = []
    for rank, retrieved_item in enumerate(normalized_retrieved[:11], start=1):
        if any(gold_item in retrieved_item for gold_item in normalized_gold):
            if rank <= 10:
                hit10 = True
                if first_relevant_rank is None:
                    first_relevant_rank = rank
                if rank <= 4:
                    hit4 = True
                count = 0
                for gold_item in normalized_gold:
                    if gold_item in retrieved_item and gold_item not in found:
                        count += 1
                        found.append(gold_item)
                average_precision_sum += count / rank
    return {
        "ap_at_10": average_precision_sum / min(len(normalized_gold), 10),
        "hit_at_10": float(hit10),
        "hit_at_4": float(hit4),
        "mrr_at_10": 1 / first_relevant_rank if first_relevant_rank else 0.0,
    }


def exact_document_metrics(selected: list[str], gold_ids: list[str]) -> dict[str, float]:
    expected = set(gold_ids)
    hit_ranks = [rank for rank, value in enumerate(selected[:10], 1) if value in expected]
    overlap = len(set(selected[:10]) & expected)
    ap = sum(index / rank for index, rank in enumerate(hit_ranks, 1)) / min(len(expected), 10)
    dcg = sum(1 / math.log2(rank + 1) for rank in hit_ranks)
    idcg = sum(1 / math.log2(rank + 1) for rank in range(1, min(len(expected), 10) + 1))
    return {
        "map_at_10": ap,
        "recall_at_10": overlap / len(expected),
        "ndcg_at_10": dcg / idcg,
        "complete_evidence_at_10": float(overlap == len(expected)),
    }


def percentile(values: list[float], fraction: float) -> float:
    return sorted(values)[max(0, math.ceil(fraction * len(values)) - 1)]


def metric_means(rows: list[dict[str, float]], keys: list[str]) -> dict[str, float]:
    return {f"{key}_percent": 100 * statistics.fmean(row[key] for row in rows) for key in keys}


def aggregate(per_question: list[dict[str, Any]], metadata: dict[str, Any]) -> dict[str, Any]:
    answerable = [row for row in per_question if not row["officially_excluded"]]
    nulls = [row for row in per_question if row["officially_excluded"]]
    official_keys = ["ap_at_10", "hit_at_10", "hit_at_4", "mrr_at_10"]
    exact_keys = ["map_at_10", "recall_at_10", "ndcg_at_10", "complete_evidence_at_10"]
    arms: dict[str, Any] = {}
    for arm in ARMS:
        official_rows = [row[arm]["official"] for row in answerable]
        exact_rows = [row[arm]["exact_document"] for row in answerable]
        walls = [float(row[arm]["wall_ms"]) for row in per_question]
        arm_report: dict[str, Any] = {
            "completed_questions": len(per_question),
            "scored_questions": len(answerable),
            "failures": sum(row[arm]["failure"] is not None for row in per_question),
            "official_metrics_percent": metric_means(official_rows, official_keys),
            "supplementary_exact_document_metrics_percent": metric_means(exact_rows, exact_keys),
            "wall_ms": {"mean": statistics.fmean(walls), "p50": percentile(walls, 0.5), "p95": percentile(walls, 0.95)},
            "by_question_type": {},
        }
        for question_type in sorted({row["question_type"] for row in answerable}):
            typed = [row[arm]["official"] for row in answerable if row["question_type"] == question_type]
            arm_report["by_question_type"][question_type] = {
                "questions": len(typed),
                "official_metrics_percent": metric_means(typed, official_keys),
            }
        if arm == "jylus":
            server = [float(row[arm]["server_ms"]) for row in per_question]
            arm_report["server_ms"] = {"mean": statistics.fmean(server), "p50": percentile(server, 0.5), "p95": percentile(server, 0.95)}
        arms[arm] = arm_report

    deltas = np.asarray([row["jylus"]["official"]["ap_at_10"] - row["nvidia_style_agentic_rag"]["official"]["ap_at_10"] for row in answerable])
    generator = np.random.default_rng(42)
    bootstrap = np.asarray([float(np.mean(generator.choice(deltas, size=len(deltas), replace=True))) for _ in range(100_000)])
    jylus_wins = int(np.sum(deltas > 1e-15))
    baseline_wins = int(np.sum(deltas < -1e-15))
    ties = len(deltas) - jylus_wins - baseline_wins
    non_ties = jylus_wins + baseline_wins
    sign_p = sum(math.comb(non_ties, k) for k in range(jylus_wins, non_ties + 1)) / (2**non_ties)
    return {
        "schema": "jylus.multihop-rag-public-summary.v1",
        "evaluation": "internal",
        "dataset": DATASET,
        "dataset_revision": DATASET_REVISION,
        "cohort_questions": len(per_question),
        "officially_scored_questions": len(answerable),
        "officially_excluded_null_questions": len(nulls),
        "averaging": "macro mean over the 236 non-null questions retained by the upstream evaluator",
        "arms": arms,
        "comparison": {
            "primary_metric": "upstream MultiHop-RAG MAP@10",
            "jylus_minus_baseline_points": 100 * float(np.mean(deltas)),
            "paired_bootstrap": {"resamples": 100_000, "seed": 42, "confidence": 0.95, "ci_points": [100 * float(np.quantile(bootstrap, 0.025)), 100 * float(np.quantile(bootstrap, 0.975))]},
            "paired_sign_test": {"alternative": "Jylus > baseline", "jylus_better": jylus_wins, "tie": ties, "baseline_better": baseline_wins, "non_ties": non_ties, "one_sided_p_value": sign_p},
        },
        "null_questions": {
            "count": len(nulls),
            "official_treatment": "excluded by upstream retrieval_evaluate.py",
            "jylus_returned_10": sum(len(row["jylus"]["ranked_document_ids"]) == 10 for row in nulls),
            "baseline_returned_10": sum(len(row["nvidia_style_agentic_rag"]["ranked_document_ids"]) == 10 for row in nulls),
            "answerability_scored": False,
        },
        "run_metadata": metadata,
        "claim_boundary": "Jylus retrieved better evidence than this NVIDIA-style agentic baseline on this frozen cohort. No final generated answers were evaluated.",
    }


def evaluate(rankings_path: Path, metadata_path: Path, per_question_path: Path, weak_cases_path: Path, summary_path: Path) -> dict[str, Any]:
    rankings = read_jsonl(rankings_path)
    if len(rankings) != 256 or len({row["question_id"] for row in rankings}) != 256:
        raise ValueError("rankings must contain exactly 256 unique questions")
    queries = load_dataset(DATASET, "MultiHopRAG", revision=DATASET_REVISION, split="train")
    articles = load_dataset(DATASET, "corpus", revision=DATASET_REVISION, split="train")
    corpus = {stable_id("mhragdoc", str(row["url"])): dict(row) for row in articles}
    url_to_id = {str(row["url"]): stable_id("mhragdoc", str(row["url"])) for row in articles}
    selected = sorted(
        enumerate(queries),
        key=lambda pair: hashlib.sha256((SELECTION_SALT + str(pair[1]["query"])).encode("utf-8")).digest(),
    )[:256]
    expected = {f"mhragq-{index:04d}": (index, dict(query)) for index, query in selected}
    if {row["question_id"] for row in rankings} != set(expected):
        raise ValueError("published question IDs do not match the frozen SHA-256 cohort")

    per_question: list[dict[str, Any]] = []
    for ranking in sorted(rankings, key=lambda row: row["question_id"]):
        question_id = ranking["question_id"]
        dataset_index, query = expected[question_id]
        question_type = str(query["question_type"])
        gold_facts = [str(item["fact"]) for item in query["evidence_list"]]
        gold_ids = list(dict.fromkeys(url_to_id[str(item["url"])] for item in query["evidence_list"]))
        record: dict[str, Any] = {
            "question_id": question_id,
            "dataset_index": dataset_index,
            "question_type": question_type,
            "gold_document_count": len(gold_ids),
            "officially_excluded": question_type == "null_query",
        }
        for arm in ARMS:
            source = ranking[arm]
            ids = list(source["ranked_document_ids"][:10])
            if len(ids) != len(set(ids)) or any(document_id not in corpus for document_id in ids):
                raise ValueError(f"invalid document IDs for {question_id}/{arm}")
            public_arm = dict(source)
            if question_type == "null_query":
                public_arm["official"] = None
                public_arm["exact_document"] = None
            else:
                public_arm["official"] = official_question_metrics([corpus_text(corpus[document_id]) for document_id in ids], gold_facts)
                public_arm["exact_document"] = exact_document_metrics(ids, gold_ids)
            record[arm] = public_arm
        if question_type == "null_query":
            record["outcome"] = "officially_excluded_null"
        else:
            delta = record["jylus"]["official"]["ap_at_10"] - record["nvidia_style_agentic_rag"]["official"]["ap_at_10"]
            record["outcome"] = "jylus_better" if delta > 1e-15 else "baseline_better" if delta < -1e-15 else "tie"
        per_question.append(record)

    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    summary = aggregate(per_question, metadata)
    write_jsonl(per_question_path, per_question)
    weak_cases = []
    for row in per_question:
        if row["officially_excluded"]:
            reason = "officially_excluded_null"
        elif row["outcome"] == "baseline_better":
            reason = "baseline_higher_official_ap"
        elif row["jylus"]["official"]["ap_at_10"] < 0.25:
            reason = "jylus_official_ap_below_0.25"
        else:
            continue
        weak_cases.append({"reason": reason, **row})
    write_jsonl(weak_cases_path, weak_cases)
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rankings", type=Path, required=True)
    parser.add_argument("--metadata", type=Path, required=True)
    parser.add_argument("--per-question", type=Path, required=True)
    parser.add_argument("--weak-cases", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(evaluate(args.rankings, args.metadata, args.per_question, args.weak_cases, args.summary), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
