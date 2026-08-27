from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any

from ..util import canonical_json, stable_id


TRANSLATION_SCHEMA_VERSION = 2
TRANSLATOR_MODEL = "openai/gpt-5.6-sol"
TRANSLATOR_REASONING = "medium"
TRANSLATOR_AGENT = "spec2lean-lean-translator"
SUPPORTED_TRANSLATOR_CONFIGURATIONS = (
    (TRANSLATOR_MODEL, TRANSLATOR_REASONING),
    ("openai/gpt-5.4-mini", "low"),
    ("openai/gpt-5.3-codex-spark", "low"),
)
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
class TranslationGroupScope:
    plan_run_id: str
    language: str
    version: str
    group: str
    units: tuple[dict[str, Any], ...]
    semantics_artifact_hashes: tuple[tuple[str, str], ...]
    semantics_run_ids: tuple[tuple[str, str], ...]
    semantic_claim_ids: tuple[tuple[str, str], ...]
    translation_run_id: str
    created_at: str

    @classmethod
    def from_inputs(
        cls, plan: dict[str, Any], group: str, semantics_by_unit: dict[str, dict[str, Any]],
        *, created_at: str
    ) -> TranslationGroupScope:
        from .groups import grouped_units

        units = tuple(grouped_units(plan).get(group, []))
        if not units:
            raise KeyError(f"translation group is not present in the Phase-2 plan: {group}")
        unit_ids = tuple(str(unit["unitId"]) for unit in units)
        if set(semantics_by_unit) != set(unit_ids):
            raise ValueError("Phase-5 group input must contain exactly one semantic artifact per group unit")
        hashes: list[tuple[str, str]] = []
        run_ids: list[tuple[str, str]] = []
        claim_refs: list[tuple[str, str]] = []
        for unit in units:
            unit_id = str(unit["unitId"])
            semantics = semantics_by_unit[unit_id]
            if semantics.get("phase") != "SEMANTIC_EXTRACTOR" or semantics.get("outcome") != "SUCCESS":
                raise ValueError(f"Phase-5 translation requires successful semantics for {unit_id}")
            if semantics.get("planRunId") != plan.get("planRunId"):
                raise ValueError(f"Phase-4 semantic planRunId does not match Phase 2 for {unit_id}")
            if semantics.get("language") != plan.get("language") or semantics.get("version") != plan.get("version"):
                raise ValueError(f"Phase-4 semantic specification identity does not match Phase 2 for {unit_id}")
            if semantics.get("unit") != unit:
                raise ValueError(f"Phase-4 semantic unit does not match Phase 2 for {unit_id}")
            run_id = semantics.get("runId")
            if not isinstance(run_id, str) or not run_id.startswith("semantic-run:"):
                raise ValueError(f"Phase-4 semantic run ID is missing or malformed for {unit_id}")
            claims = (semantics.get("semantics") or {}).get("claims")
            if not isinstance(claims, list) or not claims:
                raise ValueError(f"Phase-4 semantic artifact must contain claims for {unit_id}")
            ids = tuple(str(item.get("claimId", "")) for item in claims if isinstance(item, dict))
            if len(ids) != len(claims) or any(not item.startswith("claim:") for item in ids):
                raise ValueError(f"Phase-4 semantic claim IDs are malformed for {unit_id}")
            if len(ids) != len(set(ids)):
                raise ValueError(f"Phase-4 semantic claim IDs must be unique within {unit_id}")
            hashes.append((unit_id, semantics_artifact_hash(semantics)))
            run_ids.append((unit_id, run_id))
            claim_refs.extend((unit_id, claim_id) for claim_id in ids)
        translation_run_id = stable_id(
            "translation-group-run", plan["planRunId"], group, canonical_json(hashes)
        )
        return cls(
            plan_run_id=str(plan["planRunId"]),
            language=str(plan["language"]),
            version=str(plan["version"]),
            group=group,
            units=units,
            semantics_artifact_hashes=tuple(hashes),
            semantics_run_ids=tuple(run_ids),
            semantic_claim_ids=tuple(claim_refs),
            translation_run_id=translation_run_id,
            created_at=created_at,
        )

    @property
    def unit_ids(self) -> tuple[str, ...]:
        return tuple(str(unit["unitId"]) for unit in self.units)

    @property
    def suggested_namespace(self) -> str:
        return f"Spec2Lean.{_lean_component(self.language)}.{_lean_component(self.group)}"

    @property
    def lean_file(self) -> str:
        return f"{_lean_component(self.group)}.lean"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schemaVersion": TRANSLATION_SCHEMA_VERSION,
            "planRunId": self.plan_run_id,
            "language": self.language,
            "version": self.version,
            "group": {"name": self.group, "unitIds": list(self.unit_ids)},
            "units": [dict(unit) for unit in self.units],
            "semanticsArtifacts": [
                {"unitId": unit_id, "runId": dict(self.semantics_run_ids)[unit_id], "artifactHash": artifact_hash}
                for unit_id, artifact_hash in self.semantics_artifact_hashes
            ],
            "semanticClaimRefs": [
                {"unitId": unit_id, "claimId": claim_id}
                for unit_id, claim_id in self.semantic_claim_ids
            ],
            "translationRunId": self.translation_run_id,
            "createdAt": self.created_at,
            "suggestedNamespace": self.suggested_namespace,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> TranslationGroupScope:
        artifacts = value["semanticsArtifacts"]
        return cls(
            plan_run_id=value["planRunId"], language=value["language"], version=value["version"],
            group=value["group"]["name"], units=tuple(dict(item) for item in value["units"]),
            semantics_artifact_hashes=tuple((item["unitId"], item["artifactHash"]) for item in artifacts),
            semantics_run_ids=tuple((item["unitId"], item["runId"]) for item in artifacts),
            semantic_claim_ids=tuple((item["unitId"], item["claimId"]) for item in value["semanticClaimRefs"]),
            translation_run_id=value["translationRunId"], created_at=value["createdAt"],
        )

    def manifest(self, declarations: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "schemaVersion": TRANSLATION_SCHEMA_VERSION,
            "phase": "LLM_GROUP_TRANSLATOR",
            "planRunId": self.plan_run_id,
            "language": self.language,
            "version": self.version,
            "group": {"name": self.group, "unitIds": list(self.unit_ids)},
            "translationRunId": self.translation_run_id,
            "semanticsArtifacts": [
                {"unitId": unit_id, "runId": dict(self.semantics_run_ids)[unit_id], "artifactHash": artifact_hash}
                for unit_id, artifact_hash in self.semantics_artifact_hashes
            ],
            "translator": {
                "provider": "opencode",
                "model": TRANSLATOR_MODEL,
                "reasoning": TRANSLATOR_REASONING,
            },
            "target": {"language": LEAN_LANGUAGE, "version": LEAN_VERSION},
            "leanFile": self.lean_file,
            "createdAt": self.created_at,
            "declarations": declarations,
        }


# Import compatibility for extensions while the schema-v2 type is group-scoped.
TranslationScope = TranslationGroupScope
