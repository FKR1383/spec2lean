from __future__ import annotations

import re
from typing import Any

from ..models import DECLARATION_ROLES
from ..validation import LEAN_NAME, forbidden_constructs, lean_declarations
from .models import (
    CORE_GENERATOR_MODEL,
    CORE_GENERATOR_REASONING,
    CORE_SCHEMA_VERSION,
    GENERATOR_POLICY_VERSION,
    REPRESENTATION_SCHEMA_VERSION,
    FrozenSharedCore,
    SharedRequirement,
    core_run_id_for,
    json_hash,
    text_hash,
)
from .requirements import collect_shared_requirements


SUBMISSION_FIELDS = {"leanSource", "concepts", "declarations"}
CONCEPT_INPUT_FIELDS = {"dependencyId", "leanDeclarations"}
CONCEPT_FIELDS = {
    "dependencyId", "name", "kind", "sourceNodeIds", "requiredBy",
    "semanticInputHash", "leanDeclarations", "claimRefs",
}
DECLARATION_FIELDS = {
    "declaration", "role", "dependencyIds", "claimRefs", "supportsDeclarations",
}
MANIFEST_FIELDS = {
    "schemaVersion", "phase", "language", "version", "sourceDatabaseDigest",
    "coreRunId", "parentCoreRunId", "representationSchemaVersion", "generator",
    "target", "leanFile", "leanModule", "createdAt", "sourceHash", "concepts",
    "leanNamespace", "declarations", "semanticArtifacts",
}
SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")
NODE_ID = re.compile(r"^node:")
UNIT_ID = re.compile(r"^unit:")
PLAN_ID = re.compile(r"^plan:")
SEMANTIC_RUN_ID = re.compile(r"^semantic-run:")
CORE_RUN_ID = re.compile(r"^shared-core-run:[0-9a-f]{24}$")
LEAN_MODULE = re.compile(
    r"^[A-Za-z_][A-Za-z0-9_']*(?:\.[A-Za-z_][A-Za-z0-9_']*)+$"
)


def _diagnostic(code: str, message: str, path: str = "$") -> dict[str, str]:
    return {"code": code, "message": message, "path": path}


def _claim_ref(raw: Any, path: str, diagnostics: list[dict[str, str]]) -> tuple[str, str] | None:
    if not isinstance(raw, dict) or set(raw) != {"unitId", "claimId"}:
        diagnostics.append(_diagnostic(
            "INVALID_CLAIM_REFERENCE",
            "claim reference must contain exactly unitId and claimId",
            path,
        ))
        return None
    unit_id, claim_id = raw.get("unitId"), raw.get("claimId")
    if (
        not isinstance(unit_id, str) or not unit_id.startswith("unit:")
        or not isinstance(claim_id, str) or not claim_id.startswith("claim:")
    ):
        diagnostics.append(_diagnostic(
            "INVALID_CLAIM_REFERENCE", "claim reference IDs are malformed", path
        ))
        return None
    return unit_id, claim_id


def _normalize_refs(
    raw: Any, path: str, diagnostics: list[dict[str, str]]
) -> list[dict[str, str]]:
    if not isinstance(raw, list):
        diagnostics.append(_diagnostic("EXPECTED_ARRAY", "claimRefs must be an array", path))
        return []
    result: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for index, item in enumerate(raw):
        ref = _claim_ref(item, f"{path}[{index}]", diagnostics)
        if ref is None:
            continue
        if ref in seen:
            diagnostics.append(_diagnostic(
                "DUPLICATE_CLAIM_REFERENCE", "claimRefs contains a duplicate", f"{path}[{index}]"
            ))
            continue
        seen.add(ref)
        result.append({"unitId": ref[0], "claimId": ref[1]})
    return sorted(result, key=lambda item: (item["unitId"], item["claimId"]))


