from __future__ import annotations

import sqlite3
from collections import defaultdict
from pathlib import Path
from typing import Any

from ..database import connect, semantic_digest
from ..semantics.models import evidence_bundle_hash
from ..translation.models import semantics_artifact_hash
from ..translation.validation import lean_declarations
from ..util import canonical_json, normalize_text, stable_id


EVIDENCE_REQUIRED_KINDS = {"SOURCE_FACT", "DERIVED_INTERPRETATION"}


def _bundle_records(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        item for item in [*bundle.get("evidence", []), *bundle.get("resolutions", [])]
        if isinstance(item, dict)
    ]


def _record_id(item: dict[str, Any]) -> str | None:
    value = item.get("evidenceId") or item.get("resolutionId")
    return value if isinstance(value, str) else None


def _broken(code: str, message: str, **references: str) -> dict[str, str]:
    return {"code": code, "message": message, **references}


def _mapping_claims(
    name: str,
    mappings: dict[str, dict[str, Any]],
    broken: list[dict[str, str]],
    seen: tuple[str, ...] = (),
) -> set[str]:
    if name in seen:
        broken.append(_broken(
            "DECLARATION_SUPPORT_CYCLE",
            f"declaration support cycle includes {name}",
            declaration=name,
        ))
        return set()
    mapping = mappings.get(name)
    if mapping is None:
        broken.append(_broken(
            "MISSING_SUPPORTED_DECLARATION",
            f"supported declaration has no mapping: {name}",
            declaration=name,
        ))
        return set()
    claims = {
        item for item in mapping.get("semanticClaimIds", []) if isinstance(item, str)
    }
    for supported in mapping.get("supportsDeclarations", []):
        if isinstance(supported, str):
            claims.update(_mapping_claims(supported, mappings, broken, (*seen, name)))
    return claims


def _mapping_claim_refs(
    name: str,
    mappings: dict[str, dict[str, Any]],
    broken: list[dict[str, str]],
    seen: tuple[str, ...] = (),
) -> set[tuple[str, str]]:
    if name in seen:
        broken.append(_broken("DECLARATION_SUPPORT_CYCLE", f"declaration support cycle includes {name}", declaration=name))
        return set()
    mapping = mappings.get(name)
    if mapping is None:
        broken.append(_broken("MISSING_SUPPORTED_DECLARATION", f"supported declaration has no mapping: {name}", declaration=name))
        return set()
    refs = {
        (item.get("unitId"), item.get("claimId"))
        for item in mapping.get("claimRefs", [])
        if isinstance(item, dict) and isinstance(item.get("unitId"), str) and isinstance(item.get("claimId"), str)
    }
    for supported in mapping.get("supportsDeclarations", []):
        if isinstance(supported, str):
            refs.update(_mapping_claim_refs(supported, mappings, broken, (*seen, name)))
    return refs


def _claim_refs(values: Any) -> set[tuple[str, str]]:
    if not isinstance(values, list):
        return set()
    return {
        (str(item["unitId"]), str(item["claimId"]))
        for item in values
        if isinstance(item, dict)
        and isinstance(item.get("unitId"), str)
        and isinstance(item.get("claimId"), str)
    }


def _semantic_shared_claims(semantics: dict[str, Any]) -> dict[str, set[str]]:
    result: dict[str, set[str]] = defaultdict(set)
    for dependency in (semantics.get("semantics") or {}).get("dependencies", []):
        if not isinstance(dependency, dict) or not isinstance(dependency.get("dependencyId"), str):
            continue
        result[str(dependency["dependencyId"])].update(
            str(claim_id)
            for claim_id in dependency.get("semanticClaimIds", [])
            if isinstance(claim_id, str)
        )
    return dict(result)


def _items_by_string_key(values: Any, key: str) -> dict[str, dict[str, Any]]:
    if not isinstance(values, list):
        return {}
    return {
        str(item[key]): item
        for item in values
        if isinstance(item, dict) and isinstance(item.get(key), str)
    }


def _string_items(value: Any) -> set[str]:
    if not isinstance(value, list):
        return set()
    return {str(item) for item in value if isinstance(item, str)}


