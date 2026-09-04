"""Semantic retrieval for the specification index.

The index is full-text, which finds passages that share words with the query.
Specifications rarely oblige: a section headed "Conventional Reset ... initiates
a Controller Level Reset" is what someone asking about "reset behaviour" wants,
and lexical search reaches it only by luck of shared vocabulary.

Embeddings are computed here rather than in the harness because this is where
the index is built, and because the model is a Python one. They are stored in
the same SQLite file, so an index either carries them or does not — there is no
second artifact to keep in step with the first.

Two entry points: `build`, which fills the table, and `serve`, which answers
one query vector per line so the harness can embed a search without paying for
a model load each time.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import struct
import sys
from pathlib import Path

DEFAULT_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

SCHEMA = """
CREATE TABLE IF NOT EXISTS embeddings (
    node_id TEXT PRIMARY KEY REFERENCES nodes(node_id),
    model TEXT NOT NULL,
    dim INTEGER NOT NULL,
    vector BLOB NOT NULL
);
CREATE TABLE IF NOT EXISTS embedding_builds (
    model TEXT PRIMARY KEY,
    dim INTEGER NOT NULL,
    node_count INTEGER NOT NULL,
    created_at TEXT NOT NULL
);
"""

# Long passages are truncated rather than split: a node is the unit the rest of
# the pipeline cites, so half a node is not a thing anything downstream can name.
MAX_CHARS = 4000


def pack(vector) -> bytes:
    """Little-endian float32, which is what the reader expects."""
    return struct.pack(f"<{len(vector)}f", *(float(value) for value in vector))


def unpack(blob: bytes) -> list[float]:
    return list(struct.unpack(f"<{len(blob) // 4}f", blob))


def _load(model_name: str):
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(model_name)


def _texts(connection: sqlite3.Connection) -> list[tuple[str, str]]:
    """Every node with text worth embedding, titled where it has a title.

    The title is prepended because a heading is often the only place a concept
    is named in the words someone would search for.
    """
    rows = connection.execute(
        "SELECT node_id, title, raw_text FROM nodes WHERE raw_text IS NOT NULL"
    ).fetchall()
    found = []
    for node_id, title, raw_text in rows:
        text = raw_text.strip()
        if not text:
            continue
        if title and title.strip():
            text = f"{title.strip()}\n{text}"
        found.append((node_id, text[:MAX_CHARS]))
    return found


def build(database: Path, model_name: str = DEFAULT_MODEL, batch: int = 64) -> int:
    connection = sqlite3.connect(database)
    try:
        connection.executescript(SCHEMA)
        items = _texts(connection)
        if not items:
            return 0
        model = _load(model_name)
        vectors = model.encode(
            [text for _, text in items],
            batch_size=batch,
            show_progress_bar=False,
            normalize_embeddings=True,
        )
        dim = int(vectors.shape[1])
        connection.executemany(
            "INSERT OR REPLACE INTO embeddings (node_id, model, dim, vector) VALUES (?,?,?,?)",
            [
                (node_id, model_name, dim, pack(vector))
                for (node_id, _), vector in zip(items, vectors)
            ],
        )
        connection.execute(
            "INSERT OR REPLACE INTO embedding_builds (model, dim, node_count, created_at)"
            " VALUES (?,?,?,datetime('now'))",
            (model_name, dim, len(items)),
        )
        connection.commit()
        return len(items)
    finally:
        connection.close()


def serve(model_name: str = DEFAULT_MODEL) -> None:
    """One query per line in, one JSON vector per line out.

    The harness keeps this alive for a run, because loading the model costs far
    more than embedding anything it is subsequently asked about.
    """
    model = _load(model_name)
    print(json.dumps({"ready": True, "model": model_name}), flush=True)
    for line in sys.stdin:
        query = line.rstrip("\n")
        if not query:
            continue
        vector = model.encode([query], normalize_embeddings=True)[0]
        print(json.dumps({"vector": [float(value) for value in vector]}), flush=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="spec2lean-embeddings")
    parser.add_argument("--database", type=Path)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--serve", action="store_true")
    arguments = parser.parse_args(argv)
    if arguments.serve:
        serve(arguments.model)
        return 0
    if not arguments.database:
        parser.error("--database is required unless --serve")
    count = build(arguments.database, arguments.model)
    print(f"embedded {count} node(s) with {arguments.model}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
