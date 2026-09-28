#!/usr/bin/env python3
"""Combine arm outputs into the public ranking and run-metadata formats."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def utc_mtime(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat().replace("+00:00", "Z")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--jylus-build-id", required=True)
    parser.add_argument("--client-location", default="not recorded")
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    queries = {row["id"]: row for row in read_jsonl(args.data_dir / "queries.jsonl")}
    jylus_path = args.run_dir / "jylus-results.jsonl"
    baseline_path = args.run_dir / "nvidia_agentic_rag-results.jsonl"
    jylus = {row["question_id"]: row for row in read_jsonl(jylus_path)}
    baseline = {row["question_id"]: row for row in read_jsonl(baseline_path)}
    if set(queries) != set(jylus) or set(queries) != set(baseline):
        raise ValueError("both arms must contain every frozen question")
    rows = []
    for question_id in sorted(queries):
        query, j, b = queries[question_id], jylus[question_id], baseline[question_id]
        trace, usage = b.get("trace") or {}, (b.get("trace") or {}).get("usage") or {}
        rows.append({
            "question_id": question_id,
            "dataset_index": query["dataset_index"],
            "question_type": query["question_type"],
            "jylus": {"ranked_document_ids": j.get("selected") or [], "wall_ms": j["wall_ms"], "server_ms": j.get("server_ms") or 0, "failure": j.get("failure")},
            "nvidia_style_agentic_rag": {"ranked_document_ids": b.get("selected") or [], "wall_ms": b["wall_ms"], "retrieval_lanes": trace.get("retrieval_lanes") or 0, "planner_prompt_tokens": usage.get("prompt_tokens") or 0, "planner_completion_tokens": usage.get("completion_tokens") or 0, "failure": b.get("failure")},
        })
    (args.output_dir / "rankings.jsonl").write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    ingest = json.loads((args.run_dir / "jylus-ingest-report.json").read_text(encoding="utf-8"))
    jrun = json.loads((args.run_dir / "jylus-run.json").read_text(encoding="utf-8"))
    brun = json.loads((args.run_dir / "nvidia_agentic_rag-run.json").read_text(encoding="utf-8"))
    metadata = {
        "schema": "jylus.multihop-rag-public-run-metadata.v1",
        "evaluation": "internal",
        "run_date_utc": utc_mtime(baseline_path)[:10],
        "cohort_frozen_at_utc": utc_mtime(args.data_dir / "input-manifest.json"),
        "jylus_rankings_frozen_at_utc": utc_mtime(jylus_path),
        "baseline_rankings_frozen_at_utc": utc_mtime(baseline_path),
        "ingestion": {"documents": ingest["events"], "batches": ingest["batches"], "elapsed_seconds": ingest["elapsed_seconds"], "all_receipts_verified": ingest["all_receipts_verified"]},
        "query_runtime_seconds": {"jylus": jrun["elapsed_seconds"], "nvidia_style_agentic_rag": brun["elapsed_seconds"]},
        "locations": {"client": args.client_location, "jylus": "live public Jylus API", "nvidia_style_agentic_rag": "local workstation"},
        "concurrency": {"jylus": jrun["workers"], "nvidia_style_agentic_rag": brun["workers"]},
        "failures": {"jylus": sum(row["jylus"]["failure"] is not None for row in rows), "nvidia_style_agentic_rag": sum(row["nvidia_style_agentic_rag"]["failure"] is not None for row in rows)},
        "cost_reporting": "not reported; common-basis costs were not measured",
        "jylus_api_build_identifier": args.jylus_build_id,
    }
    (args.output_dir / "run-metadata.json").write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
