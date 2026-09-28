#!/usr/bin/env python3
"""Reproduce the frozen MultiHop-RAG retrieval comparison.

Ranking commands never read gold evidence. Gold is created in the local data
directory for the separate evaluation command and that directory is ignored by
Git. Credentials are read only from ``JYLUS_API_KEY``.
"""

from __future__ import annotations

import argparse
import ast
import collections
import concurrent.futures
import hashlib
import json
import os
import re
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import requests
from datasets import load_dataset


SCHEMA = "jylus.multihop-rag-comparison.v1"
DATASET = "yixuantt/MultiHopRAG"
DATASET_REVISION = "71ac0d0bd1f951d2d6b70311f7d2ae404e1ffa82"
OFFICIAL_CODE_REVISION = "c1c1287aa60a94acf9c4d20c891c9cd611a0f6e8"
NVIDIA_BLUEPRINT_REVISION = "cc84e6ac93801acb758570e3415ce355b550cf36"
SELECTION_SALT = "multihop-rag-frozen-v1\0"
RETRY_STATUS = {408, 429, 500, 502, 503, 504}


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True, ensure_ascii=False, default=str) + "\n")
    os.replace(temporary, path)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stable_id(prefix: str, value: str) -> str:
    return f"{prefix}-{hashlib.sha256(value.encode('utf-8')).hexdigest()[:40]}"


def corpus_text(row: dict[str, Any]) -> str:
    metadata = "\n".join(
        f"{key}: {row.get(key)}"
        for key in ("title", "source", "author", "published_at", "category")
        if row.get(key)
    )
    return metadata + "\n\n" + str(row.get("body") or "")


def prepare(output: Path, sample_size: int) -> dict[str, Any]:
    queries = load_dataset(DATASET, "MultiHopRAG", revision=DATASET_REVISION, split="train")
    articles = load_dataset(DATASET, "corpus", revision=DATASET_REVISION, split="train")
    if sample_size <= 0 or sample_size > len(queries):
        raise ValueError(f"sample-size must be between 1 and {len(queries)}")

    corpus: list[dict[str, Any]] = []
    url_to_id: dict[str, str] = {}
    for article in articles:
        row = dict(article)
        url = str(row["url"])
        if url in url_to_id:
            raise ValueError(f"duplicate corpus URL: {url}")
        document_id = stable_id("mhragdoc", url)
        url_to_id[url] = document_id
        corpus.append({"id": document_id, **row})

    selected = sorted(
        enumerate(queries),
        key=lambda pair: hashlib.sha256((SELECTION_SALT + str(pair[1]["query"])).encode("utf-8")).digest(),
    )[:sample_size]
    runtime_queries: list[dict[str, Any]] = []
    gold: dict[str, Any] = {}
    for dataset_index, query in selected:
        question_id = f"mhragq-{dataset_index:04d}"
        gold_ids = [url_to_id[str(item["url"])] for item in query["evidence_list"]]
        runtime_queries.append({
            "id": question_id,
            "dataset_index": dataset_index,
            "text": str(query["query"]),
            "question_type": str(query["question_type"]),
        })
        gold[question_id] = {
            "gold_ids": list(dict.fromkeys(gold_ids)),
            "question_type": str(query["question_type"]),
        }

    output.mkdir(parents=True, exist_ok=True)
    write_jsonl(output / "corpus.jsonl", corpus)
    write_jsonl(output / "queries.jsonl", runtime_queries)
    atomic_json(output / "evaluator-gold.json", gold)
    manifest = {
        "schema": SCHEMA,
        "dataset": DATASET,
        "dataset_revision": DATASET_REVISION,
        "official_code_revision": OFFICIAL_CODE_REVISION,
        "corpus_documents": len(corpus),
        "dataset_questions": len(queries),
        "sample_questions": len(runtime_queries),
        "sample_selection": "lowest SHA-256(multihop-rag-frozen-v1\\0 + question text)",
        "runtime_inputs_exclude_gold": True,
        "question_type_counts": dict(collections.Counter(row["question_type"] for row in runtime_queries)),
        "evidence_count_distribution": dict(collections.Counter(len(gold[row["id"]]["gold_ids"]) for row in runtime_queries)),
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    atomic_json(output / "input-manifest.json", manifest)
    return manifest


class Ollama:
    def __init__(self, url: str, model: str, embedding_model: str) -> None:
        self.url = url.rstrip("/")
        self.model = model
        self.embedding_model = embedding_model
        self.session = requests.Session()

    def embed(self, texts: list[str]) -> np.ndarray:
        response = self.session.post(
            self.url + "/api/embed",
            json={"model": self.embedding_model, "input": texts, "truncate": True, "keep_alive": "30m"},
            timeout=900,
        )
        response.raise_for_status()
        matrix = np.asarray(response.json()["embeddings"], dtype=np.float32)
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        return matrix / np.maximum(norms, 1e-12)

    def chat_json(self, system: str, user: str, max_tokens: int = 900) -> tuple[dict[str, Any], dict[str, int]]:
        response = self.session.post(
            self.url + "/api/chat",
            json={
                "model": self.model,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                "stream": False,
                "think": False,
                "keep_alive": "30m",
                "format": "json",
                "options": {"temperature": 0, "seed": 42, "num_predict": max_tokens, "num_ctx": 16384},
            },
            timeout=900,
        )
        response.raise_for_status()
        body = response.json()
        raw = str((body.get("message") or {}).get("content") or "").strip()
        try:
            parsed = json.loads(re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.IGNORECASE))
        except json.JSONDecodeError:
            parsed = {}
        usage = {
            "prompt_tokens": int(body.get("prompt_eval_count") or 0),
            "completion_tokens": int(body.get("eval_count") or 0),
        }
        usage["total_tokens"] = usage["prompt_tokens"] + usage["completion_tokens"]
        return parsed if isinstance(parsed, dict) else {}, usage