def _core_claim_mappings(
    unit_ids: set[str],
    semantics_by_unit: dict[str, dict[str, Any]],
    group_manifest: dict[str, Any],
    core_source: str,
    core_manifest: dict[str, Any],
) -> tuple[set[str], dict[str, dict[str, Any]], list[dict[str, str]]]:
    """Resolve relevant frozen-core declarations to current Phase-4 claims.

    The semantic artifacts remain authoritative: ``sharedUses`` selects the
    required dependency and declarations, while the core registry proves that
    the declarations are owned by that dependency. Claim references used by
    checking are derived from each unit's semantic dependency rather than from
    the representation registry alone.
    """

    broken: list[dict[str, str]] = []
    uses = _items_by_string_key(group_manifest.get("sharedUses"), "dependencyId")
    concepts = _items_by_string_key(core_manifest.get("concepts"), "dependencyId")
    flat_declarations = _items_by_string_key(core_manifest.get("declarations"), "declaration")
    core_declared = set(lean_declarations(core_source))

    expected_by_dependency: dict[str, set[tuple[str, str]]] = defaultdict(set)
    for unit_id, semantics in semantics_by_unit.items():
        if unit_id not in unit_ids:
            continue
        for dependency_id, claim_ids in _semantic_shared_claims(semantics).items():
            expected_by_dependency[dependency_id].update(
                (unit_id, claim_id) for claim_id in claim_ids
            )

    for dependency_id in sorted(expected_by_dependency):
        if dependency_id not in uses:
            broken.append(_broken(
                "MISSING_SHARED_USE",
                f"semantic dependency is not bound to the frozen shared core: {dependency_id}",
            ))
    for dependency_id in sorted(set(uses) - set(expected_by_dependency)):
        broken.append(_broken(
            "UNKNOWN_SHARED_USE",
            f"group manifest binds an unused shared dependency: {dependency_id}",
        ))

    relevant_names: set[str] = set()
    for dependency_id, use in sorted(uses.items()):
        concept = concepts.get(dependency_id)
        if concept is None:
            broken.append(_broken(
                "MISSING_SHARED_CONCEPT",
                f"frozen core manifest has no concept for dependency: {dependency_id}",
            ))
            continue
        used_names = _string_items(use.get("leanDeclarations"))
        registered_names = _string_items(concept.get("leanDeclarations"))
        if not used_names or not used_names.issubset(registered_names):
            broken.append(_broken(
                "SHARED_USE_DECLARATION_MISMATCH",
                f"group shared declarations are not a nonempty subset of the frozen core registry: {dependency_id}",
            ))
        expected_refs = expected_by_dependency.get(dependency_id, set())
        use_refs = {item for item in _claim_refs(use.get("claimRefs")) if item[0] in unit_ids}
        if use_refs != expected_refs:
            broken.append(_broken(
                "SHARED_USE_CLAIM_MISMATCH",
                f"group shared claim references differ from Phase-4 semantics: {dependency_id}",
            ))
        concept_refs = _claim_refs(concept.get("claimRefs"))
        if not expected_refs.issubset(concept_refs):
            broken.append(_broken(
                "SHARED_CONCEPT_CLAIM_MISMATCH",
                f"frozen core concept does not trace every required Phase-4 claim: {dependency_id}",
            ))
        if dependency_id in expected_by_dependency:
            for name in used_names & registered_names:
                relevant_names.add(name)

    # Keep the shared trace bounded to declarations this group actually names,
    # while retaining the support graph needed to resolve implementation
    # helpers.  A concept may register more declarations than one group uses.
    changed = True
    while changed:
        changed = False
        for name, mapping in flat_declarations.items():
            supports = _string_items(mapping.get("supportsDeclarations"))
            if name not in relevant_names and not (supports & relevant_names):
                continue
            before = len(relevant_names)
            relevant_names.add(name)
            relevant_names.update(supports)
            changed = changed or len(relevant_names) != before

    mappings: dict[str, dict[str, Any]] = {}
    for name in sorted(relevant_names):
        if name not in core_declared:
            broken.append(_broken(
                "MISSING_LEAN_DECLARATION",
                f"registered shared declaration is absent from the frozen core source: {name}",
                declaration=name,
            ))
            continue
        raw_mapping = flat_declarations.get(name)
        if raw_mapping is None:
            broken.append(_broken(
                "MISSING_CLAIM_MAPPING",
                f"shared Lean declaration has no core declaration mapping: {name}",
                declaration=name,
            ))
            continue
        mapping = dict(raw_mapping)
        # Declaration-level core mappings are authoritative.  Do not inflate a
        # declaration to every claim owned by its dependency: that makes a
        # registry look complete while destroying the exact code-to-claim
        # relationship.  IMPLEMENTATION_HELPER support chains are resolved by
        # the normal mapping traversal below.
        mapping["claimRefs"] = [
            {"unitId": unit_id, "claimId": claim_id}
            for unit_id, claim_id in sorted(
                ref for ref in _claim_refs(mapping.get("claimRefs"))
                if ref[0] in unit_ids
            )
        ]
        mappings[name] = mapping
    return core_declared & relevant_names, mappings, broken


