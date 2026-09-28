# Frozen configuration

Machine-readable settings are in [`frozen/configuration.json`](frozen/configuration.json) and [`frozen/software-versions.json`](frozen/software-versions.json).

## Dataset and cohort

- Dataset: `yixuantt/MultiHopRAG`
- Hugging Face revision: `71ac0d0bd1f951d2d6b70311f7d2ae404e1ffa82`
- Upstream code revision: `c1c1287aa60a94acf9c4d20c891c9cd611a0f6e8`
- Corpus: 609 documents
- Full dataset: 2,556 questions
- Frozen subset: 256 questions
- Selection: lowest SHA-256 values of `multihop-rag-frozen-v1\0 + question_text`
- Question types: 95 comparison, 87 inference, 54 temporal, 20 null
- Runtime ranking files contained question text and corpus records, but no gold evidence or answers.

Exact question and document identifiers are published under [`frozen/`](frozen/). Dataset text and labels are downloaded from the licensed upstream dataset.

## Jylus

- Public endpoint: `POST https://api.jylus.ai/api/v1/analyze`
- Build identifier: `6d4aba810ee2962326c04e3bcfd837f26def7f58`
- Scope: dedicated namespace in an existing authenticated account
- Concurrent requests: 2
- Output limit: 10
- Scan limit: 20,000
- Context mode: `decision`
- Token budget: 8,000
- Maximum facts: 10
- Maximum timeline items: 20
- Maximum contradictions: 12
- Included source documents in response: false

Only the public API contract and opaque build identifier are documented. This repository contains no Jylus implementation.

## NVIDIA-style agentic RAG

- Upstream repository: [`NVIDIA-AI-Blueprints/rag`](https://github.com/NVIDIA-AI-Blueprints/rag)
- Revision: `cc84e6ac93801acb758570e3415ce355b550cf36`
- Exact prompt source: [`src/nvidia_rag/rag_server/agentic_rag/prompt.py`](https://github.com/NVIDIA-AI-Blueprints/rag/blob/cc84e6ac93801acb758570e3415ce355b550cf36/src/nvidia_rag/rag_server/agentic_rag/prompt.py)
- Prompt wording changes: none
- Planner: `nemotron-3-nano:4b`, Ollama manifest ID `6cc467f05439`
- Embeddings: `bge-m3:latest`, Ollama manifest ID `790764642607`
- Temperature: 0
- Random seed: 42
- Planner context: 16,384 tokens; maximum output: 900 tokens
- Initial dense retrieval: top 20
- Planned queries: up to 3
- Dense retrieval for every additional lane: top 20
- Fusion: reciprocal rank fusion, `k=60`
- Final output: top 10
- Corpus embedding input: first 8,000 characters of every document using one global rule
- Planner initial-context budget: 18,000 characters
- Concurrent queries: 1

This adaptation did not run NVIDIA NIM, NVIDIA-hosted models, the complete NVIDIA blueprint pipeline, answer synthesis or a verifier. It is therefore described only as “NVIDIA-style agentic RAG.”

## Resource differences

Jylus ran remotely as a live service. The baseline ran locally on the workstation in `software-versions.json`. The systems did not receive equivalent hardware or deployment resources, so latency is reported as descriptive measurements rather than a controlled winner. Quality metrics use the same frozen questions, corpus and evaluator.

