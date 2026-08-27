from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from ..util import canonical_json, stable_id


SEMANTICS_SCHEMA_VERSION = 1
EXTRACTOR_MODEL = "openai/gpt-5.6-sol"
EXTRACTOR_REASONING = "medium"
EXTRACTOR_AGENT = "spec2lean-semantic-extractor"
SUPPORTED_EXTRACTOR_CONFIGURATIONS = (
    (EXTRACTOR_MODEL, EXTRACTOR_REASONING),
    ("openai/gpt-5.4-mini", "low"),
    ("openai/gpt-5.3-codex-spark", "low"),
)

CLAIM_KINDS = (
    "SOURCE_FACT",
    "DERIVED_INTERPRETATION",
    "DESIGN_DEPENDENCY",
    "ASSUMPTION",
)
UNIT_KINDS = ("INSTRUCTION", "LANGUAGE_CONSTRUCT", "SHARED_CONCEPT", "OTHER")
RESTRICTION_KINDS = ("VERSION", "TARGET", "TYPE", "OPERAND", "OTHER")


def evidence_bundle_hash(bundle: dict[str, Any]) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(bundle).encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class SemanticScope:
    plan_run_id: str
    language: str
    version: str
    unit: dict[str, Any]
    evidence_bundle_hash: str
    evidence_ids: tuple[str, ...]
    run_id: str
    created_at: str

    @classmethod
    def from_inputs(
        cls, plan: dict[str, Any], bundle: dict[str, Any], unit_id: str, *, created_at: str
    ) -> SemanticScope:
        units = [item for item in plan.get("requestedUnits", []) if item.get("unitId") == unit_id]
        if len(units) != 1:
            raise KeyError(f"unit is not uniquely present in Phase-2 plan: {unit_id}")
        unit = dict(units[0])
        if bundle.get("unit") != unit:
            raise ValueError("Phase-3 evidence unit does not match the Phase-2 planned unit")
        if bundle.get("planRunId") != plan.get("planRunId"):
            raise ValueError("Phase-3 evidence planRunId does not match Phase 2")
        if bundle.get("language") != plan.get("language") or bundle.get("version") != plan.get("version"):
            raise ValueError("Phase-3 evidence specification identity does not match Phase 2")
        if bundle.get("sourceDatabaseDigest") != plan.get("sourceDatabaseDigest"):
            raise ValueError("Phase-3 evidence source specification does not match Phase 2")
        records = bundle.get("evidence")
        if not isinstance(records, list) or not records:
            raise ValueError("Phase-3 evidence bundle must contain evidence")
        ids = tuple(str(item.get("evidenceId", "")) for item in records)
        if any(not value.startswith("evidence:") for value in ids) or len(ids) != len(set(ids)):
            raise ValueError("Phase-3 evidence IDs must be present and unique")
        for item in records:
            if item.get("unitId") != unit_id:
                raise ValueError("Phase-3 evidence record belongs to a different unit")
            if not item.get("documentId") or not item.get("documentSha256") or item.get("sourceType") not in {"html", "pdf"}:
                raise ValueError("Phase-3 evidence record has incomplete source specification identity")
        bundle_hash = evidence_bundle_hash(bundle)
        return cls(
            plan_run_id=str(plan["planRunId"]),
            language=str(plan["language"]),
            version=str(plan["version"]),
            unit=unit,
            evidence_bundle_hash=bundle_hash,
            evidence_ids=ids,
            run_id=stable_id("semantic-run", plan["planRunId"], unit_id, bundle_hash),
            created_at=created_at,
        )

    @property
    def unit_id(self) -> str:
        return str(self.unit["unitId"])

    def to_dict(self) -> dict[str, Any]:
        return {
            "schemaVersion": SEMANTICS_SCHEMA_VERSION,
            "planRunId": self.plan_run_id,
            "language": self.language,
            "version": self.version,
            "unit": dict(self.unit),
            "evidenceBundleHash": self.evidence_bundle_hash,
            "evidenceIds": list(self.evidence_ids),
            "runId": self.run_id,
            "createdAt": self.created_at,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> SemanticScope:
        return cls(
            plan_run_id=value["planRunId"], language=value["language"], version=value["version"],
            unit=dict(value["unit"]), evidence_bundle_hash=value["evidenceBundleHash"],
            evidence_ids=tuple(value["evidenceIds"]), run_id=value["runId"], created_at=value["createdAt"],
        )

    def artifact(self, submission: dict[str, Any]) -> dict[str, Any]:
        base = {
            "schemaVersion": SEMANTICS_SCHEMA_VERSION,
            "phase": "SEMANTIC_EXTRACTOR",
            "planRunId": self.plan_run_id,
            "language": self.language,
            "version": self.version,
            "unit": dict(self.unit),
            "evidenceBundleHash": self.evidence_bundle_hash,
            "extractor": {
                "provider": "opencode", "model": EXTRACTOR_MODEL, "reasoning": EXTRACTOR_REASONING,
            },
            "runId": self.run_id,
            "createdAt": self.created_at,
            "outcome": submission["outcome"],
        }
        if submission["outcome"] == "SUCCESS":
            base["semantics"] = {key: value for key, value in submission.items() if key != "outcome"}
        else:
            base["failure"] = {key: value for key, value in submission.items() if key != "outcome"}
        return base