def _normalize_declarations(
    raw: Any,
    source: str,
    allowed_dependency_ids: set[str],
    allowed_claims_by_dependency: dict[str, set[tuple[str, str]]],
    diagnostics: list[dict[str, str]],
    lean_namespace: str | None = None,
) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        diagnostics.append(_diagnostic("EXPECTED_ARRAY", "declarations must be an array", "$.declarations"))
        raw = []
    declared = lean_declarations(source)
    mappings: list[dict[str, Any]] = []
    names: set[str] = set()
    for index, item in enumerate(raw):
        path = f"$.declarations[{index}]"
        if not isinstance(item, dict):
            diagnostics.append(_diagnostic("EXPECTED_OBJECT", "declaration mapping must be an object", path))
            continue
        for field in sorted(set(item) - DECLARATION_FIELDS):
            diagnostics.append(_diagnostic("UNEXPECTED_FIELD", f"unsupported declaration field: {field}", f"{path}.{field}"))
        name, role = item.get("declaration"), item.get("role")
        if not isinstance(name, str) or not LEAN_NAME.fullmatch(name):
            diagnostics.append(_diagnostic("INVALID_DECLARATION_NAME", "declaration must be a qualified ASCII Lean identifier", f"{path}.declaration"))
            continue
        if lean_namespace is not None and not name.startswith(lean_namespace + "."):
            diagnostics.append(_diagnostic(
                "DECLARATION_OUTSIDE_CORE_NAMESPACE",
                f"shared-core declaration must be below {lean_namespace}: {name}",
                f"{path}.declaration",
            ))
        if name in names:
            diagnostics.append(_diagnostic("DUPLICATE_DECLARATION_MAPPING", f"duplicate declaration mapping: {name}", f"{path}.declaration"))
        names.add(name)
        if name not in declared:
            diagnostics.append(_diagnostic("MISSING_LEAN_DECLARATION", f"mapped declaration is absent from Core.lean: {name}", f"{path}.declaration"))
        if role not in DECLARATION_ROLES:
            diagnostics.append(_diagnostic("INVALID_DECLARATION_ROLE", f"role must be one of {DECLARATION_ROLES}", f"{path}.role"))
        elif name in declared and declared[name] in {"structure", "inductive", "class"} and role != "PRIMARY_TYPE":
            diagnostics.append(_diagnostic("TYPE_ROLE_MISMATCH", f"introduced type must use PRIMARY_TYPE: {name}", f"{path}.role"))
        raw_dependency_ids = item.get("dependencyIds")
        if (
            not isinstance(raw_dependency_ids, list) or not raw_dependency_ids
            or not all(isinstance(value, str) for value in raw_dependency_ids)
        ):
            diagnostics.append(_diagnostic("INVALID_DEPENDENCY_OWNERSHIP", "dependencyIds must be a non-empty string array", f"{path}.dependencyIds"))
            dependency_ids: list[str] = []
        else:
            dependency_ids = sorted(set(raw_dependency_ids))
            if len(dependency_ids) != len(raw_dependency_ids):
                diagnostics.append(_diagnostic("DUPLICATE_DEPENDENCY_OWNERSHIP", "dependencyIds contains a duplicate", f"{path}.dependencyIds"))
            for dependency_id in dependency_ids:
                if dependency_id not in allowed_dependency_ids:
                    diagnostics.append(_diagnostic("UNKNOWN_SHARED_DEPENDENCY", f"unknown shared dependency: {dependency_id}", f"{path}.dependencyIds"))
        refs = _normalize_refs(item.get("claimRefs", []), f"{path}.claimRefs", diagnostics)
        ref_keys = {(value["unitId"], value["claimId"]) for value in refs}
        allowed_refs = set().union(*(
            allowed_claims_by_dependency.get(dependency_id, set()) for dependency_id in dependency_ids
        )) if dependency_ids else set()
        for ref in sorted(ref_keys - allowed_refs):
            diagnostics.append(_diagnostic(
                "UNKNOWN_SEMANTIC_CLAIM",
                f"claim is not owned by the mapped shared dependencies: {ref[0]}/{ref[1]}",
                f"{path}.claimRefs",
            ))
        supports = item.get("supportsDeclarations", [])
        if (
            not isinstance(supports, list)
            or not all(isinstance(value, str) and LEAN_NAME.fullmatch(value) for value in supports)
        ):
            diagnostics.append(_diagnostic("INVALID_SUPPORT_MAPPING", "supportsDeclarations must contain qualified Lean identifiers", f"{path}.supportsDeclarations"))
            supports = []
        elif len(supports) != len(set(supports)):
            diagnostics.append(_diagnostic("DUPLICATE_SUPPORT_MAPPING", "supportsDeclarations contains a duplicate", f"{path}.supportsDeclarations"))
        if supports and role != "IMPLEMENTATION_HELPER":
            diagnostics.append(_diagnostic("INVALID_SUPPORT_ROLE", "only IMPLEMENTATION_HELPER may use supportsDeclarations", f"{path}.supportsDeclarations"))
        if role == "IMPLEMENTATION_HELPER":
            if not refs and not supports:
                diagnostics.append(_diagnostic("MISSING_SEMANTIC_MAPPING", "implementation helper must cite claims or support a semantic declaration", path))
        elif not refs:
            diagnostics.append(_diagnostic("MISSING_SEMANTIC_MAPPING", "semantic core declaration requires claimRefs", f"{path}.claimRefs"))
        mapping: dict[str, Any] = {
            "declaration": name,
            "role": role,
            "dependencyIds": dependency_ids,
            "claimRefs": refs,
        }
        if supports:
            mapping["supportsDeclarations"] = list(supports)
        mappings.append(mapping)
    for name in sorted(set(declared) - names):
        diagnostics.append(_diagnostic("UNMAPPED_LEAN_DECLARATION", f"Core.lean declaration lacks traceability: {name}", "$.declarations"))
    mappings_by_name = {item["declaration"]: item for item in mappings}
    for index, mapping in enumerate(mappings):
        for supported in mapping.get("supportsDeclarations", []):
            if supported == mapping["declaration"]:
                diagnostics.append(_diagnostic("SELF_SUPPORT_MAPPING", "a declaration cannot support itself", f"$.declarations[{index}].supportsDeclarations"))
            elif supported not in mappings_by_name:
                diagnostics.append(_diagnostic("UNKNOWN_SUPPORT_DECLARATION", f"supported declaration has no mapping: {supported}", f"$.declarations[{index}].supportsDeclarations"))

    def resolved(name: str, seen: set[str]) -> set[tuple[str, str]]:
        if name in seen or name not in mappings_by_name:
            return set()
        mapping = mappings_by_name[name]
        result = {(item["unitId"], item["claimId"]) for item in mapping["claimRefs"]}
        for supported in mapping.get("supportsDeclarations", []):
            result.update(resolved(supported, {*seen, name}))
        return result

    for index, mapping in enumerate(mappings):
        if not resolved(mapping["declaration"], set()):
            diagnostics.append(_diagnostic("UNRESOLVED_SUPPORT_MAPPING", "declaration traceability does not resolve to a claim", f"$.declarations[{index}]"))
    return sorted(mappings, key=lambda item: item["declaration"])


