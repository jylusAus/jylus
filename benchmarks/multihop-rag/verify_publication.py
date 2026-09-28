#!/usr/bin/env python3
"""Verify hashes, disclosure boundaries and deterministic scoring."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import tempfile
from pathlib import Path

from evaluate import evaluate
from generate_report import render


ROOT = Path(__file__).resolve().parent
CHECKSUMS = ROOT / "results" / "checksums.sha256"


def public_files() -> list[Path]:
    ignored_parts = {".git", ".venv", "__pycache__", "data", "cache", "runs", "vendor"}
    return sorted(
        path for path in ROOT.rglob("*")
        if path.is_file() and path != CHECKSUMS and path != ROOT / "config.json" and not any(part in ignored_parts for part in path.relative_to(ROOT).parts)
    )


def digest(path: Path) -> str:
    data = path.read_bytes()
    try:
        normalized = data.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")
    except UnicodeDecodeError:
        normalized = data
    return hashlib.sha256(normalized).hexdigest()


def jsonl_rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_checksums() -> None:
    CHECKSUMS.parent.mkdir(parents=True, exist_ok=True)
    CHECKSUMS.write_text("".join(f"{digest(path)}  {path.relative_to(ROOT).as_posix()}\n" for path in public_files()), encoding="utf-8")


def verify_checksums() -> None:
    expected = {}
    for line in CHECKSUMS.read_text(encoding="utf-8").splitlines():
        value, name = line.split("  ", 1)
        expected[name] = value
    actual = {path.relative_to(ROOT).as_posix(): digest(path) for path in public_files()}
    if expected != actual:
        missing = sorted(set(expected) - set(actual))
        added = sorted(set(actual) - set(expected))
        changed = sorted(name for name in set(expected) & set(actual) if expected[name] != actual[name])
        raise SystemExit(f"checksum mismatch: missing={missing}, added={added}, changed={changed}")


def verify_disclosure_boundary() -> None:
    forbidden_terms = ["h" + "mt", "s" + "fm", "context" + " compiler"]
    secret_patterns = [r"ghp_[A-Za-z0-9]{20,}", r"github_pat_[A-Za-z0-9_]{20,}", r"C:\\Users\\", r"C:\\Jylus-Benchmark", r"/opt/jylus"]
    public_ip = re.compile(r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])")
    failures = []
    for path in public_files():
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        lowered = text.casefold()
        if path.name != Path(__file__).name:
            for term in forbidden_terms:
                if term in lowered:
                    failures.append(f"{path.relative_to(ROOT)}: internal implementation term")
            for pattern in secret_patterns:
                if re.search(pattern, text):
                    failures.append(f"{path.relative_to(ROOT)}: secret/private-path pattern")
        for match in public_ip.findall(text):
            if match != "127.0.0.1":
                failures.append(f"{path.relative_to(ROOT)}: public server IP literal")
    if failures:
        raise SystemExit("disclosure check failed:\n" + "\n".join(sorted(set(failures))))


def verify_scores() -> None:
    expected = json.loads((ROOT / "results" / "summary.json").read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory(prefix="jylus-publication-") as directory:
        temporary = Path(directory)
        actual = evaluate(
            ROOT / "results" / "rankings.jsonl",
            ROOT / "results" / "run-metadata.json",
            temporary / "per-question.jsonl",
            temporary / "weak-cases.jsonl",
            temporary / "summary.json",
        )
        if actual != expected:
            raise SystemExit("reproduced summary differs from checked-in summary")
        if jsonl_rows(temporary / "per-question.jsonl") != jsonl_rows(ROOT / "results" / "per-question.jsonl"):
            raise SystemExit("reproduced per-question results differ")
        if jsonl_rows(temporary / "weak-cases.jsonl") != jsonl_rows(ROOT / "results" / "weak-cases.jsonl"):
            raise SystemExit("reproduced weak-case results differ")
        if render(actual) != (ROOT / "RESULTS.md").read_text(encoding="utf-8"):
            raise SystemExit("generated RESULTS.md differs")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-checksums", action="store_true")
    args = parser.parse_args()
    if args.write_checksums:
        write_checksums()
    verify_disclosure_boundary()
    verify_scores()
    verify_checksums()
    print("publication verification passed")


if __name__ == "__main__":
    main()
