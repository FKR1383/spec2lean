from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .models import (
    DECLARATION_ROLES,
    LEAN_LANGUAGE,
    LEAN_VERSION,
    TRANSLATION_SCHEMA_VERSION,
    SUPPORTED_TRANSLATOR_CONFIGURATIONS,
    TranslationGroupScope,
)


SUBMISSION_FIELDS = {"leanSource", "declarations", "sharedUses"}
MAPPING_FIELDS = {"declaration", "role", "claimRefs", "supportsDeclarations"}
SHARED_USE_FIELDS = {"dependencyId", "leanDeclarations"}
LEAN_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_']*(?:\.[A-Za-z_][A-Za-z0-9_']*)*$")
DECLARATION = re.compile(
    r"^\s*(?:(?:private|protected|noncomputable|partial)\s+)*"
    r"(def|abbrev|opaque|theorem|lemma|structure|inductive|class|instance)\s+"
    r"([A-Za-z_][A-Za-z0-9_']*(?:\.[A-Za-z_][A-Za-z0-9_']*)*)\b"
)
NAMESPACE = re.compile(r"^\s*namespace\s+([A-Za-z_][A-Za-z0-9_']*(?:\.[A-Za-z_][A-Za-z0-9_']*)*)\s*$")
SECTION = re.compile(r"^\s*section(?:\s+[A-Za-z_][A-Za-z0-9_']*)?\s*$")
END = re.compile(r"^\s*end(?:\s+[A-Za-z_][A-Za-z0-9_'.]*)?\s*$")
FORBIDDEN = (
    ("FORBIDDEN_SORRY", re.compile(r"\bsorry\b"), "Lean source contains forbidden 'sorry'"),
    ("FORBIDDEN_ADMIT", re.compile(r"\badmit\b"), "Lean source contains forbidden 'admit'"),
    ("FORBIDDEN_AXIOM", re.compile(r"\baxioms?\b"), "Lean source declares a forbidden axiom"),
    ("FORBIDDEN_CONSTANT", re.compile(r"\bconstants?\b"), "Lean source declares a forbidden constant/axiom"),
    ("FORBIDDEN_UNSAFE", re.compile(r"\bunsafe\b"), "Lean source contains forbidden unsafe code"),
    ("FORBIDDEN_PARTIAL", re.compile(r"\bpartial\b"), "Lean source contains a forbidden partial definition"),
)


def _shared_claims_by_dependency(
    scope: TranslationGroupScope, semantics_by_unit: dict[str, dict[str, Any]]
) -> dict[str, set[tuple[str, str]]]:
    required = set(scope.shared_dependency_ids)
    result: dict[str, set[tuple[str, str]]] = {dependency_id: set() for dependency_id in required}
    for unit_id, artifact in semantics_by_unit.items():
        claims = {
            item.get("claimId")
            for item in (artifact.get("semantics") or {}).get("claims", [])
            if isinstance(item, dict) and isinstance(item.get("claimId"), str)
        }
        for dependency in (artifact.get("semantics") or {}).get("dependencies", []):
            if not isinstance(dependency, dict):
                continue
            dependency_id = dependency.get("dependencyId")
            if dependency_id not in required:
                continue
            for claim_id in dependency.get("semanticClaimIds", []):
                if isinstance(claim_id, str) and claim_id in claims:
                    result[str(dependency_id)].add((unit_id, claim_id))
    return result


def _core_concepts(scope: TranslationGroupScope) -> dict[str, dict[str, Any]]:
    if scope.shared_core is None:
        return {}
    return {
        str(item.get("dependencyId")): item
        for item in scope.shared_core.get("concepts", [])
        if isinstance(item, dict) and isinstance(item.get("dependencyId"), str)
    }


def _core_reference(core: dict[str, Any] | None) -> dict[str, str] | None:
    if core is None:
        return None
    return {
        key: str(core[key])
        for key in ("coreRunId", "manifestHash", "sourceHash", "leanModule")
    }


def _diagnostic(code: str, message: str, path: str = "$") -> dict[str, str]:
    return {"code": code, "message": message, "path": path}


def has_genuine_execution_semantics(semantic_payload: Any) -> bool:
    """Return whether Phase 4 records behavior beyond a pure result operation.

    Destination-shaped syntax, operands, and results deliberately do not affect this
    decision.  In the current Phase-4 schema, state effects and predication are the
    explicit execution-level components.
    """
    if not isinstance(semantic_payload, dict):
        return False
    state_effects = semantic_payload.get("stateEffects")
    return (
        isinstance(state_effects, list) and bool(state_effects)
    ) or isinstance(semantic_payload.get("predication"), dict)