def normalize_core_submission(
    requirements: tuple[SharedRequirement, ...],
    submission: Any,
    *,
    parent: FrozenSharedCore | None = None,
    lean_namespace: str | None = None,
) -> tuple[dict[str, Any] | None, list[dict[str, str]]]:
    diagnostics: list[dict[str, str]] = []
    if not isinstance(submission, dict):
        return None, [_diagnostic("EXPECTED_OBJECT", "shared-core submission must be an object")]
    for field in sorted(set(submission) - SUBMISSION_FIELDS):
        diagnostics.append(_diagnostic("UNEXPECTED_FIELD", f"unsupported shared-core field: {field}", f"$.{field}"))
    source = submission.get("leanSource")
    if not isinstance(source, str) or not source.strip():
        diagnostics.append(_diagnostic("EMPTY_LEAN_SOURCE", "leanSource must be non-empty", "$.leanSource"))
        source = ""
    diagnostics.extend(forbidden_constructs(source))
    if parent is not None and not source.startswith(parent.source):
        diagnostics.append(_diagnostic(
            "CORE_PREFIX_CHANGED",
            "a shared-core extension must preserve the accepted parent source as an exact prefix",
            "$.leanSource",
        ))

    requirements_by_id = {item.dependency_id: item for item in requirements}
    parent_concepts = {
        item["dependencyId"]: dict(item)
        for item in (parent.manifest.get("concepts", []) if parent else [])
        if isinstance(item, dict) and isinstance(item.get("dependencyId"), str)
    }
    target_ids = set(requirements_by_id) | set(parent_concepts)
    raw_concepts = submission.get("concepts")
    if not isinstance(raw_concepts, list):
        diagnostics.append(_diagnostic("EXPECTED_ARRAY", "concepts must be an array", "$.concepts"))
        raw_concepts = []
    concepts: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, item in enumerate(raw_concepts):
        path = f"$.concepts[{index}]"
        if not isinstance(item, dict):
            diagnostics.append(_diagnostic("EXPECTED_OBJECT", "concept mapping must be an object", path))
            continue
        for field in sorted(set(item) - CONCEPT_INPUT_FIELDS):
            diagnostics.append(_diagnostic("UNEXPECTED_FIELD", f"unsupported concept field: {field}", f"{path}.{field}"))
        dependency_id = item.get("dependencyId")
        if not isinstance(dependency_id, str) or dependency_id not in target_ids:
            diagnostics.append(_diagnostic("UNKNOWN_SHARED_DEPENDENCY", f"unknown shared dependency: {dependency_id!r}", f"{path}.dependencyId"))
            continue
        if dependency_id in seen_ids:
            diagnostics.append(_diagnostic("DUPLICATE_SHARED_DEPENDENCY", f"duplicate concept registry entry: {dependency_id}", f"{path}.dependencyId"))
        seen_ids.add(dependency_id)
        lean_names = item.get("leanDeclarations")
        if (
            not isinstance(lean_names, list) or not lean_names
            or not all(isinstance(value, str) and LEAN_NAME.fullmatch(value) for value in lean_names)
        ):
            diagnostics.append(_diagnostic("INVALID_CONCEPT_DECLARATIONS", "leanDeclarations must be a non-empty array of qualified Lean identifiers", f"{path}.leanDeclarations"))
            lean_names = []
        elif len(lean_names) != len(set(lean_names)):
            diagnostics.append(_diagnostic("DUPLICATE_CONCEPT_DECLARATION", "leanDeclarations contains a duplicate", f"{path}.leanDeclarations"))
        old = parent_concepts.get(dependency_id)
        if old is not None and sorted(lean_names) != old.get("leanDeclarations"):
            diagnostics.append(_diagnostic(
                "CORE_MAPPING_CHANGED",
                f"extension changed the registered declarations for {dependency_id}",
                f"{path}.leanDeclarations",
            ))
        if dependency_id in requirements_by_id:
            concept = requirements_by_id[dependency_id].concept_metadata(sorted(lean_names))
            if old is not None:
                if concept != old:
                    diagnostics.append(_diagnostic(
                        "CORE_MAPPING_CHANGED",
                        f"extension changed accepted concept metadata: {dependency_id}",
                        path,
                    ))
                concept = old
            concepts.append(concept)
        elif old is not None:
            concepts.append(old)
    missing = sorted(target_ids - seen_ids)
    if missing:
        diagnostics.append(_diagnostic("MISSING_SHARED_CONCEPT", f"concept registry does not cover: {missing}", "$.concepts"))

    allowed_claims: dict[str, set[tuple[str, str]]] = {}
    for dependency_id in target_ids:
        allowed_claims[dependency_id] = {
            (item.get("unitId"), item.get("claimId"))
            for item in parent_concepts.get(dependency_id, {}).get("claimRefs", [])
            if isinstance(item, dict)
        }
        requirement = requirements_by_id.get(dependency_id)
        if requirement is not None:
            allowed_claims[dependency_id].update(requirement.claim_refs)
    declarations = _normalize_declarations(
        submission.get("declarations"), source, target_ids, allowed_claims, diagnostics,
        lean_namespace,
    )
    by_name = {item["declaration"]: item for item in declarations}
    for index, concept in enumerate(concepts):
        dependency_id = concept["dependencyId"]
        for name in concept["leanDeclarations"]:
            mapping = by_name.get(name)
            if mapping is None:
                diagnostics.append(_diagnostic("UNKNOWN_CONCEPT_DECLARATION", f"concept maps an unregistered declaration: {name}", f"$.concepts[{index}].leanDeclarations"))
            elif dependency_id not in mapping["dependencyIds"]:
                diagnostics.append(_diagnostic("CONCEPT_OWNERSHIP_MISMATCH", f"declaration does not register ownership by {dependency_id}: {name}", f"$.concepts[{index}].leanDeclarations"))
    concept_names = {
        (concept["dependencyId"], name)
        for concept in concepts for name in concept["leanDeclarations"]
    }
    for index, mapping in enumerate(declarations):
        for dependency_id in mapping["dependencyIds"]:
            if (dependency_id, mapping["declaration"]) not in concept_names:
                diagnostics.append(_diagnostic("REGISTRY_OWNERSHIP_MISMATCH", f"declaration is absent from concept {dependency_id}: {mapping['declaration']}", f"$.declarations[{index}].dependencyIds"))
    if parent is not None:
        candidate_mappings = {item["declaration"]: item for item in declarations}
        for old in parent.manifest.get("declarations", []):
            if candidate_mappings.get(old.get("declaration")) != old:
                diagnostics.append(_diagnostic("CORE_MAPPING_CHANGED", f"extension changed accepted mapping: {old.get('declaration')}", "$.declarations"))
    if diagnostics:
        return None, diagnostics
    return {
        "leanSource": source.rstrip() + "\n",
        "concepts": sorted(concepts, key=lambda item: item["dependencyId"]),
        "declarations": declarations,
    }, []


