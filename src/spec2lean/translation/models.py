from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any

from ..util import canonical_json, stable_id


TRANSLATION_SCHEMA_VERSION = 4
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
    shared_core: dict[str, Any] | None = None

    @classmethod
    def from_inputs(
        cls, plan: dict[str, Any], group: str, semantics_by_unit: dict[str, dict[str, Any]],
        *, created_at: str, shared_core: Any | None = None,
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
        relevant_shared = sorted(
            (
                dict(item)
                for item in plan.get("sharedPrerequisites", [])
                if isinstance(item, dict)
                and set(item.get("requiredBy", [])) & set(unit_ids)
            ),
            key=lambda item: str(item.get("dependencyId", "")),
        )
        core_view: dict[str, Any] | None = None
        if relevant_shared:
            from .shared_core import MissingSharedAbstraction

            manifest = getattr(shared_core, "manifest", shared_core)
            if not isinstance(manifest, dict):
                item = relevant_shared[0]
                raise MissingSharedAbstraction(
                    dependency_id=str(item.get("dependencyId", "")),
                    semantic_requirement={
                        "name": str(item.get("name", "shared semantic dependency")),
                        "kind": str(item.get("kind", "")),
                        "requiredBy": [str(value) for value in item.get("requiredBy", [])],
                        "reason": str(item.get("reason", "")),
                    },
                    claim_refs=_shared_claim_refs(item, semantics_by_unit),
                    detail="the frozen shared core was not supplied",
                )
            concepts = {
                str(item.get("dependencyId")): item
                for item in manifest.get("concepts", [])
                if isinstance(item, dict) and isinstance(item.get("dependencyId"), str)
            }
            required_ids = [str(item["dependencyId"]) for item in relevant_shared]
            for item in relevant_shared:
                dependency_id = str(item["dependencyId"])
                if dependency_id not in concepts:
                    raise MissingSharedAbstraction(
                        dependency_id=dependency_id,
                        semantic_requirement={
                            "name": str(item.get("name", "shared semantic dependency")),
                            "kind": str(item.get("kind", "")),
                            "requiredBy": [str(value) for value in item.get("requiredBy", [])],
                            "reason": str(item.get("reason", "")),
                        },
                        claim_refs=_shared_claim_refs(item, semantics_by_unit),
                        detail="the frozen shared core has no registered representation",
                    )
            declarations = [
                dict(item) for item in manifest.get("declarations", [])
                if isinstance(item, dict)
            ]
            required_declarations = {
                declaration
                for dependency_id in required_ids
                for declaration in concepts[dependency_id].get("leanDeclarations", [])
                if isinstance(declaration, str)
            }
            # Include helper mappings reachable from registered declarations so validation can
            # resolve the frozen registry without exposing unrelated semantic inputs.
            needed = set(required_declarations)
            changed = True
            while changed:
                changed = False
                for mapping in declarations:
                    name = mapping.get("declaration")
                    supports = {
                        value for value in mapping.get("supportsDeclarations", [])
                        if isinstance(value, str)
                    }
                    if isinstance(name, str) and (name in needed or supports & needed):
                        before = len(needed)
                        needed.add(name)
                        needed.update(supports)
                        changed = changed or len(needed) != before
            core_view = {
                "coreRunId": manifest.get("coreRunId"),
                "manifestHash": (
                    getattr(shared_core, "manifest_hash", None)
                    or manifest.get("manifestHash")
                    or "sha256:" + hashlib.sha256(canonical_json(manifest).encode("utf-8")).hexdigest()
                ),
                "sourceHash": manifest.get("sourceHash"),
                "leanModule": manifest.get("leanModule"),
                "concepts": [dict(concepts[item]) for item in required_ids],
                "declarations": [
                    mapping for mapping in declarations
                    if mapping.get("declaration") in needed
                ],
            }
            if not all(
                isinstance(core_view.get(field), str) and core_view[field]
                for field in ("coreRunId", "manifestHash", "sourceHash", "leanModule")
            ):
                raise ValueError("shared-core identity and integrity hashes are incomplete")
        elif shared_core is not None:
            raise ValueError("a shared core was supplied but this translation group has no shared prerequisites")

        translation_run_id = stable_id(
            "translation-group-run", plan["planRunId"], group, canonical_json(hashes),
            canonical_json(_core_reference(core_view)),
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
            shared_core=core_view,
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
        result = {
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
        if self.shared_core is not None:
            result["sharedCore"] = {
                **_core_reference(self.shared_core),
                "concepts": [dict(item) for item in self.shared_core.get("concepts", [])],
                "declarations": [dict(item) for item in self.shared_core.get("declarations", [])],
            }
        return result

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
            shared_core=dict(value["sharedCore"]) if isinstance(value.get("sharedCore"), dict) else None,
        )

    @property
    def shared_dependency_ids(self) -> tuple[str, ...]:
        if self.shared_core is None:
            return ()
        return tuple(
            str(item["dependencyId"])
            for item in self.shared_core.get("concepts", [])
        )

    def manifest(
        self, declarations: list[dict[str, Any]], shared_uses: list[dict[str, Any]] | None = None
    ) -> dict[str, Any]:
        result = {
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
            "sharedCore": _core_reference(self.shared_core),
            "sharedUses": list(shared_uses or []),
        }
        return result


def _core_reference(core: dict[str, Any] | None) -> dict[str, str] | None:
    if core is None:
        return None
    return {
        key: str(core[key])
        for key in ("coreRunId", "manifestHash", "sourceHash", "leanModule")
    }


def _shared_claim_refs(
    prerequisite: dict[str, Any], semantics_by_unit: dict[str, dict[str, Any]]
) -> list[dict[str, str]]:
    dependency_id = prerequisite.get("dependencyId")
    refs: list[dict[str, str]] = []
    for unit_id in prerequisite.get("requiredBy", []):
        semantics = semantics_by_unit.get(str(unit_id), {})
        for dependency in (semantics.get("semantics") or {}).get("dependencies", []):
            if isinstance(dependency, dict) and dependency.get("dependencyId") == dependency_id:
                refs.extend(
                    {"unitId": str(unit_id), "claimId": str(claim_id)}
                    for claim_id in dependency.get("semanticClaimIds", [])
                    if isinstance(claim_id, str)
                )
    return refs


# Import compatibility for extensions while the type remains group-scoped.
TranslationScope = TranslationGroupScope