def _without_comments_and_strings(source: str) -> str:
    """Blank Lean comments and strings while preserving newlines for line parsing."""
    result: list[str] = []
    index = 0
    block_depth = 0
    in_string = False
    while index < len(source):
        pair = source[index:index + 2]
        char = source[index]
        if block_depth:
            if pair == "/-":
                block_depth += 1
                result.extend("  ")
                index += 2
            elif pair == "-/":
                block_depth -= 1
                result.extend("  ")
                index += 2
            else:
                result.append("\n" if char == "\n" else " ")
                index += 1
            continue
        if in_string:
            if char == "\\" and index + 1 < len(source):
                result.extend("  ")
                index += 2
            elif char == '"':
                in_string = False
                result.append(" ")
                index += 1
            else:
                result.append("\n" if char == "\n" else " ")
                index += 1
            continue
        if pair == "--":
            end = source.find("\n", index)
            if end < 0:
                result.extend(" " * (len(source) - index))
                break
            result.extend(" " * (end - index))
            result.append("\n")
            index = end + 1
        elif pair == "/-":
            block_depth = 1
            result.extend("  ")
            index += 2
        elif char == '"':
            in_string = True
            result.append(" ")
            index += 1
        else:
            result.append(char)
            index += 1
    return "".join(result)


def _lean_declaration_entries(source: str) -> list[tuple[str, str, int]]:
    clean = _without_comments_and_strings(source)
    contexts: list[list[str]] = []
    found: list[tuple[str, str, int]] = []
    for line_number, line in enumerate(clean.splitlines(), start=1):
        namespace = NAMESPACE.match(line)
        if namespace:
            contexts.append(namespace.group(1).split("."))
            continue
        if SECTION.match(line):
            contexts.append([])
            continue
        if END.match(line):
            if contexts:
                contexts.pop()
            continue
        declaration = DECLARATION.match(line)
        if not declaration:
            continue
        kind, name = declaration.groups()
        prefix = [part for context in contexts for part in context]
        qualified = ".".join([*prefix, name]) if prefix else name
        found.append((qualified, kind, line_number))
    return found


def lean_declarations(source: str) -> dict[str, str]:
    return {
        name: kind
        for name, kind, _line_number in _lean_declaration_entries(source)
    }


def declaration_source_ranges(
    source: str, lean_file: str,
) -> dict[str, dict[str, str | int]]:
    """Locate named declarations after Lean source exists.

    The translator never supplies these locations.  A declaration extends from
    its declaration line through the line before the next named declaration (or
    the end of the file), matching the source slices shown by artifact viewers.
    """
    entries = _lean_declaration_entries(source)
    line_count = len(source.splitlines())
    ranges: dict[str, dict[str, str | int]] = {}
    for index, (name, _kind, start_line) in enumerate(entries):
        end_line = (
            entries[index + 1][2] - 1
            if index + 1 < len(entries)
            else line_count
        )
        ranges[name] = {
            "file": lean_file,
            "startLine": start_line,
            "endLine": end_line,
        }
    return ranges


def _is_direct_operation_wrapper(
    source: str, declaration: str, operation_declarations: set[str]
) -> bool:
    """Detect a definition whose entire body is just an OPERATION application."""
    source_range = declaration_source_ranges(source, "<source>").get(declaration)
    if source_range is None:
        return False
    lines = source.splitlines()
    fragment = "\n".join(
        lines[int(source_range["startLine"]) - 1:int(source_range["endLine"])]
    )
    clean = " ".join(_without_comments_and_strings(fragment).split())
    if ":=" not in clean:
        return False
    body = clean.split(":=", 1)[1].strip()
    while body.startswith("(") and body.endswith(")"):
        body = body[1:-1].strip()
    for operation in operation_declarations:
        for spelling in (operation, operation.rsplit(".", 1)[-1]):
            if re.fullmatch(
                rf"{re.escape(spelling)}(?:\s+[A-Za-z_][A-Za-z0-9_'.]*)+",
                body,
            ):
                return True
    return False


def _normalized_definition_body(source: str, declaration: str) -> str | None:
    """Return a conservative normalized body for duplicate-operation checks."""
    source_range = declaration_source_ranges(source, "<source>").get(declaration)
    if source_range is None:
        return None
    lines = source.splitlines()
    fragment = "\n".join(
        lines[int(source_range["startLine"]) - 1:int(source_range["endLine"])]
    )
    clean = " ".join(_without_comments_and_strings(fragment).split())
    if ":=" not in clean:
        return None
    body = clean.split(":=", 1)[1].strip()
    body = re.sub(r"\s+end(?:\s+[A-Za-z_][A-Za-z0-9_'.]*)?\s*$", "", body)
    return body or None


def forbidden_constructs(source: str) -> list[dict[str, str]]:
    clean = _without_comments_and_strings(source)
    return [
        _diagnostic(code, message, "$.leanSource")
        for code, pattern, message in FORBIDDEN
        if pattern.search(clean)
    ]


