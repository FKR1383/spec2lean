from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Any

from ..constants import PLAN_SCHEMA_VERSION
from ..database import connect
from .graph import derive_graph
from .validation import NODE_ID_PATTERN, normalize_candidate, validate_plan


SESSION_SCHEMA = """
PRAGMA journal_mode = WAL;
CREATE TABLE IF NOT EXISTS session (
    singleton INTEGER PRIMARY KEY CHECK(singleton = 1),
    submit_attempts INTEGER NOT NULL DEFAULT 0,
    accepted INTEGER NOT NULL DEFAULT 0,
    last_diagnostics_json TEXT NOT NULL DEFAULT '[]'
);
INSERT OR IGNORE INTO session(singleton) VALUES (1);
CREATE TABLE IF NOT EXISTS observed_nodes (
    node_id TEXT PRIMARY KEY
);
"""


def initialize_session_state(path: str | Path) -> None:
    target = Path(path).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(target) as connection:
        connection.executescript(SESSION_SCHEMA)


def _collect_node_ids(value: Any, result: set[str]) -> None:
    if isinstance(value, str):
        if NODE_ID_PATTERN.fullmatch(value):
            result.add(value)
    elif isinstance(value, dict):
        for child in value.values():
            _collect_node_ids(child, result)
    elif isinstance(value, list):
        for child in value:
            _collect_node_ids(child, result)


def record_observed_nodes(path: str | Path, tool_result: Any) -> int:
    node_ids: set[str] = set()
    _collect_node_ids(tool_result, node_ids)
    initialize_session_state(path)
    with sqlite3.connect(Path(path).resolve(), timeout=30) as connection:
        connection.executemany(
            "INSERT OR IGNORE INTO observed_nodes(node_id) VALUES (?)",
            [(node_id,) for node_id in sorted(node_ids)],
        )
    return len(node_ids)


def _observed_nodes(path: str | Path) -> set[str]:
    initialize_session_state(path)
    with sqlite3.connect(Path(path).resolve()) as connection:
        return {row[0] for row in connection.execute("SELECT node_id FROM observed_nodes")}


def session_status(path: str | Path) -> dict[str, Any]:
    initialize_session_state(path)
    with sqlite3.connect(Path(path).resolve()) as connection:
        row = connection.execute(
            "SELECT submit_attempts, accepted, last_diagnostics_json FROM session WHERE singleton = 1"
        ).fetchone()
        observed = connection.execute("SELECT count(*) FROM observed_nodes").fetchone()[0]
    return {
        "submitPlanAttempts": row[0],
        "accepted": bool(row[1]),
        "lastDiagnostics": json.loads(row[2]),
        "observedSourceNodes": observed,
    }


def _record_attempt(path: str | Path, *, accepted: bool, diagnostics: list[dict[str, Any]]) -> int:
    initialize_session_state(path)
    with sqlite3.connect(Path(path).resolve(), timeout=30) as connection:
        connection.execute(
            """UPDATE session
               SET submit_attempts = submit_attempts + 1,
                   accepted = max(accepted, ?),
                   last_diagnostics_json = ?
               WHERE singleton = 1""",
            (int(accepted), json.dumps(diagnostics, ensure_ascii=False, sort_keys=True)),
        )
        return connection.execute(
            "SELECT submit_attempts FROM session WHERE singleton = 1"
        ).fetchone()[0]


def _atomic_json(path: Path, value: Any) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    os.replace(temporary, path)


def submit_candidate(
    *,
    database: str | Path,
    state_path: str | Path,
    output_path: str | Path,
    language: str,
    version: str,
    digest: str,
    candidate: Any,
) -> dict[str, Any]:
    """Canonicalize and validate one submission inside the current Planner session."""

    if isinstance(candidate, dict) and "specification" not in candidate:
        candidate = {
            "schemaVersion": PLAN_SCHEMA_VERSION,
            "specification": {
                "language": language,
                "version": version,
                "indexSemanticDigest": digest,
            },
            "units": candidate.get("units"),
            "dependencies": candidate.get("dependencies"),
        }
    plan = normalize_candidate(candidate)
    observed = _observed_nodes(state_path)
    with connect(database, read_only=True) as connection:
        validation = validate_plan(
            plan,
            connection,
            expected_language=language,
            expected_version=version,
            expected_digest=digest,
            require_derived=False,
            allowed_source_node_ids=observed,
        )
        if validation["ok"]:
            plan.update(derive_graph(plan["units"], plan["dependencies"]))
            validation = validate_plan(
                plan,
                connection,
                expected_language=language,
                expected_version=version,
                expected_digest=digest,
                require_derived=True,
                allowed_source_node_ids=observed,
            )

    diagnostics = validation["issues"]
    attempt = _record_attempt(state_path, accepted=validation["ok"], diagnostics=diagnostics)
    if not validation["ok"]:
        return {
            "accepted": False,
            "attempt": attempt,
            "diagnosticCount": len(diagnostics),
            "diagnostics": diagnostics[:25],
            "instruction": "Correct only the reported issues, then call submit_plan again in this same session.",
        }

    _atomic_json(Path(output_path).resolve(), plan)
    return {
        "accepted": True,
        "attempt": attempt,
        "units": len(plan["units"]),
        "dependencies": len(plan["dependencies"]),
    }
