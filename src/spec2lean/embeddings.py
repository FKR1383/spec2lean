"""Optional cosine retrieval over current Phase-1 node identities.

Ported from supervisor semantic-index (26b43f2). Titles precede node text;
normalized float32 vectors live beside the lexical index in SQLite. The MCP
worker caches the model, so queries do not launch an embedding process per call.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import sqlite3
import struct
from functools import lru_cache
from contextlib import closing, contextmanager
from pathlib import Path
from typing import Any

from .database import connect, utc_now

DEFAULT_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
MAX_CHARS = 4000
SCHEMA = """
CREATE TABLE IF NOT EXISTS embeddings (
    node_id TEXT PRIMARY KEY REFERENCES nodes(node_id),
    vector BLOB NOT NULL
);
CREATE TABLE IF NOT EXISTS embedding_builds (
    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
    model TEXT NOT NULL,
    revision TEXT,
    dim INTEGER NOT NULL,
    node_count INTEGER NOT NULL,
    source_digest TEXT NOT NULL,
    text_digest TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


def index_mode() -> str:
    mode = os.environ.get("SPEC2LEAN_INDEX_MODE", "lexical")
    if mode not in {"lexical", "semantic"}:
        raise ValueError("index mode must be lexical or semantic")
    return mode


@contextmanager
def retrieval_selection(mode: str | None):
    previous = os.environ.get("SPEC2LEAN_INDEX_MODE")
    try:
        if mode is not None:
            os.environ["SPEC2LEAN_INDEX_MODE"] = mode
        index_mode()
        yield
    finally:
        if previous is None:
            os.environ.pop("SPEC2LEAN_INDEX_MODE", None)
        else:
            os.environ["SPEC2LEAN_INDEX_MODE"] = previous


def pack(vector) -> bytes:
    return struct.pack(f"<{len(vector)}f", *vector)


def unpack(blob: bytes) -> list[float]:
    if not blob or len(blob) % 4:
        raise ValueError("invalid semantic vector storage")
    return list(struct.unpack(f"<{len(blob) // 4}f", blob))


def _normalize(vector) -> list[float]:
    values = [float(v) for v in vector]
    if not values or not all(math.isfinite(v) for v in values):
        raise ValueError("embedding vector must be finite and nonempty")
    norm = math.sqrt(sum(v * v for v in values))
    if not math.isfinite(norm) or norm == 0:
        raise ValueError("embedding vector must have a finite nonzero norm")
    return [v / norm for v in values]


@lru_cache(maxsize=2)
def _load(model_name: str, revision: str | None = None):
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise RuntimeError("semantic indexing requires pip install -e '.[semantic]'") from exc
    # CPU is deliberate: predictable memory use for small specification indexes.
    try:
        return SentenceTransformer(model_name, revision=revision, device="cpu")
    except OSError as exc:
        raise RuntimeError(f"could not load semantic embedding model {model_name}: {exc}") from exc


def _texts(connection: sqlite3.Connection) -> list[tuple[str, str]]:
    items = []
    for row in connection.execute("SELECT node_id, title, raw_text FROM nodes ORDER BY node_id"):
        text = (row["raw_text"] or "").strip()
        if text:
            if row["title"]:
                text = f"{row['title'].strip()}\n{text}"
            items.append((row["node_id"], text[:MAX_CHARS]))
    return items


def _digests(connection: sqlite3.Connection) -> tuple[str, str]:
    row = connection.execute(
        "SELECT semantic_digest FROM builds WHERE status='COMPLETE' ORDER BY created_at DESC LIMIT 1"
    ).fetchone()
    if not row or not row[0]:
        raise ValueError("semantic indexing requires a complete Phase-1 database")
    text_digest = hashlib.sha256(json.dumps(_texts(connection), ensure_ascii=False).encode()).hexdigest()
    return row[0], text_digest


def metadata(connection: sqlite3.Connection) -> dict[str, Any]:
    try:
        row = connection.execute("SELECT * FROM embedding_builds WHERE singleton=1").fetchone()
    except sqlite3.OperationalError as exc:
        raise ValueError("semantic index is missing; run spec2lean index embed") from exc
    if row is None:
        raise ValueError("semantic index is missing; run spec2lean index embed")
    data = dict(row)
    if (data["source_digest"], data["text_digest"]) != _digests(connection):
        raise ValueError("semantic index is stale; run spec2lean index embed")
    rows = connection.execute("SELECT node_id, vector FROM embeddings ORDER BY node_id").fetchall()
    if [r["node_id"] for r in rows] != [node for node, _ in _texts(connection)] or len(rows) != data["node_count"]:
        raise ValueError("semantic index is incomplete; run spec2lean index embed")
    for row in rows:
        values = unpack(row["vector"])
        if len(values) != data["dim"] or not all(math.isfinite(v) for v in values):
            raise ValueError("semantic index has invalid vector dimensions or values")
        if not math.isclose(sum(v * v for v in values), 1.0, abs_tol=1e-5):
            raise ValueError("semantic index has a non-normalized vector")
    return data


def build(database: Path, model_name: str = DEFAULT_MODEL, *, revision: str | None = None, batch: int = 64) -> dict[str, Any]:
    if not database.is_file():
        raise FileNotFoundError(database)
    if batch < 1:
        raise ValueError("embedding batch must be positive")
    with closing(connect(database, read_only=True)) as connection:
        digests = _digests(connection)
        items = _texts(connection)
    if not items:
        raise ValueError("semantic index requires at least one nonempty node")
    model = _load(model_name, revision)
    vectors = list(model.encode([text for _, text in items], batch_size=batch,
                               show_progress_bar=False, normalize_embeddings=True))
    if len(vectors) != len(items):
        raise ValueError("embedder returned the wrong number of vectors")
    vectors = [_normalize(vector) for vector in vectors]
    dim = len(vectors[0])
    if any(len(vector) != dim for vector in vectors):
        raise ValueError("embedder returned inconsistent vector dimensions")
    # Capture the immutable HF revision, when supplied by SentenceTransformer.
    if revision is None and hasattr(model, "_first_module"):
        auto_model = getattr(model._first_module(), "auto_model", None)
        revision = getattr(getattr(auto_model, "config", None), "_commit_hash", None)
    with closing(connect(database)) as connection, connection:
        # DDL and replacement are one transaction; failed rebuilds retain the old index.
        connection.execute("BEGIN IMMEDIATE")
        for statement in SCHEMA.split(';'):
            if statement.strip():
                connection.execute(statement)
        if digests != _digests(connection):
            raise ValueError("Phase-1 database changed during embedding; retry the build")
        connection.execute("DELETE FROM embeddings")
        connection.execute("DELETE FROM embedding_builds")
        connection.executemany("INSERT INTO embeddings VALUES (?, ?)", [
            (node, pack(vector)) for (node, _), vector in zip(items, vectors, strict=True)
        ])
        connection.execute("INSERT INTO embedding_builds VALUES (1, ?, ?, ?, ?, ?, ?, ?)",
                           (model_name, revision, dim, len(items), *digests, utc_now()))
        result = metadata(connection)
    return result


def ensure(database: Path, *, dry_run: bool = False) -> dict[str, Any]:
    with closing(connect(database, read_only=True)) as connection:
        try:
            return {**metadata(connection), "disposition": "REUSED"}
        except ValueError:
            if dry_run:
                return {"disposition": "WOULD_BUILD"}
    return {**build(database), "disposition": "BUILT"}


def search(connection: sqlite3.Connection, query: str, *, limit: int = 20,
           source_type: str | None = None, node_type: str | None = None) -> list[dict[str, Any]]:
    if not query.strip() or limit < 1:
        raise ValueError("search query must be nonempty and limit positive")
    info = metadata(connection)
    model = _load(info["model"], info["revision"])
    query_vector = _normalize(model.encode([query], normalize_embeddings=True)[0])
    if len(query_vector) != info["dim"]:
        raise ValueError("query embedding dimension differs from the stored model")
    rows = connection.execute("""SELECT n.*, d.source_type, e.vector FROM embeddings e
        JOIN nodes n USING(node_id) JOIN documents d USING(document_id)
        WHERE (? IS NULL OR d.source_type=?) AND (? IS NULL OR n.node_type=?)""",
        (source_type, source_type, node_type, node_type)).fetchall()
    ranked = []
    for row in rows:
        vector = unpack(row["vector"])
        score = sum(a * b for a, b in zip(query_vector, vector, strict=True))
        item = dict(row)
        del item["vector"]
        item.update(rank=-score, similarity=score, snippet=item["raw_text"][:500])
        ranked.append(item)
    return sorted(ranked, key=lambda item: (item["rank"], item["node_id"]))[:limit]