def validate_submission(
    scope: TranslationGroupScope,
    semantics_by_unit: dict[str, dict[str, Any]],
    submission: Any,
) -> tuple[dict[str, Any] | None, list[dict[str, str]]]:
    diagnostics: list[dict[str, str]] = []
    if not isinstance(submission, dict):
        return None, [_diagnostic("EXPECTED_OBJECT", "translation submission must be an object")]
    for field in sorted(set(submission) - SUBMISSION_FIELDS):
        diagnostics.append(_diagnostic("UNEXPECTED_FIELD", f"unsupported translation field: {field}", f"$.{field}"))
    source = submission.get("leanSource")
    if not isinstance(source, str) or not source.strip():
        diagnostics.append(_diagnostic("EMPTY_LEAN_SOURCE", "leanSource must be non-empty", "$.leanSource"))
        source = ""
    diagnostics.extend(forbidden_constructs(source))
    declared = lean_declarations(source)
    if source and not declared:
        diagnostics.append(_diagnostic("NO_LEAN_DECLARATIONS", "Lean source must contain at least one named declaration", "$.leanSource"))

    core_concepts = _core_concepts(scope)
    core_declarations = {
        declaration
        for concept in core_concepts.values()
        for declaration in concept.get("leanDeclarations", [])
        if isinstance(declaration, str)
    }
    shared_claims = _shared_claims_by_dependency(scope, semantics_by_unit)
    shared_claim_refs = {
        ref for refs in shared_claims.values() for ref in refs
    }
    if scope.shared_core is not None:
        module = str(scope.shared_core["leanModule"])
        imports = {
            value
            for line in _without_comments_and_strings(source).splitlines()
            if (match := re.match(r"^\s*import\s+([^\s]+)\s*$", line))
            for value in (match.group(1),)
        }
        if module not in imports:
            diagnostics.append(_diagnostic(
                "MISSING_SHARED_CORE_IMPORT",
                f"Lean source must import the frozen shared core module exactly: {module}",
                "$.leanSource",
            ))
    for name in sorted(set(declared) & core_declarations):
        diagnostics.append(_diagnostic(
            "SHARED_DECLARATION_REDEFINED",
            f"unit source redeclares a Lean declaration owned by the shared core: {name}",
            "$.leanSource",
        ))

    raw_shared_uses = submission.get("sharedUses", [])
    if not isinstance(raw_shared_uses, list):
        diagnostics.append(_diagnostic("EXPECTED_ARRAY", "sharedUses must be an array", "$.sharedUses"))
        raw_shared_uses = []
    shared_uses: list[dict[str, Any]] = []
    seen_shared: set[str] = set()
    clean_source = _without_comments_and_strings(source)
    for index, raw in enumerate(raw_shared_uses):
        path = f"$.sharedUses[{index}]"
        if not isinstance(raw, dict):
            diagnostics.append(_diagnostic("EXPECTED_OBJECT", "shared use must be an object", path))
            continue
        for field in sorted(set(raw) - SHARED_USE_FIELDS):
            diagnostics.append(_diagnostic("UNEXPECTED_FIELD", f"unsupported shared-use field: {field}", f"{path}.{field}"))
        dependency_id = raw.get("dependencyId")
        if not isinstance(dependency_id, str) or dependency_id not in core_concepts:
            diagnostics.append(_diagnostic(
                "MISSING_SHARED_ABSTRACTION",
                f"shared use does not resolve through the frozen core: {dependency_id!r}",
                f"{path}.dependencyId",
            ))
            continue
        if dependency_id in seen_shared:
            diagnostics.append(_diagnostic(
                "DUPLICATE_SHARED_USE", f"shared dependency is listed twice: {dependency_id}", path
            ))
        seen_shared.add(dependency_id)
        raw_names = raw.get("leanDeclarations")
        if not isinstance(raw_names, list) or not raw_names:
            diagnostics.append(_diagnostic(
                "MISSING_SHARED_DECLARATION_USE",
                "shared use must name at least one registered Lean declaration",
                f"{path}.leanDeclarations",
            ))
            raw_names = []
        registered = {
            item for item in core_concepts[dependency_id].get("leanDeclarations", [])
            if isinstance(item, str)
        }
        names: list[str] = []
        for item_index, name in enumerate(raw_names):
            item_path = f"{path}.leanDeclarations[{item_index}]"
            if not isinstance(name, str) or name not in registered:
                diagnostics.append(_diagnostic(
                    "UNREGISTERED_SHARED_DECLARATION",
                    f"declaration is not registered for {dependency_id}: {name!r}",
                    item_path,
                ))
            elif name in names:
                diagnostics.append(_diagnostic(
                    "DUPLICATE_SHARED_DECLARATION_USE", f"duplicate shared declaration: {name}", item_path
                ))
            else:
                names.append(name)
        if names and not any(re.search(rf"(?<![A-Za-z0-9_']){re.escape(name)}(?![A-Za-z0-9_'])", clean_source) for name in names):
            diagnostics.append(_diagnostic(
                "UNUSED_SHARED_ABSTRACTION",
                f"unit source does not reference a registered declaration for {dependency_id}",
                f"{path}.leanDeclarations",
            ))
        refs = [
            {"unitId": unit_id, "claimId": claim_id}
            for unit_id, claim_id in sorted(shared_claims.get(dependency_id, set()))
        ]
        if not refs:
            diagnostics.append(_diagnostic(
                "MISSING_SHARED_SEMANTIC_MAPPING",
                f"shared dependency has no Phase-4 semantic claim linkage: {dependency_id}",
                path,
            ))
        shared_uses.append({
            "dependencyId": dependency_id,
            "leanDeclarations": names,
            "claimRefs": refs,
        })
    missing_shared = sorted(set(core_concepts) - seen_shared)
    if missing_shared:
        diagnostics.append(_diagnostic(
            "MISSING_SHARED_USE",
            f"every group-required shared dependency must be reused; missing={missing_shared}",
            "$.sharedUses",
        ))
    if scope.shared_core is None and raw_shared_uses:
        diagnostics.append(_diagnostic(
            "UNEXPECTED_SHARED_USE", "sharedUses requires a frozen shared core", "$.sharedUses"
        ))

    raw_mappings = submission.get("declarations")
    if not isinstance(raw_mappings, list):
        diagnostics.append(_diagnostic("EXPECTED_ARRAY", "declarations must be an array", "$.declarations"))
        raw_mappings = []
    known_claims = set(scope.semantic_claim_ids)
    mappings: list[dict[str, Any]] = []
    mapping_source_indices: list[int] = []
    mapped_names: set[str] = set()
    roles: set[str] = set()
    for index, raw in enumerate(raw_mappings):
        path = f"$.declarations[{index}]"
        if not isinstance(raw, dict):
            diagnostics.append(_diagnostic("EXPECTED_OBJECT", "declaration mapping must be an object", path))
            continue
        for field in sorted(set(raw) - MAPPING_FIELDS):
            diagnostics.append(_diagnostic("UNEXPECTED_FIELD", f"unsupported declaration field: {field}", f"{path}.{field}"))
        name, role, raw_claim_refs = raw.get("declaration"), raw.get("role"), raw.get("claimRefs")
        supports = raw.get("supportsDeclarations", [])
        if not isinstance(name, str) or not LEAN_NAME.fullmatch(name):
            diagnostics.append(_diagnostic("INVALID_DECLARATION_NAME", "declaration must be a qualified ASCII Lean identifier", f"{path}.declaration"))
            continue
        if name in mapped_names:
            diagnostics.append(_diagnostic("DUPLICATE_DECLARATION_MAPPING", f"duplicate declaration mapping: {name}", f"{path}.declaration"))
        mapped_names.add(name)
        if name in core_declarations:
            diagnostics.append(_diagnostic(
                "SHARED_DECLARATION_REDEFINED",
                f"unit mapping attempts to own a declaration registered by the shared core: {name}",
                f"{path}.declaration",
            ))
        if name not in declared:
            diagnostics.append(_diagnostic("MISSING_LEAN_DECLARATION", f"mapped declaration is not present in Lean source: {name}", f"{path}.declaration"))
        if role not in DECLARATION_ROLES:
            diagnostics.append(_diagnostic("INVALID_DECLARATION_ROLE", f"role must be one of {DECLARATION_ROLES}", f"{path}.role"))
        else:
            roles.add(role)
            if name in declared and declared[name] in {"structure", "inductive", "class"} and role != "PRIMARY_TYPE":
                diagnostics.append(_diagnostic("TYPE_ROLE_MISMATCH", f"introduced type must use PRIMARY_TYPE role: {name}", f"{path}.role"))
        claim_refs: list[dict[str, str]] = []
        if not isinstance(raw_claim_refs, list):
            diagnostics.append(_diagnostic("INVALID_SEMANTIC_MAPPING", "claimRefs must be an array", f"{path}.claimRefs"))
            raw_claim_refs = []
        seen_refs: set[tuple[str, str]] = set()
        for ref_index, ref in enumerate(raw_claim_refs):
            ref_path = f"{path}.claimRefs[{ref_index}]"
            if not isinstance(ref, dict) or set(ref) != {"unitId", "claimId"}:
                diagnostics.append(_diagnostic("INVALID_CLAIM_REFERENCE", "claim reference must contain exactly unitId and claimId", ref_path))
                continue
            unit_id, claim_id = ref.get("unitId"), ref.get("claimId")
            if not isinstance(unit_id, str) or not isinstance(claim_id, str):
                diagnostics.append(_diagnostic("INVALID_CLAIM_REFERENCE", "unitId and claimId must be strings", ref_path))
                continue
            key = (unit_id, claim_id)
            if key in seen_refs:
                diagnostics.append(_diagnostic("DUPLICATE_SEMANTIC_CLAIM", "claimRefs contains a duplicate", ref_path))
                continue
            seen_refs.add(key)
            if key not in known_claims:
                diagnostics.append(_diagnostic("UNKNOWN_SEMANTIC_CLAIM", f"semantic claim is not in the matching Phase-4 artifact: {unit_id}/{claim_id}", ref_path))
            if key in shared_claim_refs:
                diagnostics.append(_diagnostic(
                    "SHARED_DEPENDENCY_REDEFINED",
                    "shared semantic claims must be covered through the frozen core, not a local declaration: "
                    f"{unit_id}/{claim_id}",
                    ref_path,
                ))
            claim_refs.append({"unitId": unit_id, "claimId": claim_id})
        if not isinstance(supports, list) or not all(isinstance(item, str) and LEAN_NAME.fullmatch(item) for item in supports):
            diagnostics.append(_diagnostic("INVALID_SUPPORT_MAPPING", "supportsDeclarations must be an array of qualified ASCII Lean identifiers", f"{path}.supportsDeclarations"))
            supports = []
        elif len(supports) != len(set(supports)):
            diagnostics.append(_diagnostic("DUPLICATE_SUPPORT_MAPPING", "supportsDeclarations contains a duplicate", f"{path}.supportsDeclarations"))
        support_roles = {"IMPLEMENTATION_HELPER", "OPERATION"}
        if supports and role not in support_roles:
            diagnostics.append(_diagnostic(
                "INVALID_SUPPORT_ROLE",
                "only IMPLEMENTATION_HELPER or OPERATION may use supportsDeclarations",
                f"{path}.supportsDeclarations",
            ))
        if role in support_roles:
            if not claim_refs and not supports:
                subject = "operations" if role == "OPERATION" else "implementation helpers"
                diagnostics.append(_diagnostic(
                    "MISSING_SEMANTIC_MAPPING",
                    f"{subject} require semantic claims or a supported semantic declaration",
                    path,
                ))
        elif not claim_refs:
            diagnostics.append(_diagnostic(
                "MISSING_SEMANTIC_MAPPING",
                "semantic declarations require at least one claim reference",
                f"{path}.claimRefs",
            ))
        mapping = {"declaration": name, "role": role, "claimRefs": claim_refs}
        if supports:
            mapping["supportsDeclarations"] = list(supports)
        mappings.append(mapping)
        mapping_source_indices.append(index)

    mappings_by_name = {item["declaration"]: item for item in mappings}
    core_mappings_by_name = {
        str(item["declaration"]): item
        for item in (scope.shared_core or {}).get("declarations", [])
        if isinstance(item, dict) and isinstance(item.get("declaration"), str)
    }
    used_core_declarations = {
        name
        for use in shared_uses
        for name in use.get("leanDeclarations", [])
        if isinstance(name, str)
    }
    resolvable_mappings = {**core_mappings_by_name, **mappings_by_name}
    for source_index, mapping in zip(mapping_source_indices, mappings):
        for supported in mapping.get("supportsDeclarations", []):
            if supported == mapping["declaration"]:
                diagnostics.append(_diagnostic("SELF_SUPPORT_MAPPING", "a declaration cannot support itself", f"$.declarations[{source_index}].supportsDeclarations"))
            elif supported not in resolvable_mappings:
                diagnostics.append(_diagnostic("UNKNOWN_SUPPORT_DECLARATION", f"supported declaration has no local or frozen-core mapping: {supported}", f"$.declarations[{source_index}].supportsDeclarations"))
            elif supported in core_mappings_by_name and supported not in used_core_declarations:
                diagnostics.append(_diagnostic(
                    "UNBOUND_SHARED_SUPPORT",
                    f"supported frozen-core declaration must be listed in sharedUses: {supported}",
                    f"$.declarations[{source_index}].supportsDeclarations",
                ))
            elif mapping["role"] == "OPERATION" and supported not in core_mappings_by_name:
                diagnostics.append(_diagnostic(
                    "INVALID_OPERATION_SUPPORT",
                    "an OPERATION may delegate only to a declaration in the frozen shared core",
                    f"$.declarations[{source_index}].supportsDeclarations",
                ))

    def resolved_claims(name: str, seen: set[str]) -> set[tuple[str, str]]:
        if name in seen or name not in resolvable_mappings:
            return set()
        mapping = resolvable_mappings[name]
        claims = {(item["unitId"], item["claimId"]) for item in mapping["claimRefs"]}
        for supported in mapping.get("supportsDeclarations", []):
            claims.update(resolved_claims(supported, {*seen, name}))
        return claims

    for index, mapping in enumerate(mappings):
        if not resolved_claims(mapping["declaration"], set()):
            diagnostics.append(_diagnostic("UNRESOLVED_SUPPORT_MAPPING", "declaration traceability does not resolve to a semantic claim", f"$.declarations[{index}]"))

    execution_semantics_by_unit = {
        unit_id: has_genuine_execution_semantics(
            (semantics_by_unit[unit_id].get("semantics") or {})
        )
        for unit_id in scope.unit_ids
    }
    operation_declarations = {
        item["declaration"] for item in mappings if item["role"] == "OPERATION"
    }
    operation_bodies_by_unit: dict[str, dict[str, set[str]]] = {
        unit_id: {} for unit_id in scope.unit_ids
    }
    for mapping in mappings:
        if mapping["role"] != "OPERATION":
            continue
        body = _normalized_definition_body(source, mapping["declaration"])
        if body is None:
            continue
        for unit_id, _claim_id in resolved_claims(mapping["declaration"], set()):
            if unit_id in operation_bodies_by_unit:
                operation_bodies_by_unit[unit_id].setdefault(body, set()).add(
                    mapping["declaration"]
                )
    for unit_id, bodies in operation_bodies_by_unit.items():
        for names in bodies.values():
            if len(names) > 1:
                diagnostics.append(_diagnostic(
                    "DUPLICATE_OPERATION_IMPLEMENTATION",
                    f"instruction {unit_id} has duplicate OPERATION bodies: {sorted(names)}; "
                    "represent modifier conditions as parameters/branches unless they are separate requested units",
                    "$.declarations",
                ))
    for source_index, mapping in zip(mapping_source_indices, mappings):
        if mapping["role"] != "EXECUTION":
            continue
        mapped_units = {
            unit_id
            for unit_id, _claim_id in resolved_claims(mapping["declaration"], set())
            if unit_id in execution_semantics_by_unit
        }
        operation_only_units = sorted(
            unit_id
            for unit_id in mapped_units
            if not execution_semantics_by_unit[unit_id]
        )
        if operation_only_units:
            diagnostics.append(_diagnostic(
                "REDUNDANT_EXECUTION_MAPPING",
                "EXECUTION is permitted only when Phase 4 records state effects or predication "
                "beyond the pure operation; destination-shaped syntax or results do not justify "
                f"an execution wrapper: {operation_only_units}",
                f"$.declarations[{source_index}].role",
            ))
        elif _is_direct_operation_wrapper(
            source, mapping["declaration"], operation_declarations
        ):
            diagnostics.append(_diagnostic(
                "REDUNDANT_EXECUTION_MAPPING",
                "EXECUTION must add source-supported execution behavior; this declaration "
                "is only a direct application of a mapped OPERATION",
                f"$.declarations[{source_index}].role",
            ))

    for name in sorted(set(declared) - mapped_names):
        diagnostics.append(_diagnostic("UNMAPPED_LEAN_DECLARATION", f"named Lean declaration lacks semantic traceability: {name}", "$.declarations"))

    roles_by_unit: dict[str, set[str]] = {unit_id: set() for unit_id in scope.unit_ids}
    for mapping in mappings:
        for unit_id, _claim_id in resolved_claims(mapping["declaration"], set()):
            if unit_id in roles_by_unit and mapping["role"] in DECLARATION_ROLES:
                roles_by_unit[unit_id].add(mapping["role"])
    for unit_id in scope.unit_ids:
        semantic_payload = (semantics_by_unit[unit_id].get("semantics") or {})
        instruction = semantic_payload.get("unitKind") == "INSTRUCTION"
        if instruction and "OPERATION" not in roles_by_unit[unit_id]:
            diagnostics.append(_diagnostic("MISSING_OPERATION_MAPPING", f"instruction {unit_id} requires a mapped OPERATION declaration", "$.declarations"))
        # A destination assignment recorded at value level does not force a state
        # wrapper. Predication cannot be represented by the unconditional pure
        # operation and therefore still requires an execution-level declaration.
        needs_execution = instruction and isinstance(
            semantic_payload.get("predication"), dict
        )
        if needs_execution and "EXECUTION" not in roles_by_unit[unit_id]:
            diagnostics.append(_diagnostic("MISSING_EXECUTION_MAPPING", f"stateful or predicated instruction {unit_id} requires a mapped EXECUTION declaration", "$.declarations"))
    if diagnostics:
        return None, diagnostics
    source_ranges = declaration_source_ranges(source, scope.lean_file)
    manifested_mappings = [
        {**mapping, "sourceRange": source_ranges[mapping["declaration"]]}
        for mapping in mappings
    ]
    return {
        "leanSource": source,
        "manifest": scope.manifest(manifested_mappings, shared_uses),
    }, []