def embed(data_dir: Path, cache_dir: Path, config: dict[str, Any], batch_size: int) -> dict[str, Any]:
    corpus = read_jsonl(data_dir / "corpus.jsonl")
    queries = read_jsonl(data_dir / "queries.jsonl")
    cfg = config["ollama"]
    ollama = Ollama(str(cfg["url"]), str(cfg["model"]), str(cfg["embedding_model"]))
    cache_dir.mkdir(parents=True, exist_ok=True)
    batches = cache_dir / "embedding-batches"
    batches.mkdir(exist_ok=True)

    def run_batches(kind: str, texts: list[str]) -> np.ndarray:
        matrices: list[np.ndarray] = []
        for start in range(0, len(texts), batch_size):
            stop = min(len(texts), start + batch_size)
            path = batches / f"{kind}-{start:06d}.npy"
            binding_path = batches / f"{kind}-{start:06d}.sha256"
            binding = hashlib.sha256(canonical({"model": ollama.embedding_model, "texts": texts[start:stop]})).hexdigest()
            if path.exists() and binding_path.exists() and binding_path.read_text().strip() == binding:
                matrix = np.load(path)
            else:
                matrix = ollama.embed(texts[start:stop])
                np.save(path, matrix)
                binding_path.write_text(binding + "\n", encoding="utf-8")
            matrices.append(matrix)
            print(json.dumps({"phase": f"embed_{kind}", "complete": stop, "total": len(texts)}), flush=True)
        return np.concatenate(matrices, axis=0)

    started = time.perf_counter()
    limit = int(config["agentic"]["corpus_embedding_character_limit"])
    corpus_matrix = run_batches("corpus", [corpus_text(row)[:limit] for row in corpus])
    query_matrix = run_batches("queries", [str(row["text"]) for row in queries])
    np.save(cache_dir / "corpus-embeddings.npy", corpus_matrix)
    np.save(cache_dir / "query-embeddings.npy", query_matrix)
    manifest = {
        "schema": SCHEMA,
        "embedding_model": ollama.embedding_model,
        "dimensions": int(corpus_matrix.shape[1]),
        "corpus_documents": len(corpus),
        "queries": len(queries),
        "corpus_embedding_character_limit": limit,
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "corpus_sha256": sha256_file(data_dir / "corpus.jsonl"),
        "queries_sha256": sha256_file(data_dir / "queries.jsonl"),
    }
    atomic_json(cache_dir / "embedding-manifest.json", manifest)
    return manifest


