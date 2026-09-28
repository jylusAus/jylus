#!/usr/bin/env python3
"""Generate RESULTS.md only from results/summary.json."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def f(value: float, digits: int = 3) -> str:
    return f"{value:.{digits}f}"


def render(summary: dict[str, Any]) -> str:
    j = summary["arms"]["jylus"]
    b = summary["arms"]["nvidia_style_agentic_rag"]
    jm = j["official_metrics_percent"]
    bm = b["official_metrics_percent"]
    comparison = summary["comparison"]
    ci = comparison["paired_bootstrap"]["ci_points"]
    sign = comparison["paired_sign_test"]
    nulls = summary["null_questions"]
    meta = summary["run_metadata"]
    lines = [
        "# Frozen 256-question results",
        "",
        "> Internal evaluation. These are retrieval-ranking results, not answer accuracy.",
        "",
        "The unchanged upstream MultiHop-RAG retrieval protocol scored 236 answerable questions and excluded 20 `null_query` questions.",
        "",
        "| System | MAP@10 | Hits@10 | Hits@4 | MRR@10 |",
        "| --- | ---: | ---: | ---: | ---: |",
        f"| Jylus | **{f(jm['ap_at_10_percent'], 6)}%** | **{f(jm['hit_at_10_percent'], 6)}%** | **{f(jm['hit_at_4_percent'], 6)}%** | **{f(jm['mrr_at_10_percent'], 6)}%** |",
        f"| NVIDIA-style agentic RAG | {f(bm['ap_at_10_percent'], 6)}% | {f(bm['hit_at_10_percent'], 6)}% | {f(bm['hit_at_4_percent'], 6)}% | {f(bm['mrr_at_10_percent'], 6)}% |",
        "",
        f"Jylus MAP@10 lead: **+{f(comparison['jylus_minus_baseline_points'], 6)} points**. Paired 100,000-resample bootstrap 95% interval: **+{f(ci[0], 6)} to +{f(ci[1], 6)} points**. One-sided paired sign-test: **p = {sign['one_sided_p_value']:.8g}** ({sign['jylus_better']} Jylus wins, {sign['tie']} ties, {sign['baseline_better']} baseline wins).",
        "",
        "## Question type",
        "",
        "| Type | Questions | Jylus MAP@10 | Baseline MAP@10 |",
        "| --- | ---: | ---: | ---: |",
    ]
    for question_type in ("comparison_query", "inference_query", "temporal_query"):
        jr = j["by_question_type"][question_type]
        br = b["by_question_type"][question_type]
        lines.append(f"| `{question_type}` | {jr['questions']} | {f(jr['official_metrics_percent']['ap_at_10_percent'], 6)}% | {f(br['official_metrics_percent']['ap_at_10_percent'], 6)}% |")
    lines += [
        "",
        "## Null questions",
        "",
        f"All {nulls['count']} null questions were retained in the run. The upstream evaluator excludes them. Both systems returned ten documents for {nulls['count']}/{nulls['count']}; neither arm produced a valid answerability decision, so no null-answer accuracy is reported.",
        "",
        "## Timing",
        "",
        "These timings are descriptive and are not a controlled same-hardware comparison.",
        "",
        "| Measurement | Mean | P50 | P95 |",
        "| --- | ---: | ---: | ---: |",
        f"| Jylus client wall time (Perth to live API and back) | {f(j['wall_ms']['mean'], 1)} ms | {f(j['wall_ms']['p50'], 1)} ms | {f(j['wall_ms']['p95'], 1)} ms |",
        f"| Jylus reported server processing | {f(j['server_ms']['mean'], 1)} ms | {f(j['server_ms']['p50'], 1)} ms | {f(j['server_ms']['p95'], 1)} ms |",
        f"| Baseline local wall time | {f(b['wall_ms']['mean'], 1)} ms | {f(b['wall_ms']['p50'], 1)} ms | {f(b['wall_ms']['p95'], 1)} ms |",
        "",
        f"Jylus ingestion: {meta['ingestion']['documents']} documents in {meta['ingestion']['batches']} verified batches, {f(meta['ingestion']['elapsed_seconds'], 3)} seconds. Query batch runtime: Jylus {f(meta['query_runtime_seconds']['jylus'], 3)} seconds; baseline {f(meta['query_runtime_seconds']['nvidia_style_agentic_rag'], 3)} seconds.",
        "",
        "A combined end-to-end wall-clock duration is not reported because the two arms overlapped and the orchestrator's exact overall start time was not retained.",
        "",
        "No cost comparison is reported because energy, hardware depreciation, Jylus account pricing and shared service costs were not measured on a common basis.",
        "",
        "## Claim boundary",
        "",
        summary["claim_boundary"],
        "",
        "This was not an official NVIDIA benchmark, did not compare against NVIDIA's best possible deployment, and did not measure generated-answer correctness.",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    summary = json.loads(args.summary.read_text(encoding="utf-8"))
    args.output.write_text(render(summary), encoding="utf-8")


if __name__ == "__main__":
    main()