def validate_manifest(
    plan: dict[str, Any], semantics_by_unit: dict[str, dict[str, Any]], source: str, manifest: Any,
    core_manifest: dict[str, Any] | None = None,
) -> list[dict[str, str]]:
    if not isinstance(manifest, dict):
        return [_diagnostic("EXPECTED_OBJECT", "translation manifest must be an object")]
    try:
        recorded_core = manifest.get("sharedCore")
        if recorded_core is not None and core_manifest is None:
            return [_diagnostic(
                "MISSING_SHARED_CORE",
                "translation manifest references a shared core that was not supplied for validation",
                "$.sharedCore",
            )]
        scope = TranslationGroupScope.from_inputs(
            plan, manifest.get("group", {}).get("name", ""), semantics_by_unit,
            created_at=manifest.get("createdAt", ""),
            shared_core=core_manifest,
        )
    except (KeyError, ValueError, AttributeError) as exc:
        return [_diagnostic("INPUT_BOUNDARY", str(exc))]
    manifest_mappings = manifest.get("declarations")
    submission_mappings = (
        [
            {key: value for key, value in item.items() if key != "sourceRange"}
            if isinstance(item, dict) else item
            for item in manifest_mappings
        ]
        if isinstance(manifest_mappings, list) else manifest_mappings
    )
    candidate, diagnostics = validate_submission(scope, semantics_by_unit, {
        "leanSource": source,
        "declarations": submission_mappings,
        "sharedUses": [
            {
                "dependencyId": item.get("dependencyId"),
                "leanDeclarations": item.get("leanDeclarations"),
            }
            for item in manifest.get("sharedUses", [])
            if isinstance(item, dict)
        ],
    })
    translator = manifest.get("translator")
    supported_translator = (
        isinstance(translator, dict)
        and translator.get("provider") == "opencode"
        and (translator.get("model"), translator.get("reasoning"))
        in SUPPORTED_TRANSLATOR_CONFIGURATIONS
    )
    if not supported_translator:
        diagnostics.append(_diagnostic(
            "UNSUPPORTED_TRANSLATOR",
            "translator must use a supported model/reasoning configuration: "
            f"{SUPPORTED_TRANSLATOR_CONFIGURATIONS}",
            "$.translator",
        ))
    elif candidate is not None:
        candidate["manifest"]["translator"] = dict(translator)
    candidate_manifest = candidate["manifest"] if candidate is not None else None
    historical_without_ranges = (
        isinstance(manifest_mappings, list)
        and bool(manifest_mappings)
        and all(
            isinstance(item, dict) and "sourceRange" not in item
            for item in manifest_mappings
        )
    )
    if candidate_manifest is not None and historical_without_ranges:
        candidate_manifest = {
            **candidate_manifest,
            "declarations": [
                {key: value for key, value in item.items() if key != "sourceRange"}
                for item in candidate_manifest["declarations"]
            ],
        }
    if candidate_manifest is not None and candidate_manifest != manifest:
        diagnostics.append(_diagnostic("DETERMINISTIC_MISMATCH", "manifest metadata or declaration mappings differ from deterministic reconstruction"))
    return diagnostics