def load_nvidia_prompts(path: Path) -> dict[str, str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    wanted = {"PLANNER_SYSTEM_PROMPT_TEMPLATE", "PLANNER_USER_PROMPT"}
    values: dict[str, str] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            if node.targets[0].id in wanted and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                values[node.targets[0].id] = node.value.value
    if set(values) != wanted:
        raise ValueError(f"NVIDIA prompt source missing {sorted(wanted - set(values))}")
    return values


def render(template: str, values: dict[str, str]) -> str:
    open_mark, close_mark = "\x00OPEN\x00", "\x00CLOSE\x00"
    text = template.replace("{{", open_mark).replace("}}", close_mark)
    for key, value in values.items():
        text = text.replace("{" + key + "}", value)
    return text.replace(open_mark, "{").replace(close_mark, "}")


def rrf(rankings: list[list[str]], k: int) -> list[str]:
    scores: dict[str, float] = collections.defaultdict(float)
    best: dict[str, tuple[int, int]] = {}
    for lane, ranking in enumerate(rankings):
        for rank, document_id in enumerate(ranking, 1):
            scores[document_id] += 1.0 / (k + rank)
            marker = (rank, lane)
            if document_id not in best or marker < best[document_id]:
                best[document_id] = marker
    return sorted(scores, key=lambda document_id: (-scores[document_id], best[document_id], document_id))


class DenseCorpusRetriever:
    def __init__(self, data_dir: Path, cache_dir: Path, config: dict[str, Any]) -> None:
        self.corpus = read_jsonl(data_dir / "corpus.jsonl")
        queries = read_jsonl(data_dir / "queries.jsonl")
        self.by_id = {row["id"]: row for row in self.corpus}
        self.query_index = {row["id"]: index for index, row in enumerate(queries)}
        self.corpus_matrix = np.load(cache_dir / "corpus-embeddings.npy", mmap_mode="r")
        self.query_matrix = np.load(cache_dir / "query-embeddings.npy", mmap_mode="r")
        cfg = config["ollama"]
        self.ollama = Ollama(str(cfg["url"]), str(cfg["model"]), str(cfg["embedding_model"]))

    def dense(self, query: str, top_k: int, query_id: str | None = None) -> list[dict[str, Any]]:
        if query_id in self.query_index:
            vector = np.asarray(self.query_matrix[self.query_index[query_id]], dtype=np.float32)
        else:
            vector = self.ollama.embed([query])[0]
        scores = np.asarray(self.corpus_matrix) @ vector
        order = np.argsort(-scores, kind="stable")[:top_k]
        return [{"id": self.corpus[int(index)]["id"], "score": float(scores[int(index)])} for index in order]

    def document_text(self, document_id: str) -> str:
        return corpus_text(self.by_id[document_id])


def run_agentic(data_dir: Path, cache_dir: Path, run_dir: Path, config: dict[str, Any], workers: int) -> dict[str, Any]:
    queries = read_jsonl(data_dir / "queries.jsonl")
    prompt_source = Path(config["nvidia"]["prompt_source"])
    prompts = load_nvidia_prompts(prompt_source)
    cfg = config["agentic"]
    max_tasks = int(cfg["max_plan_tasks"])
    initial_top_k = int(cfg["initial_top_k"])
    lane_top_k = int(cfg["lane_top_k"])
    output_top_k = int(cfg["output_top_k"])
    context_budget = int(cfg["planner_context_characters"])
    rrf_k = int(cfg["rrf_k"])
    checkpoint_dir = run_dir / "checkpoints" / "nvidia_agentic_rag"
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    binding_prefix = {
        "schema": SCHEMA,
        "arm": "nvidia_agentic_rag",
        "protocol": "nvidia-blueprint-planner-dense-rrf",
        "nvidia_blueprint_revision": NVIDIA_BLUEPRINT_REVISION,
        "model": config["ollama"]["model"],
        "embedding_model": config["ollama"]["embedding_model"],
        "max_tasks": max_tasks,
        "corpus_sha256": sha256_file(data_dir / "corpus.jsonl"),
        "queries_sha256": sha256_file(data_dir / "queries.jsonl"),
    }
    local = threading.local()

    def retriever() -> DenseCorpusRetriever:
        value = getattr(local, "value", None)
        if value is None:
            value = DenseCorpusRetriever(data_dir, cache_dir, config)
            local.value = value
        return value

    def one(query: dict[str, Any]) -> dict[str, Any]:
        engine = retriever()
        checkpoint = checkpoint_dir / f"{query['id']}.json"
        binding = hashlib.sha256(canonical({**binding_prefix, "query": query})).hexdigest()
        if checkpoint.exists():
            prior = json.loads(checkpoint.read_text(encoding="utf-8"))
            if prior.get("binding") != binding:
                raise RuntimeError(f"checkpoint binding changed: {checkpoint}")
            return prior
        started = time.perf_counter()
        try:
            question = str(query["text"])
            initial = engine.dense(question, initial_top_k, query_id=str(query["id"]))
            blocks: list[str] = []
            used = 0
            for row in initial:
                block = f"[SOURCE_ID: {row['id']}]\n{engine.document_text(str(row['id']))}"
                if blocks and used + len(block) > context_budget:
                    break
                blocks.append(block)
                used += len(block)
            system = prompts["PLANNER_SYSTEM_PROMPT_TEMPLATE"].replace("{max_plan_tasks}", str(max_tasks))
            user = render(prompts["PLANNER_USER_PROMPT"], {"query": question, "scope_section": "", "initial_context": "\n\n".join(blocks)})
            plan, usage = engine.ollama.chat_json(system, user)
            question_key = " ".join(question.split()).casefold()
            subqueries: list[str] = []
            for task in plan.get("tasks") or []:
                if isinstance(task, dict):
                    value = str(task.get("query") or "").strip()
                    key = " ".join(value.split()).casefold()
                    if value and key != question_key and key not in {" ".join(item.split()).casefold() for item in subqueries}:
                        subqueries.append(value)
            resolved = str(plan.get("resolved_query") or "").strip()
            resolved_key = " ".join(resolved.split()).casefold()
            if resolved and resolved_key != question_key and resolved_key not in {" ".join(item.split()).casefold() for item in subqueries}:
                subqueries.insert(0, resolved)
            subqueries = subqueries[:max_tasks]
            rankings = [[str(row["id"]) for row in initial]]
            rankings.extend([[str(row["id"]) for row in engine.dense(subquery, lane_top_k)] for subquery in subqueries])
            record = {
                "binding": binding,
                "question_id": query["id"],
                "selected": rrf(rankings, rrf_k)[:output_top_k],
                "arm": "nvidia_agentic_rag",
                "wall_ms": round((time.perf_counter() - started) * 1000, 3),
                "trace": {"subqueries": subqueries, "retrieval_lanes": len(rankings), "usage": usage},
                "failure": None,
            }
        except Exception as error:
            record = {"binding": binding, "question_id": query["id"], "selected": [], "arm": "nvidia_agentic_rag", "wall_ms": round((time.perf_counter() - started) * 1000, 3), "trace": {"subqueries": [], "retrieval_lanes": 0, "usage": {}}, "failure": {"type": type(error).__name__, "message": str(error)[:500]}}
        atomic_json(checkpoint, record)
        return record

    started = time.perf_counter()
    records: list[dict[str, Any]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        for offset, record in enumerate(pool.map(one, queries), 1):
            records.append(record)
            if offset == 1 or offset % 10 == 0 or offset == len(queries):
                print(json.dumps({"phase": "agentic", "complete": offset, "total": len(queries)}), flush=True)
    write_jsonl(run_dir / "nvidia_agentic_rag-results.jsonl", records)
    manifest = {
        **binding_prefix,
        "completed": len(records),
        "workers": workers,
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "results_sha256": sha256_file(run_dir / "nvidia_agentic_rag-results.jsonl"),
    }
    atomic_json(run_dir / "nvidia_agentic_rag-run.json", manifest)
    return manifest


def api_session(config: dict[str, Any]) -> requests.Session:
    key = os.environ.get(str(config["jylus"].get("api_key_env") or "JYLUS_API_KEY"), "").strip()
    if len(key) < 24 or any(char.isspace() for char in key):
        raise ValueError("set JYLUS_API_KEY to a valid Jylus API key")
    session = requests.Session()
    session.headers.update({"accept": "application/json", "authorization": "Bearer " + key, "user-agent": "jylus-public-multihop-rag/1"})
    return session


def request_json(session: requests.Session, api_root: str, method: str, path: str, *, payload: dict[str, Any] | None = None, idempotency_key: str | None = None, timeout: float = 180.0) -> tuple[dict[str, Any], requests.Response, float]:
    headers = {"content-type": "application/json"}
    if idempotency_key:
        headers["idempotency-key"] = idempotency_key
    if path.endswith("/analyze"):
        headers["x-jylus-cache-bypass"] = "receipt-verification"
    started = time.perf_counter()
    response = None
    for attempt in range(7):
        response = session.request(method, api_root.rstrip("/") + path, data=canonical(payload) if payload is not None else None, headers=headers, timeout=timeout)
        if response.status_code not in RETRY_STATUS:
            break
        time.sleep(min(12.0, 0.5 * 2**attempt))
    assert response is not None
    body = response.json()
    if not response.ok:
        raise RuntimeError(f"{method} {path} returned HTTP {response.status_code}: {json.dumps(body)[:800]}")
    return body, response, time.perf_counter() - started


def ensure_scope(run_dir: Path) -> dict[str, Any]:
    path = run_dir / "live-scope.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    nonce = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    scope = {
        "isolation": "dedicated_namespace_in_authenticated_account",
        "namespace": f"benchmark-multihop-rag-{nonce.casefold()}",
        "occurred_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    atomic_json(path, scope)
    return scope


def ingest_jylus(data_dir: Path, run_dir: Path, config: dict[str, Any]) -> dict[str, Any]:
    corpus = read_jsonl(data_dir / "corpus.jsonl")
    scope = ensure_scope(run_dir)
    session = api_session(config)
    api_root = str(config["jylus"]["base_url"])
    events = [{
        "id": row["id"],
        "type": "benchmark.multihop_rag.article",
        "occurred_at": scope["occurred_at"],
        "site_id": "JYLUS_PUBLIC_MULTIHOP_RAG_BENCHMARK",
        "source_id": row["id"],
        "data": {
            "document": {"id": row["id"], "content": corpus_text(row), "title": row.get("title"), "url": row.get("url")},
            "benchmark": {"name": "MultiHop-RAG", "namespace": scope["namespace"]},
            "metadata": {key: row.get(key) for key in ("category", "author", "published_at", "source")},
        },
    } for row in corpus]
    batches: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    current_size = 0
    for event in events:
        event_size = len(canonical(event))
        if current and (len(current) >= 40 or current_size + event_size > 350_000):
            batches.append(current)
            current, current_size = [], 0
        current.append(event)
        current_size += event_size
    if current:
        batches.append(current)

    checkpoint_dir = run_dir / "ingest-checkpoints"
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    for index, batch in enumerate(batches):
        checkpoint = checkpoint_dir / f"batch-{index:04d}.json"
        digest = hashlib.sha256(canonical(batch)).hexdigest()
        if checkpoint.exists():
            prior = json.loads(checkpoint.read_text(encoding="utf-8"))
            if prior.get("digest") == digest and prior.get("verified") is True:
                continue
        payload = {
            "stream": "benchmark-multihop-rag-public",
            "namespace": scope["namespace"],
            "site_id": "JYLUS_PUBLIC_MULTIHOP_RAG_BENCHMARK",
            "source_id": "multihop-rag-corpus",
            "events": batch,
        }
        body, _, _ = request_json(session, api_root, "POST", "/api/v1/events", payload=payload, idempotency_key=f"mhrag-{index:04d}-{digest[:20]}")
        verify_path = str(body.get("verify_url") or "")
        deadline = time.monotonic() + 240
        verified: dict[str, Any] | None = None
        while time.monotonic() < deadline:
            verified, _, _ = request_json(session, api_root, "GET", verify_path, timeout=60)
            if verified.get("status") == "verified":
                break
            if verified.get("status") == "conflict":
                raise RuntimeError(f"ingest conflict in batch {index}")
            time.sleep(0.5)
        integrity = (verified or {}).get("integrity") or {}
        if not (verified and verified.get("all_data_available") is True and int(integrity.get("queryable_events") or 0) == len(batch) and int(integrity.get("missing_events") or 0) == 0):
            raise RuntimeError(f"ingest batch {index} did not verify")
        atomic_json(checkpoint, {"digest": digest, "events": len(batch), "verified": True, "receipt_id": body.get("receipt_id")})
        print(json.dumps({"phase": "jylus_ingest", "complete": index + 1, "total": len(batches)}), flush=True)
    report = {"schema": SCHEMA, "events": len(events), "batches": len(batches), "elapsed_seconds": round(time.perf_counter() - started, 3), "all_receipts_verified": True}
    atomic_json(run_dir / "jylus-ingest-report.json", report)
    return report


def result_id(row: dict[str, Any], allowed: set[str]) -> str:
    document = (row.get("payload") or {}).get("document") or {}
    for value in (document.get("id"), row.get("source_id"), row.get("id")):
        text = str(value or "")
        for prefix in ("evt-v3-", "evt-"):
            if text.startswith(prefix):
                text = text[len(prefix):]
        text = text.removesuffix("-chunk-0000")
        if text in allowed:
            return text
    return ""


def run_jylus(data_dir: Path, run_dir: Path, config: dict[str, Any], workers: int) -> dict[str, Any]:
    corpus = read_jsonl(data_dir / "corpus.jsonl")
    queries = read_jsonl(data_dir / "queries.jsonl")
    allowed = {row["id"] for row in corpus}
    scope = ensure_scope(run_dir)
    api_root = str(config["jylus"]["base_url"])
    checkpoint_dir = run_dir / "checkpoints" / "jylus"
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    binding_prefix = {
        "schema": SCHEMA,
        "arm": "jylus",
        "protocol": "ordinary-authenticated-public-v1",
        "namespace": scope["namespace"],
        "corpus_sha256": sha256_file(data_dir / "corpus.jsonl"),
        "queries_sha256": sha256_file(data_dir / "queries.jsonl"),
    }

    def one(query: dict[str, Any]) -> dict[str, Any]:
        checkpoint = checkpoint_dir / f"{query['id']}.json"
        binding = hashlib.sha256(canonical({**binding_prefix, "query": query})).hexdigest()
        if checkpoint.exists():
            prior = json.loads(checkpoint.read_text(encoding="utf-8"))
            if prior.get("binding") == binding:
                return prior
        started = time.perf_counter()
        try:
            session = api_session(config)
            payload = {
                "source": "history",
                "where": {"namespace": {"eq": scope["namespace"]}, "timestamp": {"gte": scope["occurred_at"]}},
                "text": str(query["text"])[:500],
                "vector": {"text": str(query["text"])},
                "context": {"mode": "decision", "token_budget": 8000, "max_facts": 10, "max_timeline": 20, "max_contradictions": 12, "include_documents": False},
                "scan_limit": 20000,
                "limit": 10,
            }
            body, response, wall = request_json(session, api_root, "POST", "/api/v1/analyze", payload=payload)
            ranked = sorted(body.get("results") or [], key=lambda item: int(item.get("evidence_rank") or 1_000_000))
            selected: list[str] = []
            for item in ranked:
                value = result_id(item, allowed)
                if value and value not in selected:
                    selected.append(value)
            record = {
                "binding": binding,
                "question_id": query["id"],
                "selected": selected[:10],
                "arm": "jylus",
                "wall_ms": round(wall * 1000, 3),
                "server_ms": float(response.headers.get("X-Jylus-Server-Ms") or 0),
                "complete": body.get("complete"),
                "execution_mode": body.get("execution_mode"),
                "failure": None,
            }
        except Exception as error:
            record = {"binding": binding, "question_id": query["id"], "selected": [], "arm": "jylus", "wall_ms": round((time.perf_counter() - started) * 1000, 3), "server_ms": 0.0, "complete": None, "execution_mode": None, "failure": {"type": type(error).__name__, "message": str(error)[:500]}}
        atomic_json(checkpoint, record)
        return record

    started = time.perf_counter()
    records: list[dict[str, Any]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(2, workers)) as pool:
        futures = [pool.submit(one, query) for query in queries]
        for offset, future in enumerate(concurrent.futures.as_completed(futures), 1):
            records.append(future.result())
            if offset == 1 or offset % 20 == 0 or offset == len(queries):
                print(json.dumps({"phase": "jylus", "complete": offset, "total": len(queries)}), flush=True)
    records.sort(key=lambda row: row["question_id"])
    write_jsonl(run_dir / "jylus-results.jsonl", records)
    manifest = {
        **binding_prefix,
        "completed": len(records),
        "workers": min(2, workers),
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "results_sha256": sha256_file(run_dir / "jylus-results.jsonl"),
    }
    atomic_json(run_dir / "jylus-run.json", manifest)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("config.json"))
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--cache-dir", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare_parser = commands.add_parser("prepare")
    prepare_parser.add_argument("--sample-size", type=int, default=256)
    embed_parser = commands.add_parser("embed")
    embed_parser.add_argument("--batch-size", type=int, default=16)
    agentic_parser = commands.add_parser("run-agentic")
    agentic_parser.add_argument("--workers", type=int, choices=(1, 2), default=1)
    commands.add_parser("ingest-jylus")
    jylus_parser = commands.add_parser("run-jylus")
    jylus_parser.add_argument("--workers", type=int, choices=(1, 2), default=2)
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8")) if args.command != "prepare" else {}
    if args.command == "prepare":
        result = prepare(args.data_dir, args.sample_size)
    elif args.command == "embed":
        result = embed(args.data_dir, args.cache_dir, config, args.batch_size)
    elif args.command == "run-agentic":
        result = run_agentic(args.data_dir, args.cache_dir, args.run_dir, config, args.workers)
    elif args.command == "ingest-jylus":
        result = ingest_jylus(args.data_dir, args.run_dir, config)
    else:
        result = run_jylus(args.data_dir, args.run_dir, config, args.workers)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
