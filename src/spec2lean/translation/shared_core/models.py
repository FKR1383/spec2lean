from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ...util import canonical_json, stable_id
from ..models import TRANSLATOR_MODEL, TRANSLATOR_REASONING


CORE_SCHEMA_VERSION = 1
REPRESENTATION_SCHEMA_VERSION = 1
GENERATOR_POLICY_VERSION = 1
CORE_GENERATOR_MODEL = TRANSLATOR_MODEL
CORE_GENERATOR_REASONING = TRANSLATOR_REASONING
CORE_GENERATOR_AGENT = "spec2lean-shared-core-materializer"


def json_hash(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def text_hash(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def core_run_id_for(
    plan: dict[str, Any], source_hash: str, concepts: list[dict[str, Any]],
    declarations: list[dict[str, Any]],
) -> str:
    registry = {
        "concepts": sorted(
            concepts, key=lambda value: str(value.get("dependencyId", ""))
        ),
        "declarations": sorted(
            declarations, key=lambda value: str(value.get("declaration", ""))
        ),
    }
    return stable_id(
        "shared-core-run",
        plan.get("language"),
        plan.get("version"),
        plan.get("sourceDatabaseDigest"),
        CORE_SCHEMA_VERSION,
        REPRESENTATION_SCHEMA_VERSION,
        GENERATOR_POLICY_VERSION,
        CORE_GENERATOR_MODEL,
        CORE_GENERATOR_REASONING,
        source_hash,
        canonical_json(registry),
    )


@dataclass(frozen=True, slots=True)
class SharedRequirement:
    dependency_id: str
    name: str
    kind: str
    source_node_ids: tuple[str, ...]
    required_by: tuple[str, ...]
    semantic_input_hash: str
    claim_refs: tuple[tuple[str, str], ...]
    semantic_dependencies: tuple[dict[str, Any], ...]
    claims: tuple[dict[str, Any], ...]
    semantic_artifacts: tuple[dict[str, str], ...]

    def concept_metadata(self, lean_declarations: list[str]) -> dict[str, Any]:
        return {
            "dependencyId": self.dependency_id,
            "name": self.name,
            "kind": self.kind,
            "sourceNodeIds": list(self.source_node_ids),
            "requiredBy": list(self.required_by),
            "semanticInputHash": self.semantic_input_hash,
            "leanDeclarations": list(lean_declarations),
            "claimRefs": [
                {"unitId": unit_id, "claimId": claim_id}
                for unit_id, claim_id in self.claim_refs
            ],
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.concept_metadata([]),
            "semanticDependencies": [dict(item) for item in self.semantic_dependencies],
            "claims": [dict(item) for item in self.claims],
            "semanticArtifacts": [dict(item) for item in self.semantic_artifacts],
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> SharedRequirement:
        return cls(
            dependency_id=str(value["dependencyId"]),
            name=str(value["name"]),
            kind=str(value["kind"]),
            source_node_ids=tuple(str(item) for item in value["sourceNodeIds"]),
            required_by=tuple(str(item) for item in value["requiredBy"]),
            semantic_input_hash=str(value["semanticInputHash"]),
            claim_refs=tuple(
                (str(item["unitId"]), str(item["claimId"]))
                for item in value["claimRefs"]
            ),
            semantic_dependencies=tuple(dict(item) for item in value["semanticDependencies"]),
            claims=tuple(dict(item) for item in value["claims"]),
            semantic_artifacts=tuple(dict(item) for item in value["semanticArtifacts"]),
        )


@dataclass(frozen=True, slots=True)
class FrozenSharedCore:
    directory: Path
    source_path: Path
    manifest_path: Path
    run_path: Path
    source: str
    manifest: dict[str, Any]
    core_run_id: str
    lean_module: str
    source_hash: str
    manifest_hash: str
    reused: bool = False

    @property
    def core_id(self) -> str:
        """Compatibility alias; persisted artifacts use ``coreRunId``."""
        return self.core_run_id

    def with_reused(self, value: bool) -> FrozenSharedCore:
        return FrozenSharedCore(
            directory=self.directory,
            source_path=self.source_path,
            manifest_path=self.manifest_path,
            run_path=self.run_path,
            source=self.source,
            manifest=self.manifest,
            core_run_id=self.core_run_id,
            lean_module=self.lean_module,
            source_hash=self.source_hash,
            manifest_hash=self.manifest_hash,
            reused=value,
        )

    def reference(self) -> dict[str, str]:
        return {
            "coreRunId": self.core_run_id,
            "manifestHash": self.manifest_hash,
            "sourceHash": self.source_hash,
            "leanModule": self.lean_module,
        }


@dataclass(slots=True)
class MissingSharedAbstraction(ValueError):
    dependency_id: str
    semantic_requirement: dict[str, Any]
    claim_refs: list[dict[str, str]] = field(default_factory=list)
    detail: str = ""

    @property
    def code(self) -> str:
        return "MISSING_SHARED_ABSTRACTION"

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "dependencyId": self.dependency_id,
            "semanticRequirement": dict(self.semantic_requirement),
            "claimRefs": [dict(item) for item in self.claim_refs],
            "detail": self.detail,
        }

    def __str__(self) -> str:
        suffix = f": {self.detail}" if self.detail else ""
        return f"{self.code} for {self.dependency_id}{suffix}"