def validate_run_metadata(scope: TranslationGroupScope, metadata: Any) -> list[dict[str, str]]:
    if not isinstance(metadata, dict):
        return [_diagnostic("EXPECTED_OBJECT", "translator run metadata must be an object")]
    expected = {
        "schemaVersion": TRANSLATION_SCHEMA_VERSION,
        "phase": "LLM_GROUP_TRANSLATOR",
        "planRunId": scope.plan_run_id,
        "group": {"name": scope.group, "unitIds": list(scope.unit_ids)},
        "translationRunId": scope.translation_run_id,
        "translator": "opencode",
        "singleSession": True,
        "automaticRetries": 0,
        "semanticsArtifacts": [
            {"unitId": unit_id, "runId": dict(scope.semantics_run_ids)[unit_id], "artifactHash": artifact_hash}
            for unit_id, artifact_hash in scope.semantics_artifact_hashes
        ],
        "targetLanguage": LEAN_LANGUAGE,
        "targetVersion": LEAN_VERSION,
        "exitCode": 0,
        "outcome": "SUCCESS",
        "error": None,
        "sharedCore": _core_reference(scope.shared_core),
        "inputBoundary": (
            "PHASE_4_AND_FROZEN_SHARED_CORE"
            if scope.shared_core is not None
            else "PHASE_4_SEMANTIC_ARTIFACTS_ONLY"
        ),
    }
    diagnostics = []
    configuration = (metadata.get("model"), metadata.get("reasoning"))
    if configuration not in SUPPORTED_TRANSLATOR_CONFIGURATIONS:
        diagnostics.append(_diagnostic(
            "INCOMPLETE_TRANSLATOR_METADATA",
            "translator metadata must use a supported model/reasoning configuration: "
            f"{SUPPORTED_TRANSLATOR_CONFIGURATIONS!r}",
            "$.model",
        ))
    for key, value in expected.items():
        if metadata.get(key) != value:
            diagnostics.append(_diagnostic("INCOMPLETE_TRANSLATOR_METADATA", f"translator metadata {key} must equal {value!r}", f"$.{key}"))
    for key in (
        "startedAt", "finishedAt", "semanticsArtifactPaths", "command", "sessionId",
        "stdout", "stderr",
    ):
        if key not in metadata:
            diagnostics.append(_diagnostic("INCOMPLETE_TRANSLATOR_METADATA", f"translator metadata is missing {key}", f"$.{key}"))
    for key in ("startedAt", "finishedAt"):
        if key in metadata and (not isinstance(metadata[key], str) or not metadata[key]):
            diagnostics.append(_diagnostic("INCOMPLETE_TRANSLATOR_METADATA", f"translator metadata {key} must be non-empty text", f"$.{key}"))
    if "command" in metadata and not isinstance(metadata["command"], list):
        diagnostics.append(_diagnostic("INCOMPLETE_TRANSLATOR_METADATA", "translator metadata command must be an array", "$.command"))
    if "semanticsArtifactPaths" in metadata and not isinstance(metadata["semanticsArtifactPaths"], list):
        diagnostics.append(_diagnostic("INCOMPLETE_TRANSLATOR_METADATA", "translator metadata semanticsArtifactPaths must be an array", "$.semanticsArtifactPaths"))
    for key in ("stdout", "stderr"):
        if key in metadata and not isinstance(metadata[key], str):
            diagnostics.append(_diagnostic("INCOMPLETE_TRANSLATOR_METADATA", f"translator metadata {key} must be text", f"$.{key}"))
    return diagnostics


