# Reproducing the comparison

The scoring and report can be verified without a Jylus account or local model. Re-running both ranking arms requires Jylus API access and Ollama.

## Requirements

- Git and Python 3.12.
- A Jylus account and API key with event-ingestion and analysis access for 609 documents and 256 questions.
- Ollama 0.30.5 for the measured baseline.
- `nemotron-3-nano:4b` and `bge-m3` in Ollama.
- Sufficient local memory for both Ollama models and a 609-document embedding matrix.

The measured local workstation used Windows 11, an AMD Ryzen 9 9950X and an NVIDIA GeForce RTX 5060 Ti. Other hardware can reproduce ranking logic but will not reproduce latency. Jylus is a hosted service; the exact measured service build is proprietary and cannot be downloaded from this repository. A later public API build can return different rankings.

## Clean installation

PowerShell:

```powershell
git clone https://github.com/jylusAus/jylus.git
cd jylus/benchmarks/multihop-rag

python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

git clone https://github.com/NVIDIA-AI-Blueprints/rag.git vendor/rag
git -C vendor/rag checkout cc84e6ac93801acb758570e3415ce355b550cf36

ollama pull nemotron-3-nano:4b
ollama pull bge-m3
Copy-Item config.example.json config.json
```

Linux or macOS uses `source .venv/bin/activate` and `cp config.example.json config.json`.

Confirm that `config.json` points to:

```text
vendor/rag/src/nvidia_rag/rag_server/agentic_rag/prompt.py
```

## Download and freeze the data

```powershell
python benchmark.py --data-dir data/frozen-256 --cache-dir cache/frozen-256 --run-dir runs/frozen-256 prepare --sample-size 256
```

This downloads `yixuantt/MultiHopRAG` at revision `71ac0d0bd1f951d2d6b70311f7d2ae404e1ffa82`, regenerates the exact SHA-256-selected cohort and writes corpus, questions and local evaluator gold under the ignored `data/` directory.

## Build the baseline embeddings

Start Ollama, then run:

```powershell
python benchmark.py --config config.json --data-dir data/frozen-256 --cache-dir cache/frozen-256 --run-dir runs/frozen-256 embed --batch-size 16
```

## Ingest and query Jylus

Set the key only in the current process. Do not place it in `config.json`.

```powershell
$env:JYLUS_API_KEY = "YOUR_KEY"
python benchmark.py --config config.json --data-dir data/frozen-256 --cache-dir cache/frozen-256 --run-dir runs/frozen-256 ingest-jylus
python benchmark.py --config config.json --data-dir data/frozen-256 --cache-dir cache/frozen-256 --run-dir runs/frozen-256 run-jylus --workers 2
```

The ingestion command creates a timestamped dedicated namespace and verifies every batch receipt. The measured run used the public API and an existing authenticated account. Keep the two-worker limit for parity with the recorded run.

## Run the NVIDIA-style agentic baseline

```powershell
python benchmark.py --config config.json --data-dir data/frozen-256 --cache-dir cache/frozen-256 --run-dir runs/frozen-256 run-agentic --workers 1
```

One worker is the frozen measured setting. The script records failures instead of silently omitting questions; any exception stops the batch and leaves bound checkpoints for diagnosis and resume.

## Assemble and score a new run

Replace `CURRENT_PUBLIC_BUILD_ID` with the build identifier reported for the public service used by your run.

```powershell
python assemble_results.py `
  --data-dir data/frozen-256 `
  --run-dir runs/frozen-256 `
  --output-dir runs/frozen-256/public `
  --jylus-build-id CURRENT_PUBLIC_BUILD_ID `
  --client-location "your location"

python evaluate.py `
  --rankings runs/frozen-256/public/rankings.jsonl `
  --metadata runs/frozen-256/public/run-metadata.json `
  --per-question runs/frozen-256/public/per-question.jsonl `
  --weak-cases runs/frozen-256/public/weak-cases.jsonl `
  --summary runs/frozen-256/public/summary.json

python generate_report.py --summary runs/frozen-256/public/summary.json --output runs/frozen-256/public/RESULTS.md
```

The checked-in run can be re-scored directly:

```powershell
python evaluate.py `
  --rankings results/rankings.jsonl `
  --metadata results/run-metadata.json `
  --per-question results/per-question.reproduced.jsonl `
  --weak-cases results/weak-cases.reproduced.jsonl `
  --summary results/summary.reproduced.json
```

`verify_publication.py` performs that operation in a temporary directory, compares the reproduced metrics with the checked-in summary, verifies file hashes and scans the public tree for credentials, private paths, server addresses and internal implementation terms.
