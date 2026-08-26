from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any

from ..util import canonical_json, stable_id


TRANSLATION_SCHEMA_VERSION = 1
TRANSLATOR_MODEL = "openai/gpt-5.3-codex-spark"
TRANSLATOR_REASONING = "low"
TRANSLATOR_AGENT = "spec2lean-lean-translator"
LEAN_LANGUAGE = "Lean"
LEAN_VERSION = "4"

DECLARATION_ROLES = (
    "PRIMARY_TYPE",
    "OPERATION",
    "EXECUTION",
    "BRANCH_HELPER",
    "EDGE_CASE_HELPER",
    "SEMANTIC_HELPER",
    "IMPLEMENTATION_HELPER",
)


def semantics_artifact_hash(artifact: dict[str, Any]) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(artifact).encode("utf-8")).hexdigest()


def _lean_component(value: str) -> str:
    words = re.findall(r"[A-Za-z0-9]+", value)
    component = "".join(word[:1].upper() + word[1:] for word in words) or "Unit"
    if component[0].isdigit():
        component = "V" + component
    return component


@dataclass(frozen=True, slots=True)
class TranslationScope:
    plan_run_id: str
    language: str
    version: str
    unit: dict[str, Any]
    semantics_artifact_hash: str
    semantics_run_id: str
    semantic_claim_ids: tuple[str, ...]
    translation_run_id: str
    created_at: str

    @classmethod
    def from_inputs(
        cls, plan: dict[str, Any], semantics: dict[str, Any], unit_id: str, *, created_at: str
    ) -> TranslationScope:
        units = [item for item in plan.get("requestedUnits", []) if item.get("unitId") == unit_id]
        if len(units) != 1:
            raise KeyError(f"unit is not uniquely present in Phase-2 plan: {unit_id}")
        unit = dict(units[0])
        if semantics.get("phase") != "SEMANTIC_EXTRACTOR" or semantics.get("outcome") != "SUCCESS":
            raise ValueError("Phase-5 translation requires a successful Phase-4 semantic artifact")
        if semantics.get("planRunId") != plan.get("planRunId"):
            raise ValueError("Phase-4 semantic planRunId does not match Phase 2")
        if semantics.get("language") != plan.get("language") or semantics.get("version") != plan.get("version"):
            raise ValueError("Phase-4 semantic specification identity does not match Phase 2")
        if semantics.get("unit") != unit:
            raise ValueError("Phase-4 semantic unit does not match the Phase-2 planned unit")
        semantics_run_id = semantics.get("runId")
        if not isinstance(semantics_run_id, str) or not semantics_run_id.startswith("semantic-run:"):
            raise ValueError("Phase-4 semantic run ID is missing or malformed")
        semantic_payload = semantics.get("semantics")
        if not isinstance(semantic_payload, dict):
            raise ValueError("Phase-4 semantic payload is missing")
        claims = semantic_payload.get("claims")
        if not isinstance(claims, list) or not claims:
            raise ValueError("Phase-4 semantic artifact must contain semantic claims")
        claim_ids = tuple(str(item.get("claimId", "")) for item in claims if isinstance(item, dict))
        if len(claim_ids) != len(claims) or any(not item.startswith("claim:") for item in claim_ids):
            raise ValueError("Phase-4 semantic claim IDs are malformed")
        if len(claim_ids) != len(set(claim_ids)):
            raise ValueError("Phase-4 semantic claim IDs must be unique")
        semantic_hash = semantics_artifact_hash(semantics)
        translation_run_id = stable_id("translation-run", plan["planRunId"], unit_id, semantic_hash)
        return cls(
            plan_run_id=str(plan["planRunId"]),
            language=str(plan["language"]),
            version=str(plan["version"]),
            unit=unit,
            semantics_artifact_hash=semantic_hash,
            semantics_run_id=semantics_run_id,
            semantic_claim_ids=claim_ids,
            translation_run_id=translation_run_id,
            created_at=created_at,
        )

    @property
    def unit_id(self) -> str:
        return str(self.unit["unitId"])

    @property
    def suggested_namespace(self) -> str:
        return f"Spec2Lean.{_lean_component(self.language)}.{_lean_component(str(self.unit['name']))}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schemaVersion": TRANSLATION_SCHEMA_VERSION,
            "planRunId": self.plan_run_id,
            "language": self.language,
            "version": self.version,
            "unit": dict(self.unit),
            "semanticsArtifactHash": self.semantics_artifact_hash,
            "semanticsRunId": self.semantics_run_id,
            "semanticClaimIds": list(self.semantic_claim_ids),
            "translationRunId": self.translation_run_id,
            "createdAt": self.created_at,
            "suggestedNamespace": self.suggested_namespace,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> TranslationScope:
        return cls(
            plan_run_id=value["planRunId"],
            language=value["language"],
            version=value["version"],
            unit=dict(value["unit"]),
            semantics_artifact_hash=value["semanticsArtifactHash"],
            semantics_run_id=value["semanticsRunId"],
            semantic_claim_ids=tuple(value["semanticClaimIds"]),
            translation_run_id=value["translationRunId"],
            created_at=value["createdAt"],
        )

    def manifest(self, declarations: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "schemaVersion": TRANSLATION_SCHEMA_VERSION,
            "phase": "LLM_TRANSLATOR",
            "planRunId": self.plan_run_id,
            "language": self.language,
            "version": self.version,
            "unit": dict(self.unit),
            "translationRunId": self.translation_run_id,
            "semanticsRunId": self.semantics_run_id,
            "semanticsArtifactHash": self.semantics_artifact_hash,
            "translator": {
                "provider": "opencode",
                "model": TRANSLATOR_MODEL,
                "reasoning": TRANSLATOR_REASONING,
            },
            "target": {"language": LEAN_LANGUAGE, "version": LEAN_VERSION},
            "leanFile": "Unit.lean",
            "createdAt": self.created_at,
            "declarations": declarations,
        }