def _registry_diagnostics(source: str, manifest: dict[str, Any]) -> list[dict[str, str]]:
    diagnostics: list[dict[str, str]] = []
    concepts = manifest.get("concepts")
    declarations = manifest.get("declarations")
    if not isinstance(concepts, list) or not isinstance(declarations, list):
        return [_diagnostic("INVALID_REGISTRY", "core manifest concepts/declarations must be arrays")]
    concept_ids: set[str] = set()
    concept_names: set[tuple[str, str]] = set()
    known_claims: dict[str, set[tuple[str, str]]] = {}
    for index, concept in enumerate(concepts):
        path = f"$.concepts[{index}]"
        if not isinstance(concept, dict) or set(concept) != CONCEPT_FIELDS:
            diagnostics.append(_diagnostic("INVALID_CONCEPT", "concept has an invalid field set", path))
            continue
        dependency_id = concept.get("dependencyId")
        if not isinstance(dependency_id, str) or not dependency_id.startswith("shared:"):
            diagnostics.append(_diagnostic("INVALID_SHARED_DEPENDENCY", "dependencyId must start shared:", f"{path}.dependencyId"))
            continue
        if dependency_id in concept_ids:
            diagnostics.append(_diagnostic("DUPLICATE_SHARED_DEPENDENCY", f"duplicate concept: {dependency_id}", path))
        concept_ids.add(dependency_id)
        for field in ("name", "kind"):
            value = concept.get(field)
            if not isinstance(value, str) or not value.strip():
                diagnostics.append(_diagnostic(
                    "INVALID_CONCEPT_METADATA",
                    f"concept {field} must be non-empty text",
                    f"{path}.{field}",
                ))
        source_node_ids = concept.get("sourceNodeIds")
        if (
            not isinstance(source_node_ids, list)
            or not source_node_ids
            or not all(
                isinstance(value, str) and NODE_ID.match(value)
                for value in source_node_ids
            )
            or len(source_node_ids) != len(set(source_node_ids))
        ):
            diagnostics.append(_diagnostic(
                "INVALID_CONCEPT_METADATA",
                "concept sourceNodeIds must be a non-empty unique node:* array",
                f"{path}.sourceNodeIds",
            ))
        required_by = concept.get("requiredBy")
        if (
            not isinstance(required_by, list)
            or not required_by
            or not all(
                isinstance(value, str) and UNIT_ID.match(value)
                for value in required_by
            )
            or len(required_by) != len(set(required_by))
        ):
            diagnostics.append(_diagnostic(
                "INVALID_CONCEPT_METADATA",
                "concept requiredBy must be a non-empty unique unit:* array",
                f"{path}.requiredBy",
            ))
        if not SHA256.fullmatch(str(concept.get("semanticInputHash", ""))):
            diagnostics.append(_diagnostic("INVALID_SEMANTIC_INPUT_HASH", "semanticInputHash is malformed", f"{path}.semanticInputHash"))
        refs = _normalize_refs(concept.get("claimRefs"), f"{path}.claimRefs", diagnostics)
        if not refs:
            diagnostics.append(_diagnostic(
                "MISSING_SEMANTIC_MAPPING",
                "shared concept must cite at least one semantic claim",
                f"{path}.claimRefs",
            ))
        known_claims[dependency_id] = {(item["unitId"], item["claimId"]) for item in refs}
        lean_names = concept.get("leanDeclarations")
        if (
            not isinstance(lean_names, list)
            or not lean_names
            or not all(isinstance(name, str) for name in lean_names)
            or len(lean_names) != len(set(lean_names))
        ):
            diagnostics.append(_diagnostic("INVALID_CONCEPT_DECLARATIONS", "concept must map at least one declaration", f"{path}.leanDeclarations"))
            continue
        for name in lean_names:
            if not isinstance(name, str) or not LEAN_NAME.fullmatch(name):
                diagnostics.append(_diagnostic("INVALID_CONCEPT_DECLARATIONS", "concept declaration is malformed", f"{path}.leanDeclarations"))
            else:
                concept_names.add((dependency_id, name))
    canonical_concepts = sorted(
        (item for item in concepts if isinstance(item, dict)),
        key=lambda item: str(item.get("dependencyId", "")),
    )
    if concepts != canonical_concepts:
        diagnostics.append(_diagnostic(
            "NONCANONICAL_CONCEPTS",
            "core concepts are not in canonical dependency order",
            "$.concepts",
        ))
    normalized = _normalize_declarations(
        declarations, source, concept_ids, known_claims, diagnostics,
        manifest.get("leanNamespace") if isinstance(manifest.get("leanNamespace"), str) else None,
    )
    canonical_declarations = sorted(
        (item for item in declarations if isinstance(item, dict)),
        key=lambda item: str(item.get("declaration", "")),
    )
    if declarations != canonical_declarations or normalized != canonical_declarations:
        diagnostics.append(_diagnostic("NONCANONICAL_DECLARATIONS", "core declaration mappings are not canonical", "$.declarations"))
    for index, mapping in enumerate(normalized):
        for dependency_id in mapping["dependencyIds"]:
            if (dependency_id, mapping["declaration"]) not in concept_names:
                diagnostics.append(_diagnostic("REGISTRY_OWNERSHIP_MISMATCH", f"declaration is absent from concept {dependency_id}: {mapping['declaration']}", f"$.declarations[{index}]"))
    mapped = {item["declaration"]: item for item in normalized}
    for dependency_id, name in concept_names:
        if name not in mapped or dependency_id not in mapped[name]["dependencyIds"]:
            diagnostics.append(_diagnostic("CONCEPT_OWNERSHIP_MISMATCH", f"concept mapping lacks matching declaration ownership: {dependency_id}/{name}", "$.concepts"))
    return diagnostics