def validate_published(
    plan: dict[str, Any], semantics_by_unit: dict[str, dict[str, Any]], directory: Path,
    core_manifest: dict[str, Any] | None = None,
) -> list[dict[str, str]]:
    diagnostics: list[dict[str, str]] = []
    manifest_path = directory / "translation-manifest.json"
    run_path = directory / "translator-run.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        diagnostics.append(_diagnostic("MISSING_MANIFEST", "translation-manifest.json does not exist"))
        manifest = None
    except json.JSONDecodeError:
        diagnostics.append(_diagnostic("INVALID_MANIFEST_JSON", "translation-manifest.json is invalid JSON"))
        manifest = None
    lean_file = manifest.get("leanFile") if isinstance(manifest, dict) else None
    lean_path = directory / str(lean_file or "Group.lean")
    if not lean_path.is_file():
        diagnostics.append(_diagnostic("MISSING_LEAN_FILE", f"{lean_path.name} does not exist", "$.leanFile"))
    source = lean_path.read_text(encoding="utf-8") if lean_path.is_file() else ""
    if not source.strip():
        diagnostics.append(_diagnostic("EMPTY_LEAN_FILE", f"{lean_path.name} is empty", "$.leanFile"))
    if manifest is not None:
        diagnostics.extend(validate_manifest(
            plan, semantics_by_unit, source, manifest, core_manifest=core_manifest
        ))
    try:
        metadata = json.loads(run_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        diagnostics.append(_diagnostic("MISSING_RUN_METADATA", "translator-run.json does not exist"))
        metadata = None
    except json.JSONDecodeError:
        diagnostics.append(_diagnostic("INVALID_RUN_METADATA_JSON", "translator-run.json is invalid JSON"))
        metadata = None
    if metadata is not None:
        try:
            scope = TranslationGroupScope.from_inputs(
                plan, (manifest or {}).get("group", {}).get("name", ""), semantics_by_unit,
                created_at=(manifest or {}).get("createdAt", ""),
                shared_core=core_manifest,
            )
            diagnostics.extend(validate_run_metadata(scope, metadata))
        except (KeyError, ValueError, AttributeError) as exc:
            diagnostics.append(_diagnostic("INPUT_BOUNDARY", str(exc)))
    if manifest is not None and metadata is not None and manifest.get("createdAt") != metadata.get("startedAt"):
        diagnostics.append(_diagnostic("DETERMINISTIC_MISMATCH", "manifest createdAt must equal translator-run startedAt", "$.createdAt"))
    return diagnostics