def group_coverage_test(
    unit_id: str,
    semantics: dict[str, Any],
    source: str,
    manifest: dict[str, Any],
    *,
    core_source: str | None = None,
    core_manifest: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if (core_source is None) != (core_manifest is None):
        raise ValueError("core_source and core_manifest must be supplied together")
    claims = {
        item.get("claimId"): item
        for item in (semantics.get("semantics") or {}).get("claims", [])
        if isinstance(item, dict) and isinstance(item.get("claimId"), str)
    }
    declared = set(lean_declarations(source))
    mappings = {
        item.get("declaration"): item
        for item in manifest.get("declarations", [])
        if isinstance(item, dict) and isinstance(item.get("declaration"), str)
    }
    if core_source is not None and core_manifest is not None:
        core_declared, core_mappings, _ = _core_claim_mappings(
            {unit_id}, {unit_id: semantics}, manifest, core_source, core_manifest
        )
        declared.update(core_declared)
        mappings.update(core_mappings)
    claim_declarations: dict[str, set[str]] = defaultdict(set)
    ignored: list[dict[str, str]] = []
    for name in sorted(declared & set(mappings)):
        for ref_unit, claim_id in _mapping_claim_refs(name, mappings, ignored):
            if ref_unit == unit_id and claim_id in claims:
                claim_declarations[claim_id].add(name)
    covered: list[dict[str, Any]] = []
    uncovered: list[dict[str, Any]] = []
    for claim_id, claim in sorted(claims.items()):
        declarations = sorted(claim_declarations.get(claim_id, set()))
        item = {"itemType": "SEMANTIC_CLAIM", "itemId": claim_id, "unitId": unit_id, "declarations": declarations}
        (covered if declarations else uncovered).append(item)
    evidence_claims: dict[str, set[str]] = defaultdict(set)
    evidence_declarations: dict[str, set[str]] = defaultdict(set)
    for claim_id, claim in claims.items():
        for evidence_id in claim.get("evidenceIds", []):
            if isinstance(evidence_id, str):
                evidence_claims[evidence_id].add(claim_id)
                evidence_declarations[evidence_id].update(claim_declarations.get(claim_id, set()))
    for evidence_id in sorted(evidence_claims):
        declarations = sorted(evidence_declarations[evidence_id])
        item = {"itemType": "EVIDENCE", "itemId": evidence_id, "unitId": unit_id, "semanticClaimIds": sorted(evidence_claims[evidence_id]), "declarations": declarations}
        (covered if declarations else uncovered).append(item)
    return {"status": "PASS" if not uncovered else "FAIL", "covered": covered, "uncovered": uncovered}


def group_traceability_test(
    plan: dict[str, Any], bundles_by_unit: dict[str, dict[str, Any]],
    semantics_by_unit: dict[str, dict[str, Any]], source: str,
    manifest: dict[str, Any], database: Path, *,
    core_source: str | None = None,
    core_manifest: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if (core_source is None) != (core_manifest is None):
        raise ValueError("core_source and core_manifest must be supplied together")
    broken: list[dict[str, str]] = []
    declared = set(lean_declarations(source))
    frozen_core_declarations: set[str] = set()
    mappings: dict[str, dict[str, Any]] = {
        item.get("declaration"): item
        for item in manifest.get("declarations", [])
        if isinstance(item, dict) and isinstance(item.get("declaration"), str)
    }
    if core_source is not None and core_manifest is not None:
        core_declared, core_mappings, core_broken = _core_claim_mappings(
            set(semantics_by_unit), semantics_by_unit, manifest, core_source, core_manifest
        )
        frozen_core_declarations = set(core_declared)
        broken.extend(core_broken)
        for name in sorted(declared & core_declared):
            broken.append(_broken(
                "SHARED_DECLARATION_REDEFINED",
                f"group source redefines a declaration owned by the frozen shared core: {name}",
                declaration=name,
            ))
        declared.update(core_declared)
        for name, mapping in core_mappings.items():
            if name not in mappings:
                mappings[name] = mapping
    for name in sorted(declared - set(mappings)):
        broken.append(_broken("MISSING_CLAIM_MAPPING", f"Lean declaration has no semantic/claim mapping: {name}", declaration=name))
    for name in sorted(set(mappings) - declared):
        broken.append(_broken("MISSING_LEAN_DECLARATION", f"mapped Lean declaration is absent from the group Lean file: {name}", declaration=name))

    claims_by_unit = {
        unit_id: {
            item.get("claimId"): item
            for item in (semantics.get("semantics") or {}).get("claims", [])
            if isinstance(item, dict) and isinstance(item.get("claimId"), str)
        }
        for unit_id, semantics in semantics_by_unit.items()
    }
    evidence_by_unit = {
        unit_id: {
            _record_id(item): item
            for item in _bundle_records(bundle)
            if _record_id(item) is not None
        }
        for unit_id, bundle in bundles_by_unit.items()
    }
    valid: list[dict[str, Any]] = []
    referenced_evidence: set[tuple[str, str]] = set()
    for name in sorted(declared & set(mappings)):
        local: list[dict[str, str]] = []
        refs = _mapping_claim_refs(name, mappings, local)
        broken.extend(local)
        valid_refs: list[dict[str, Any]] = []
        # A frozen-core declaration can be a representation dependency whose
        # authoritative claim mapping belongs to an earlier unit recorded by
        # the immutable core.  Its mapping is deliberately filtered to this
        # group's units above, so an empty local result is not an unmapped
        # declaration.  Current-unit coverage is still checked independently,
        # while genuinely unmapped group-local declarations remain failures.
        if not refs and name not in frozen_core_declarations:
            broken.append(_broken("MISSING_CLAIM_MAPPING", f"Lean declaration does not resolve to a semantic claim: {name}", declaration=name))
        for unit_id, claim_id in sorted(refs):
            claim = claims_by_unit.get(unit_id, {}).get(claim_id)
            if claim is None:
                broken.append(_broken("MISSING_SEMANTIC_CLAIM", f"mapping references a nonexistent semantic claim: {unit_id}/{claim_id}", declaration=name, unitId=unit_id, semanticClaimId=claim_id))
                continue
            evidence_ids = [item for item in claim.get("evidenceIds", []) if isinstance(item, str)]
            if claim.get("kind") in EVIDENCE_REQUIRED_KINDS and not evidence_ids:
                broken.append(_broken("MISSING_CLAIM_EVIDENCE", f"semantic claim requires evidence but cites none: {unit_id}/{claim_id}", unitId=unit_id, semanticClaimId=claim_id))
            for evidence_id in evidence_ids:
                if evidence_id not in evidence_by_unit.get(unit_id, {}):
                    broken.append(_broken("MISSING_EVIDENCE", f"semantic claim references nonexistent evidence: {unit_id}/{evidence_id}", unitId=unit_id, semanticClaimId=claim_id, evidenceId=evidence_id))
                else:
                    referenced_evidence.add((unit_id, evidence_id))
            valid_refs.append({"unitId": unit_id, "claimId": claim_id, "evidenceIds": sorted(evidence_ids)})
        if valid_refs and not local:
            valid.append({"declaration": name, "claimRefs": valid_refs})

    expected_artifacts = {
        unit_id: semantics_artifact_hash(semantics)
        for unit_id, semantics in semantics_by_unit.items()
    }
    recorded_artifacts = {
        item.get("unitId"): item.get("artifactHash")
        for item in manifest.get("semanticsArtifacts", []) if isinstance(item, dict)
    }
    if recorded_artifacts != expected_artifacts:
        broken.append(_broken("SEMANTICS_ARTIFACT_HASH_MISMATCH", "group manifest does not reference the current Phase-4 artifacts"))
    expected_unit_ids = {str(unit["unitId"]) for unit in plan.get("requestedUnits", []) if str(unit["unitId"]) in semantics_by_unit}
    if set((manifest.get("group") or {}).get("unitIds", [])) != expected_unit_ids:
        broken.append(_broken("ARTIFACT_BOUNDARY_MISMATCH", "group manifest unit set does not match its semantic inputs"))

    with connect(database, read_only=True) as connection:
        if semantic_digest(connection) != plan.get("sourceDatabaseDigest"):
            broken.append(_broken("SOURCE_DATABASE_DIGEST_MISMATCH", "the Phase-1 index does not match the plan source digest"))
        for unit_id, semantics in semantics_by_unit.items():
            bundle = bundles_by_unit[unit_id]
            expected_unit = next((unit for unit in plan.get("requestedUnits", []) if unit.get("unitId") == unit_id), None)
            for artifact_name, artifact in (("evidence", bundle), ("semantics", semantics)):
                if artifact.get("planRunId") != plan.get("planRunId") or artifact.get("language") != plan.get("language") or artifact.get("version") != plan.get("version") or artifact.get("unit") != expected_unit:
                    broken.append(_broken("ARTIFACT_BOUNDARY_MISMATCH", f"{artifact_name} artifact does not match plan unit {unit_id}", unitId=unit_id))
            if semantics.get("evidenceBundleHash") != evidence_bundle_hash(bundle):
                broken.append(_broken("EVIDENCE_BUNDLE_HASH_MISMATCH", f"semantic artifact does not reference current evidence for {unit_id}", unitId=unit_id))
        for unit_id, evidence_id in sorted(referenced_evidence):
            record = evidence_by_unit[unit_id][evidence_id]
            if record.get("unitId") != unit_id:
                broken.append(_broken("EVIDENCE_UNIT_MISMATCH", f"evidence belongs to another unit: {evidence_id}", unitId=unit_id, evidenceId=evidence_id))
            if evidence_id.startswith("resolution:"):
                _resolution_provenance(record, broken)
            else:
                _source_provenance(connection, record, broken)

    unique = {tuple(sorted(item.items())): item for item in broken}
    ordered = [unique[key] for key in sorted(unique)]
    return {"status": "PASS" if not ordered else "FAIL", "validMappings": valid if not ordered else [], "brokenMappings": ordered}


def _source_provenance(
    connection: sqlite3.Connection,
    evidence: dict[str, Any],
    broken: list[dict[str, str]],
) -> None:
    evidence_id = str(evidence.get("evidenceId", ""))
    document_id = evidence.get("documentId")
    document = connection.execute(
        "SELECT document_id, source_type, sha256, local_path, official_url "
        "FROM documents WHERE document_id = ?",
        (document_id,),
    ).fetchone()
    if document is None:
        broken.append(_broken(
            "MISSING_SOURCE_DOCUMENT",
            f"evidence references a nonexistent Phase-1 document: {document_id}",
            evidenceId=evidence_id,
        ))
        return
    if (
        document["sha256"] != evidence.get("documentSha256")
        or document["source_type"] != evidence.get("sourceType")
        or document["local_path"] != evidence.get("sourcePath")
        or document["official_url"] != evidence.get("officialUrl")
    ):
        broken.append(_broken(
            "SOURCE_DOCUMENT_MISMATCH",
            f"evidence source identity differs from Phase 1: {document_id}",
            evidenceId=evidence_id,
        ))

    node_ids = evidence.get("sourceNodeIds")
    if not isinstance(node_ids, list) or not node_ids:
        broken.append(_broken(
            "MISSING_SOURCE_NODES",
            "evidence has no Phase-1 source node provenance",
            evidenceId=evidence_id,
        ))
        node_ids = []
    valid_nodes: set[str] = set()
    for node_id in node_ids:
        row = connection.execute(
            "SELECT document_id FROM nodes WHERE node_id = ?", (node_id,)
        ).fetchone()
        if row is None:
            broken.append(_broken(
                "MISSING_SOURCE_NODE",
                f"evidence references a nonexistent Phase-1 source node: {node_id}",
                evidenceId=evidence_id,
                sourceNodeId=str(node_id),
            ))
        elif row["document_id"] != document_id:
            broken.append(_broken(
                "SOURCE_NODE_DOCUMENT_MISMATCH",
                f"source node belongs to a different document: {node_id}",
                evidenceId=evidence_id,
                sourceNodeId=str(node_id),
            ))
        else:
            valid_nodes.add(str(node_id))

    span_ids = evidence.get("sourceSpanIds")
    if not isinstance(span_ids, list):
        broken.append(_broken(
            "INVALID_SOURCE_SPANS",
            "evidence sourceSpanIds is not an array",
            evidenceId=evidence_id,
        ))
        span_ids = []
    for span_id in span_ids:
        row = connection.execute(
            "SELECT node_id, document_id FROM source_spans WHERE span_id = ?", (span_id,)
        ).fetchone()
        if row is None:
            broken.append(_broken(
                "MISSING_SOURCE_SPAN",
                f"evidence references a nonexistent Phase-1 source span: {span_id}",
                evidenceId=evidence_id,
                sourceSpanId=str(span_id),
            ))
        elif row["node_id"] not in valid_nodes or row["document_id"] != document_id:
            broken.append(_broken(
                "SOURCE_SPAN_MISMATCH",
                f"source span does not belong to the evidence source nodes: {span_id}",
                evidenceId=evidence_id,
                sourceSpanId=str(span_id),
            ))

    fragments = evidence.get("provenance")
    if not isinstance(fragments, list) or not fragments:
        broken.append(_broken(
            "MISSING_PROVENANCE_FRAGMENT",
            "evidence has no source provenance fragments",
            evidenceId=evidence_id,
        ))
        return
    fragment_nodes = {
        item.get("sourceNodeId") for item in fragments if isinstance(item, dict)
    }
    nested_span_ids: set[str] = set()
    for fragment in fragments:
        if not isinstance(fragment, dict):
            continue
        fragment_node = fragment.get("sourceNodeId")
        if fragment_node not in node_ids:
            broken.append(_broken(
                "PROVENANCE_NODE_MISMATCH",
                f"provenance fragment is outside the evidence source nodes: {fragment_node}",
                evidenceId=evidence_id,
                sourceNodeId=str(fragment_node),
            ))
        source_spans = fragment.get("sourceSpans")
        if not isinstance(source_spans, list):
            broken.append(_broken(
                "INVALID_PROVENANCE_SPANS",
                f"provenance fragment has invalid source spans: {fragment_node}",
                evidenceId=evidence_id,
                sourceNodeId=str(fragment_node),
            ))
            continue
        for span in source_spans:
            span_id = span.get("spanId") if isinstance(span, dict) else None
            if not isinstance(span_id, str):
                broken.append(_broken(
                    "INVALID_PROVENANCE_SPAN",
                    f"provenance fragment contains an invalid span: {fragment_node}",
                    evidenceId=evidence_id,
                    sourceNodeId=str(fragment_node),
                ))
                continue
            nested_span_ids.add(span_id)
            row = connection.execute(
                "SELECT node_id, document_id FROM source_spans WHERE span_id = ?", (span_id,)
            ).fetchone()
            if row is None:
                broken.append(_broken(
                    "MISSING_SOURCE_SPAN",
                    f"provenance references a nonexistent Phase-1 source span: {span_id}",
                    evidenceId=evidence_id,
                    sourceSpanId=span_id,
                ))
            elif row["node_id"] != fragment_node or row["document_id"] != document_id:
                broken.append(_broken(
                    "SOURCE_SPAN_MISMATCH",
                    f"provenance span does not belong to its source node: {span_id}",
                    evidenceId=evidence_id,
                    sourceSpanId=span_id,
                ))
    for node_id in node_ids:
        if node_id not in fragment_nodes:
            broken.append(_broken(
                "MISSING_NODE_PROVENANCE",
                f"source node has no provenance fragment: {node_id}",
                evidenceId=evidence_id,
                sourceNodeId=str(node_id),
            ))
    if span_ids and nested_span_ids != set(span_ids):
        broken.append(_broken(
            "PROVENANCE_SPAN_MISMATCH",
            "evidence sourceSpanIds differ from its provenance fragments",
            evidenceId=evidence_id,
        ))


def _resolution_provenance(
    resolution: dict[str, Any], broken: list[dict[str, str]]
) -> None:
    resolution_id = str(resolution.get("resolutionId", ""))
    source = resolution.get("sourceKind")
    if resolution.get("nonNormative") is not True:
        broken.append(_broken(
            "MISSING_NON_NORMATIVE_FLAG",
            f"supplemental resolution is not flagged non-normative: {resolution_id}",
            evidenceId=resolution_id,
        ))
    if source not in {"INTERNET", "RUNTIME", "LLM_REASONING"}:
        broken.append(_broken(
            "INVALID_RESOLUTION_SOURCE",
            f"supplemental resolution has an invalid source: {resolution_id}",
            evidenceId=resolution_id,
        ))
    provenance = resolution.get("provenance")
    if not isinstance(provenance, dict):
        broken.append(_broken(
            "INVALID_RESOLUTION_PROVENANCE",
            f"supplemental resolution has no provenance: {resolution_id}",
            evidenceId=resolution_id,
        ))
        return
    if source == "INTERNET" and (
        not isinstance(provenance.get("url"), str)
        or not provenance["url"].startswith(("https://", "http://"))
        or not isinstance(provenance.get("excerpt"), str)
        or not normalize_text(provenance["excerpt"])
    ):
        broken.append(_broken(
            "INCOMPLETE_INTERNET_PROVENANCE",
            f"internet resolution lacks URL or excerpt: {resolution_id}",
            evidenceId=resolution_id,
        ))
    if source == "RUNTIME" and any(
        field not in provenance
        for field in ("probeId", "adapter", "request", "exitCode", "stdout", "stderr")
    ):
        broken.append(_broken(
            "INCOMPLETE_RUNTIME_PROVENANCE",
            f"runtime resolution lacks a probe ID: {resolution_id}",
            evidenceId=resolution_id,
        ))
    if source == "LLM_REASONING" and (
        not isinstance(provenance.get("model"), str)
        or not isinstance(provenance.get("reasoning"), str)
    ):
        broken.append(_broken(
            "INCOMPLETE_LLM_PROVENANCE",
            f"LLM resolution lacks model identity: {resolution_id}",
            evidenceId=resolution_id,
        ))
    identity = {
        "questionId": resolution.get("questionId"),
        "sourceKind": source,
        "role": resolution.get("role"),
        "statement": normalize_text(resolution.get("statement", ""))
        if isinstance(resolution.get("statement"), str) else "",
        "rationale": normalize_text(resolution.get("rationale", ""))
        if isinstance(resolution.get("rationale"), str) else "",
        "provenance": provenance,
    }
    expected_id = stable_id("resolution", canonical_json(identity), length=32)
    if resolution_id != expected_id:
        broken.append(_broken(
            "RESOLUTION_ID_MISMATCH",
            f"supplemental resolution ID does not match its content: {resolution_id}",
            evidenceId=resolution_id,
        ))


def coverage_test(semantics: dict[str, Any], source: str, manifest: dict[str, Any]) -> dict[str, Any]:
    claims = {
        item.get("claimId"): item
        for item in (semantics.get("semantics") or {}).get("claims", [])
        if isinstance(item, dict) and isinstance(item.get("claimId"), str)
    }
    declared = set(lean_declarations(source))
    mappings = {
        item.get("declaration"): item
        for item in manifest.get("declarations", [])
        if isinstance(item, dict) and isinstance(item.get("declaration"), str)
    }
    claim_declarations: dict[str, set[str]] = defaultdict(set)
    ignored_broken: list[dict[str, str]] = []
    for name in sorted(declared & set(mappings)):
        for claim_id in _mapping_claims(name, mappings, ignored_broken):
            if claim_id in claims:
                claim_declarations[claim_id].add(name)

    covered: list[dict[str, Any]] = []
    uncovered: list[dict[str, Any]] = []
    for claim_id, claim in sorted(claims.items()):
        declarations = sorted(claim_declarations.get(claim_id, set()))
        item = {
            "itemType": "SEMANTIC_CLAIM",
            "itemId": claim_id,
            "declarations": declarations,
        }
        (covered if declarations else uncovered).append(item)

    evidence_claims: dict[str, set[str]] = defaultdict(set)
    evidence_declarations: dict[str, set[str]] = defaultdict(set)
    for claim_id, claim in claims.items():
        for evidence_id in claim.get("evidenceIds", []):
            if not isinstance(evidence_id, str):
                continue
            evidence_claims[evidence_id].add(claim_id)
            evidence_declarations[evidence_id].update(claim_declarations.get(claim_id, set()))
    for evidence_id in sorted(evidence_claims):
        declarations = sorted(evidence_declarations[evidence_id])
        item = {
            "itemType": "EVIDENCE",
            "itemId": evidence_id,
            "semanticClaimIds": sorted(evidence_claims[evidence_id]),
            "declarations": declarations,
        }
        (covered if declarations else uncovered).append(item)
    return {
        "status": "PASS" if not uncovered else "FAIL",
        "covered": covered,
        "uncovered": uncovered,
    }


def traceability_test(
    plan: dict[str, Any],
    bundle: dict[str, Any],
    semantics: dict[str, Any],
    source: str,
    manifest: dict[str, Any],
    database: Path,
) -> dict[str, Any]:
    broken: list[dict[str, str]] = []
    declared = set(lean_declarations(source))
    raw_mappings = [item for item in manifest.get("declarations", []) if isinstance(item, dict)]
    mappings: dict[str, dict[str, Any]] = {}
    for item in raw_mappings:
        name = item.get("declaration")
        if not isinstance(name, str):
            continue
        if name in mappings:
            broken.append(_broken(
                "DUPLICATE_DECLARATION_MAPPING",
                f"Lean declaration has duplicate mappings: {name}",
                declaration=name,
            ))
        else:
            mappings[name] = item

    for name in sorted(declared - set(mappings)):
        broken.append(_broken(
            "MISSING_CLAIM_MAPPING",
            f"Lean declaration has no semantic/claim mapping: {name}",
            declaration=name,
        ))
    for name in sorted(set(mappings) - declared):
        broken.append(_broken(
            "MISSING_LEAN_DECLARATION",
            f"mapped Lean declaration is absent from Unit.lean: {name}",
            declaration=name,
        ))

    claims = {
        item.get("claimId"): item
        for item in (semantics.get("semantics") or {}).get("claims", [])
        if isinstance(item, dict) and isinstance(item.get("claimId"), str)
    }
    evidence = {
        _record_id(item): item
        for item in _bundle_records(bundle)
        if _record_id(item) is not None
    }
    for claim_id, claim in sorted(claims.items()):
        cited = claim.get("evidenceIds")
        if not isinstance(cited, list):
            cited = []
        if claim.get("kind") in EVIDENCE_REQUIRED_KINDS and not cited:
            broken.append(_broken(
                "MISSING_CLAIM_EVIDENCE",
                f"semantic claim requires evidence but cites none: {claim_id}",
                semanticClaimId=claim_id,
            ))
        for evidence_id in cited:
            if isinstance(evidence_id, str) and evidence_id not in evidence:
                broken.append(_broken(
                    "MISSING_EVIDENCE",
                    f"semantic claim references nonexistent evidence: {evidence_id}",
                    semanticClaimId=claim_id,
                    evidenceId=evidence_id,
                ))

    valid: list[dict[str, Any]] = []
    for name in sorted(declared & set(mappings)):
        local_broken: list[dict[str, str]] = []
        claim_ids = _mapping_claims(name, mappings, local_broken)
        broken.extend(local_broken)
        evidence_ids: set[str] = set()
        if not claim_ids:
            broken.append(_broken(
                "MISSING_CLAIM_MAPPING",
                f"Lean declaration does not resolve to a semantic claim: {name}",
                declaration=name,
            ))
        for claim_id in sorted(claim_ids):
            claim = claims.get(claim_id)
            if claim is None:
                broken.append(_broken(
                    "MISSING_SEMANTIC_CLAIM",
                    f"mapping references a nonexistent semantic claim: {claim_id}",
                    declaration=name,
                    semanticClaimId=claim_id,
                ))
                continue
            cited = claim.get("evidenceIds")
            if not isinstance(cited, list):
                cited = []
            for evidence_id in cited:
                if not isinstance(evidence_id, str):
                    continue
                if evidence_id in evidence:
                    evidence_ids.add(evidence_id)
        if not local_broken and claim_ids and all(claim_id in claims for claim_id in claim_ids):
            valid.append({
                "declaration": name,
                "semanticClaimIds": sorted(claim_ids),
                "evidenceIds": sorted(evidence_ids),
            })

    if manifest.get("semanticsArtifactHash") != semantics_artifact_hash(semantics):
        broken.append(_broken(
            "SEMANTICS_ARTIFACT_HASH_MISMATCH",
            "translation manifest does not reference the current Phase-4 artifact",
        ))
    if semantics.get("evidenceBundleHash") != evidence_bundle_hash(bundle):
        broken.append(_broken(
            "EVIDENCE_BUNDLE_HASH_MISMATCH",
            "semantic artifact does not reference the current Phase-3 evidence bundle",
        ))
    expected_units = [
        item for item in plan.get("requestedUnits", [])
        if item.get("unitId") == manifest.get("unit", {}).get("unitId")
    ]
    expected_unit = expected_units[0] if len(expected_units) == 1 else None
    for artifact_name, artifact in (("evidence", bundle), ("semantics", semantics), ("translation", manifest)):
        if (
            artifact.get("planRunId") != plan.get("planRunId")
            or artifact.get("language") != plan.get("language")
            or artifact.get("version") != plan.get("version")
            or artifact.get("unit") != expected_unit
        ):
            broken.append(_broken(
                "ARTIFACT_BOUNDARY_MISMATCH",
                f"{artifact_name} artifact does not match the checked plan/unit",
            ))

    with connect(database, read_only=True) as connection:
        if (
            bundle.get("sourceDatabaseDigest") != plan.get("sourceDatabaseDigest")
            or semantic_digest(connection) != plan.get("sourceDatabaseDigest")
        ):
            broken.append(_broken(
                "SOURCE_DATABASE_DIGEST_MISMATCH",
                "the Phase-1 index does not match the plan source digest",
            ))
        referenced_evidence = {
            item_id
            for mapping in valid
            for item_id in mapping["evidenceIds"]
        }
        for evidence_id in sorted(referenced_evidence):
            record = evidence[evidence_id]
            if record.get("unitId") != manifest.get("unit", {}).get("unitId"):
                broken.append(_broken(
                    "EVIDENCE_UNIT_MISMATCH",
                    f"evidence belongs to another unit: {evidence_id}",
                    evidenceId=evidence_id,
                ))
            if evidence_id.startswith("resolution:"):
                _resolution_provenance(record, broken)
            else:
                _source_provenance(connection, record, broken)

    unique_broken = {
        tuple(sorted(item.items())): item for item in broken
    }
    ordered_broken = [unique_broken[key] for key in sorted(unique_broken)]
    broken_declarations = {item.get("declaration") for item in ordered_broken}
    broken_claims = {item.get("semanticClaimId") for item in ordered_broken}
    broken_evidence = {item.get("evidenceId") for item in ordered_broken}
    global_chain_broken = any(
        item["code"] in {
            "SEMANTICS_ARTIFACT_HASH_MISMATCH", "EVIDENCE_BUNDLE_HASH_MISMATCH",
            "ARTIFACT_BOUNDARY_MISMATCH", "SOURCE_DATABASE_DIGEST_MISMATCH",
        }
        for item in ordered_broken
    )
    valid = [
        item for item in valid
        if not global_chain_broken
        and item["declaration"] not in broken_declarations
        and not (set(item["semanticClaimIds"]) & broken_claims)
        and not (set(item["evidenceIds"]) & broken_evidence)
    ]
    return {
        "status": "PASS" if not ordered_broken else "FAIL",
        "validMappings": valid,
        "brokenMappings": ordered_broken,
    }


def logical_tests(
    plan: dict[str, Any],
    bundle: dict[str, Any],
    semantics: dict[str, Any],
    source: str,
    manifest: dict[str, Any],
    database: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    return (
        coverage_test(semantics, source, manifest),
        traceability_test(plan, bundle, semantics, source, manifest, database),
    )
