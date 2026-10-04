"""Convert the pinned BrowseComp-Plus parquet corpus to verified gzip JSONL."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path

import pyarrow.parquet as parquet


parser=argparse.ArgumentParser()
parser.add_argument("--directory", type=Path, required=True)
ROOT=parser.parse_args().directory
CORPUS = ROOT / "corpus"
OUTPUT = ROOT / "browsecomp-plus-corpus.jsonl.gz"
REPORT = ROOT / "corpus-preparation.json"
EXPECTED_ROWS = 100_195


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    source = json.loads((ROOT / "corpus-manifest.json").read_text(encoding="utf-8"))
    files = [CORPUS / Path(item["path"]).name for item in source["files"]]
    if len(files) != 7 or any(not path.is_file() for path in files):
        raise RuntimeError("the seven pinned parquet shards are required")

    temporary = OUTPUT.with_suffix(OUTPUT.suffix + ".tmp")
    rows = 0
    text_bytes = 0
    max_text_bytes = 0
    seen: set[str] = set()
    with gzip.open(temporary, "wt", encoding="utf-8", newline="\n", compresslevel=6) as output:
        for filename in files:
            source_sha = next(item["sha256"] for item in source["files"] if Path(item["path"]).name == filename.name)
            if file_sha256(filename) != source_sha:
                raise RuntimeError(f"source checksum mismatch for {filename.name}")
            parquet_file = parquet.ParquetFile(filename)
            for batch in parquet_file.iter_batches(batch_size=256, columns=["docid", "text", "url"]):
                for row in batch.to_pylist():
                    docid = str(row.get("docid") or "")
                    text = str(row.get("text") or "")
                    url = str(row.get("url") or "")
                    if not docid or not text or docid in seen:
                        raise RuntimeError("invalid or duplicate BrowseComp-Plus corpus row")
                    seen.add(docid)
                    size = len(text.encode("utf-8"))
                    text_bytes += size
                    max_text_bytes = max(max_text_bytes, size)
                    output.write(json.dumps({"docid": docid, "text": text, "url": url}, ensure_ascii=False, separators=(",", ":")))
                    output.write("\n")
                    rows += 1
    if rows != EXPECTED_ROWS:
        raise RuntimeError(f"expected {EXPECTED_ROWS} corpus rows, found {rows}")
    temporary.replace(OUTPUT)
    report = {
        "schema": "jylus.browsecomp-plus-corpus-preparation.v1",
        "dataset": source["dataset"],
        "dataset_revision": source["revision"],
        "rows": rows,
        "unique_docids": len(seen),
        "text_bytes": text_bytes,
        "max_text_bytes": max_text_bytes,
        "output_bytes": OUTPUT.stat().st_size,
        "output_sha256": file_sha256(OUTPUT),
    }
    REPORT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