def validate_core_artifact(
    plan: dict[str, Any],
    semantics_by_unit: dict[str, dict[str, Any]],
    core: FrozenSharedCore,
    *,
    parent: FrozenSharedCore | None = None,
) -> list[dict[str, str]]:
    manifest = core.manifest
    if not isinstance(manifest, dict):
        return [_diagnostic(
            "INVALID_MANIFEST", "shared-core manifest must be an object"
        )]
    diagnostics: list[dict[str, str]] = []
    if set(manifest) != MANIFEST_FIELDS:
        diagnostics.append(_diagnostic("INVALID_MANIFEST_FIELDS", "shared-core manifest has an invalid field set"))
    expected_scalar = {
        "schemaVersion": CORE_SCHEMA_VERSION,
        "phase": "SHARED_CORE",
        "language": plan.get("language"),
        "version": plan.get("version"),
        "sourceDatabaseDigest": plan.get("sourceDatabaseDigest"),
        "representationSchemaVersion": REPRESENTATION_SCHEMA_VERSION,
        "target": {"language": "Lean", "version": "4"},
    }
    for field, expected in expected_scalar.items():
        if manifest.get(field) != expected:
            diagnostics.append(_diagnostic("MANIFEST_MISMATCH", f"manifest {field} must equal {expected!r}", f"$.{field}"))
    created_at = manifest.get("createdAt")
    if not isinstance(created_at, str) or not created_at:
        diagnostics.append(_diagnostic(
            "INVALID_CREATED_AT", "createdAt must be non-empty text", "$.createdAt"
        ))
    lean_module = manifest.get("leanModule")
    lean_file = manifest.get("leanFile")
    lean_namespace = manifest.get("leanNamespace")
    if not isinstance(lean_namespace, str) or not LEAN_MODULE.fullmatch(lean_namespace):
        diagnostics.append(_diagnostic(
            "INVALID_LEAN_NAMESPACE", "leanNamespace is malformed", "$.leanNamespace"
        ))
    if not isinstance(lean_module, str) or not LEAN_MODULE.fullmatch(lean_module):
        diagnostics.append(_diagnostic(
            "INVALID_LEAN_MODULE", "leanModule is malformed", "$.leanModule"
        ))
    elif (
        not isinstance(lean_file, str)
        or lean_file != "modules/" + lean_module.replace(".", "/") + ".lean"
    ):
        diagnostics.append(_diagnostic(
            "INVALID_LEAN_FILE",
            "leanFile must be the modules/ path corresponding to leanModule",
            "$.leanFile",
        ))
    if core.lean_module != lean_module:
        diagnostics.append(_diagnostic(
            "LEAN_MODULE_MISMATCH",
            "loaded core and manifest Lean modules differ",
            "$.leanModule",
        ))
    if (
        isinstance(lean_namespace, str)
        and isinstance(manifest.get("sourceHash"), str)
        and lean_module
        != f"{lean_namespace}.C{manifest['sourceHash'].removeprefix('sha256:')[:16]}.Core"
    ):
        diagnostics.append(_diagnostic(
            "LEAN_NAMESPACE_MISMATCH",
            "leanModule must be rooted in leanNamespace and addressed by sourceHash",
            "$.leanModule",
        ))
    parent_core_run_id = manifest.get("parentCoreRunId")
    if (
        parent_core_run_id is not None
        and (
            not isinstance(parent_core_run_id, str)
            or not CORE_RUN_ID.fullmatch(parent_core_run_id)
        )
    ):
        diagnostics.append(_diagnostic(
            "INVALID_PARENT_CORE",
            "parentCoreRunId must be null or a shared-core run ID",
            "$.parentCoreRunId",
        ))
    expected_generator = {
        "provider": "opencode",
        "model": CORE_GENERATOR_MODEL,
        "reasoning": CORE_GENERATOR_REASONING,
        "policyVersion": GENERATOR_POLICY_VERSION,
        "invoked": bool(manifest.get("concepts")),
    }
    if manifest.get("generator") != expected_generator:
        diagnostics.append(_diagnostic("GENERATOR_POLICY_MISMATCH", "shared-core generator metadata is stale or malformed", "$.generator"))
    if manifest.get("sourceHash") != core.source_hash or core.source_hash != text_hash(core.source):
        diagnostics.append(_diagnostic("SOURCE_HASH_MISMATCH", "Core.lean differs from its recorded source hash", "$.sourceHash"))
    if core.manifest_hash != json_hash(manifest):
        diagnostics.append(_diagnostic("MANIFEST_HASH_MISMATCH", "loaded manifest hash is inconsistent"))
    concepts = manifest.get("concepts") if isinstance(manifest.get("concepts"), list) else []
    declarations = (
        manifest.get("declarations")
        if isinstance(manifest.get("declarations"), list) else []
    )
    registry_concepts = [item for item in concepts if isinstance(item, dict)]
    registry_declarations = [
        item for item in declarations if isinstance(item, dict)
    ]
    if manifest.get("coreRunId") != core_run_id_for(
        plan, core.source_hash, registry_concepts, registry_declarations
    ):
        diagnostics.append(_diagnostic("CORE_RUN_ID_MISMATCH", "coreRunId differs from deterministic content identity", "$.coreRunId"))
    if manifest.get("coreRunId") != core.core_run_id:
        diagnostics.append(_diagnostic("CORE_RUN_ID_MISMATCH", "loaded core and manifest IDs differ", "$.coreRunId"))
    diagnostics.extend(forbidden_constructs(core.source))
    diagnostics.extend(_registry_diagnostics(core.source, manifest))
    try:
        requirements = collect_shared_requirements(plan, semantics_by_unit)
    except Exception:
        raise
    concepts_by_id = {
        item.get("dependencyId"): item for item in concepts if isinstance(item, dict)
    }
    for requirement in requirements:
        concept = concepts_by_id.get(requirement.dependency_id)
        if concept is None:
            diagnostics.append(_diagnostic("MISSING_SHARED_CONCEPT", f"core lacks required dependency {requirement.dependency_id}", "$.concepts"))
            continue
        for field, expected in {
            "name": requirement.name,
            "kind": requirement.kind,
            "sourceNodeIds": list(requirement.source_node_ids),
            "semanticInputHash": requirement.semantic_input_hash,
        }.items():
            if concept.get(field) != expected:
                diagnostics.append(_diagnostic("STALE_SHARED_CONCEPT", f"{requirement.dependency_id} has stale {field}", "$.concepts"))
        recorded_required_by = concept.get("requiredBy")
        if (
            not isinstance(recorded_required_by, list)
            or not set(requirement.required_by).issubset(recorded_required_by)
        ):
            diagnostics.append(_diagnostic("STALE_SHARED_CONCEPT", f"{requirement.dependency_id} has stale requiredBy", "$.concepts"))
        raw_recorded_refs = concept.get("claimRefs")
        recorded_refs = {
            (item.get("unitId"), item.get("claimId"))
            for item in raw_recorded_refs if isinstance(item, dict)
        } if isinstance(raw_recorded_refs, list) else set()
        if not set(requirement.claim_refs).issubset(recorded_refs):
            diagnostics.append(_diagnostic("STALE_SHARED_CONCEPT", f"{requirement.dependency_id} has stale claimRefs", "$.concepts"))

    artifacts = manifest.get("semanticArtifacts")
    if not isinstance(artifacts, list):
        diagnostics.append(_diagnostic("INVALID_SEMANTIC_ARTIFACTS", "semanticArtifacts must be an array", "$.semanticArtifacts"))
        artifacts = []
    artifact_keys: set[tuple[str, str, str, str]] = set()
    for index, artifact in enumerate(artifacts):
        path = f"$.semanticArtifacts[{index}]"
        if not isinstance(artifact, dict) or set(artifact) != {"planRunId", "unitId", "runId", "artifactHash"}:
            diagnostics.append(_diagnostic("INVALID_SEMANTIC_ARTIFACT", "semantic artifact record is malformed", path))
            continue
        plan_run_id = artifact.get("planRunId")
        unit_id = artifact.get("unitId")
        run_id = artifact.get("runId")
        artifact_hash = artifact.get("artifactHash")
        if (
            not isinstance(plan_run_id, str) or not PLAN_ID.match(plan_run_id)
            or not isinstance(unit_id, str) or not UNIT_ID.match(unit_id)
            or not isinstance(run_id, str) or not SEMANTIC_RUN_ID.match(run_id)
            or not isinstance(artifact_hash, str) or not SHA256.fullmatch(artifact_hash)
        ):
            diagnostics.append(_diagnostic(
                "INVALID_SEMANTIC_ARTIFACT",
                "semantic artifact record contains malformed identifiers or hash",
                path,
            ))
            continue
        key = (plan_run_id, unit_id, run_id, artifact_hash)
        if key in artifact_keys:
            diagnostics.append(_diagnostic("DUPLICATE_SEMANTIC_ARTIFACT", "semantic artifact record is duplicated", path))
        artifact_keys.add(key)

    # semanticInputHash is the scoped freshness authority: a new Phase-4 run
    # whose unrelated unit semantics changed must not invalidate this core.  The
    # provenance registry still has to remain well-formed and cover every
    # claim-bearing unit. Artifact hashes bind the accepted historical inputs;
    # they are not compared to a later artifact with unrelated changes.
    # Require provenance only for concepts this immutable snapshot actually
    # owns.  A candidate parent may legitimately lack a newly requested
    # concept (and therefore its unit's provenance); that is precisely the
    # append-only extension case.  The completed child is validated again and
    # must cover the newly materialized concept before publication.
    required_trace_units = {
        str(ref.get("unitId"))
        for concept in concepts if isinstance(concept, dict)
        for ref in (
            concept.get("claimRefs")
            if isinstance(concept.get("claimRefs"), list) else []
        )
        if isinstance(ref, dict) and isinstance(ref.get("unitId"), str)
    }
    artifact_units = {key[1] for key in artifact_keys}
    for unit_id in sorted(required_trace_units - artifact_units):
        diagnostics.append(_diagnostic(
            "MISSING_SEMANTIC_ARTIFACT",
            f"core has no Phase-4 provenance for claim-bearing unit {unit_id}",
            "$.semanticArtifacts",
        ))
    if parent is not None:
        if manifest.get("parentCoreRunId") != parent.core_run_id:
            diagnostics.append(_diagnostic("PARENT_CORE_MISMATCH", "parentCoreRunId does not name the accepted parent", "$.parentCoreRunId"))
        if not core.source.startswith(parent.source):
            diagnostics.append(_diagnostic("CORE_PREFIX_CHANGED", "extension changed the immutable parent source prefix", "$.sourceHash"))
        if manifest.get("leanNamespace") != parent.manifest.get("leanNamespace"):
            diagnostics.append(_diagnostic(
                "CORE_NAMESPACE_CHANGED",
                "extension changed the immutable parent Lean namespace",
                "$.leanNamespace",
            ))
        current_mappings = {item.get("declaration"): item for item in manifest.get("declarations", []) if isinstance(item, dict)}
        for old in parent.manifest.get("declarations", []):
            if current_mappings.get(old.get("declaration")) != old:
                diagnostics.append(_diagnostic("CORE_MAPPING_CHANGED", f"extension changed parent mapping {old.get('declaration')}", "$.declarations"))
        current_concepts = {
            item.get("dependencyId"): item
            for item in manifest.get("concepts", []) if isinstance(item, dict)
        }
        for old in parent.manifest.get("concepts", []):
            if (
                not isinstance(old, dict)
                or current_concepts.get(old.get("dependencyId")) != old
            ):
                diagnostics.append(_diagnostic(
                    "CORE_MAPPING_CHANGED",
                    f"extension changed parent concept {old.get('dependencyId') if isinstance(old, dict) else '<malformed>'}",
                    "$.concepts",
                ))
    return diagnostics
