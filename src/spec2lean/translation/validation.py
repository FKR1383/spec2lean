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
    TRANSLATOR_MODEL,
    TRANSLATOR_REASONING,
    TranslationScope,
)


SUBMISSION_FIELDS = {"leanSource", "declarations"}
MAPPING_FIELDS = {"declaration", "role", "semanticClaimIds", "supportsDeclarations"}
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


def _diagnostic(code: str, message: str, path: str = "$") -> dict[str, str]:
    return {"code": code, "message": message, "path": path}


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


def lean_declarations(source: str) -> dict[str, str]:
    clean = _without_comments_and_strings(source)
    contexts: list[list[str]] = []
    found: dict[str, str] = {}
    for line in clean.splitlines():
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
        found[qualified] = kind
    return found


def forbidden_constructs(source: str) -> list[dict[str, str]]:
    clean = _without_comments_and_strings(source)
    return [
        _diagnostic(code, message, "$.leanSource")
        for code, pattern, message in FORBIDDEN
        if pattern.search(clean)
    ]


def validate_submission(
    scope: TranslationScope, semantics: dict[str, Any], submission: Any
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

    raw_mappings = submission.get("declarations")
    if not isinstance(raw_mappings, list):
        diagnostics.append(_diagnostic("EXPECTED_ARRAY", "declarations must be an array", "$.declarations"))
        raw_mappings = []
    known_claims = set(scope.semantic_claim_ids)
    mappings: list[dict[str, Any]] = []
    mapped_names: set[str] = set()
    roles: set[str] = set()
    for index, raw in enumerate(raw_mappings):
        path = f"$.declarations[{index}]"
        if not isinstance(raw, dict):
            diagnostics.append(_diagnostic("EXPECTED_OBJECT", "declaration mapping must be an object", path))
            continue
        for field in sorted(set(raw) - MAPPING_FIELDS):
            diagnostics.append(_diagnostic("UNEXPECTED_FIELD", f"unsupported declaration field: {field}", f"{path}.{field}"))
        name, role, claims = raw.get("declaration"), raw.get("role"), raw.get("semanticClaimIds")
        supports = raw.get("supportsDeclarations", [])
        if not isinstance(name, str) or not LEAN_NAME.fullmatch(name):
            diagnostics.append(_diagnostic("INVALID_DECLARATION_NAME", "declaration must be a qualified ASCII Lean identifier", f"{path}.declaration"))
            continue
        if name in mapped_names:
            diagnostics.append(_diagnostic("DUPLICATE_DECLARATION_MAPPING", f"duplicate declaration mapping: {name}", f"{path}.declaration"))
        mapped_names.add(name)
        if name not in declared:
            diagnostics.append(_diagnostic("MISSING_LEAN_DECLARATION", f"mapped declaration is not present in Lean source: {name}", f"{path}.declaration"))
        if role not in DECLARATION_ROLES:
            diagnostics.append(_diagnostic("INVALID_DECLARATION_ROLE", f"role must be one of {DECLARATION_ROLES}", f"{path}.role"))
        else:
            roles.add(role)
            if name in declared and declared[name] in {"structure", "inductive", "class"} and role != "PRIMARY_TYPE":
                diagnostics.append(_diagnostic("TYPE_ROLE_MISMATCH", f"introduced type must use PRIMARY_TYPE role: {name}", f"{path}.role"))
        if not isinstance(claims, list) or not all(isinstance(item, str) for item in claims):
            diagnostics.append(_diagnostic("INVALID_SEMANTIC_MAPPING", "semanticClaimIds must be a string array", f"{path}.semanticClaimIds"))
            claims = []
        elif len(claims) != len(set(claims)):
            diagnostics.append(_diagnostic("DUPLICATE_SEMANTIC_CLAIM", "semanticClaimIds contains a duplicate", f"{path}.semanticClaimIds"))
        for claim_id in claims:
            if claim_id not in known_claims:
                diagnostics.append(_diagnostic("UNKNOWN_SEMANTIC_CLAIM", f"semantic claim is not in the Phase-4 artifact: {claim_id}", f"{path}.semanticClaimIds"))
        if not isinstance(supports, list) or not all(isinstance(item, str) and LEAN_NAME.fullmatch(item) for item in supports):
            diagnostics.append(_diagnostic("INVALID_SUPPORT_MAPPING", "supportsDeclarations must be an array of qualified ASCII Lean identifiers", f"{path}.supportsDeclarations"))
            supports = []
        elif len(supports) != len(set(supports)):
            diagnostics.append(_diagnostic("DUPLICATE_SUPPORT_MAPPING", "supportsDeclarations contains a duplicate", f"{path}.supportsDeclarations"))
        if supports and role != "IMPLEMENTATION_HELPER":
            diagnostics.append(_diagnostic("INVALID_SUPPORT_ROLE", "only IMPLEMENTATION_HELPER may use supportsDeclarations", f"{path}.supportsDeclarations"))
        if role != "IMPLEMENTATION_HELPER" and not claims:
            diagnostics.append(_diagnostic("MISSING_SEMANTIC_MAPPING", "semantic declarations require at least one semantic claim ID", f"{path}.semanticClaimIds"))
        if role == "IMPLEMENTATION_HELPER" and not claims and not supports:
            diagnostics.append(_diagnostic("MISSING_SEMANTIC_MAPPING", "implementation helpers require semantic claims or a supported semantic declaration", path))
        mapping = {"declaration": name, "role": role, "semanticClaimIds": list(claims)}
        if supports:
            mapping["supportsDeclarations"] = list(supports)
        mappings.append(mapping)

    mappings_by_name = {item["declaration"]: item for item in mappings}
    for index, mapping in enumerate(mappings):
        for supported in mapping.get("supportsDeclarations", []):
            if supported == mapping["declaration"]:
                diagnostics.append(_diagnostic("SELF_SUPPORT_MAPPING", "a declaration cannot support itself", f"$.declarations[{index}].supportsDeclarations"))
            elif supported not in mappings_by_name:
                diagnostics.append(_diagnostic("UNKNOWN_SUPPORT_DECLARATION", f"supported declaration has no mapping: {supported}", f"$.declarations[{index}].supportsDeclarations"))

    def resolves_to_claims(name: str, seen: set[str]) -> bool:
        if name in seen or name not in mappings_by_name:
            return False
        mapping = mappings_by_name[name]
        if mapping["semanticClaimIds"]:
            return True
        return any(resolves_to_claims(item, {*seen, name}) for item in mapping.get("supportsDeclarations", []))

    for index, mapping in enumerate(mappings):
        if not resolves_to_claims(mapping["declaration"], set()):
            diagnostics.append(_diagnostic("UNRESOLVED_SUPPORT_MAPPING", "declaration traceability does not resolve to a semantic claim", f"$.declarations[{index}]"))

    for name in sorted(set(declared) - mapped_names):
        diagnostics.append(_diagnostic("UNMAPPED_LEAN_DECLARATION", f"named Lean declaration lacks semantic traceability: {name}", "$.declarations"))

    semantic_payload = semantics.get("semantics") or {}
    instruction = semantic_payload.get("unitKind") == "INSTRUCTION"
    if instruction and "OPERATION" not in roles:
        diagnostics.append(_diagnostic("MISSING_OPERATION_MAPPING", "instruction translation requires a mapped OPERATION declaration", "$.declarations"))
    needs_execution = instruction and bool(semantic_payload.get("stateEffects") or semantic_payload.get("predication"))
    if needs_execution and "EXECUTION" not in roles:
        diagnostics.append(_diagnostic("MISSING_EXECUTION_MAPPING", "stateful or predicated instruction translation requires a mapped EXECUTION declaration", "$.declarations"))
    return ({"leanSource": source, "manifest": scope.manifest(mappings)}, []) if not diagnostics else (None, diagnostics)


def validate_manifest(
    plan: dict[str, Any], semantics: dict[str, Any], source: str, manifest: Any
) -> list[dict[str, str]]:
    if not isinstance(manifest, dict):
        return [_diagnostic("EXPECTED_OBJECT", "translation manifest must be an object")]
    try:
        scope = TranslationScope.from_inputs(
            plan, semantics, manifest.get("unit", {}).get("unitId"), created_at=manifest.get("createdAt", "")
        )
    except (KeyError, ValueError, AttributeError) as exc:
        return [_diagnostic("INPUT_BOUNDARY", str(exc))]
    candidate, diagnostics = validate_submission(scope, semantics, {
        "leanSource": source,
        "declarations": manifest.get("declarations"),
    })
    if candidate is not None and candidate["manifest"] != manifest:
        diagnostics.append(_diagnostic("DETERMINISTIC_MISMATCH", "manifest metadata or declaration mappings differ from deterministic reconstruction"))
    return diagnostics


def validate_run_metadata(scope: TranslationScope, metadata: Any) -> list[dict[str, str]]:
    if not isinstance(metadata, dict):
        return [_diagnostic("EXPECTED_OBJECT", "translator run metadata must be an object")]
    expected = {
        "schemaVersion": TRANSLATION_SCHEMA_VERSION,
        "phase": "LLM_TRANSLATOR",
        "planRunId": scope.plan_run_id,
        "unitId": scope.unit_id,
        "translationRunId": scope.translation_run_id,
        "translator": "opencode",
        "model": TRANSLATOR_MODEL,
        "reasoning": TRANSLATOR_REASONING,
        "singleSession": True,
        "automaticRetries": 0,
        "semanticsArtifactHash": scope.semantics_artifact_hash,
        "inputBoundary": "PHASE_4_SEMANTIC_ARTIFACT_ONLY",
        "targetLanguage": LEAN_LANGUAGE,
        "targetVersion": LEAN_VERSION,
        "exitCode": 0,
        "outcome": "SUCCESS",
        "error": None,
    }
    diagnostics = []
    for key, value in expected.items():
        if metadata.get(key) != value:
            diagnostics.append(_diagnostic("INCOMPLETE_TRANSLATOR_METADATA", f"translator metadata {key} must equal {value!r}", f"$.{key}"))
    for key in (
        "startedAt", "finishedAt", "semanticsArtifact", "command", "sessionId",
        "sharedLeanFiles", "stdout", "stderr",
    ):
        if key not in metadata:
            diagnostics.append(_diagnostic("INCOMPLETE_TRANSLATOR_METADATA", f"translator metadata is missing {key}", f"$.{key}"))
    for key in ("startedAt", "finishedAt", "semanticsArtifact"):
        if key in metadata and (not isinstance(metadata[key], str) or not metadata[key]):
            diagnostics.append(_diagnostic("INCOMPLETE_TRANSLATOR_METADATA", f"translator metadata {key} must be non-empty text", f"$.{key}"))
    if "command" in metadata and not isinstance(metadata["command"], list):
        diagnostics.append(_diagnostic("INCOMPLETE_TRANSLATOR_METADATA", "translator metadata command must be an array", "$.command"))
    if "sharedLeanFiles" in metadata and not isinstance(metadata["sharedLeanFiles"], list):
        diagnostics.append(_diagnostic("INCOMPLETE_TRANSLATOR_METADATA", "translator metadata sharedLeanFiles must be an array", "$.sharedLeanFiles"))
    for key in ("stdout", "stderr"):
        if key in metadata and not isinstance(metadata[key], str):
            diagnostics.append(_diagnostic("INCOMPLETE_TRANSLATOR_METADATA", f"translator metadata {key} must be text", f"$.{key}"))
    return diagnostics


def validate_published(
    plan: dict[str, Any], semantics: dict[str, Any], directory: Path
) -> list[dict[str, str]]:
    diagnostics: list[dict[str, str]] = []
    lean_path = directory / "Unit.lean"
    manifest_path = directory / "translation-manifest.json"
    run_path = directory / "translator-run.json"
    if not lean_path.is_file():
        diagnostics.append(_diagnostic("MISSING_LEAN_FILE", "Unit.lean does not exist", "$.leanFile"))
    source = lean_path.read_text(encoding="utf-8") if lean_path.is_file() else ""
    if not source.strip():
        diagnostics.append(_diagnostic("EMPTY_LEAN_FILE", "Unit.lean is empty", "$.leanFile"))
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        diagnostics.append(_diagnostic("MISSING_MANIFEST", "translation-manifest.json does not exist"))
        manifest = None
    except json.JSONDecodeError:
        diagnostics.append(_diagnostic("INVALID_MANIFEST_JSON", "translation-manifest.json is invalid JSON"))
        manifest = None
    if manifest is not None:
        diagnostics.extend(validate_manifest(plan, semantics, source, manifest))
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
            scope = TranslationScope.from_inputs(plan, semantics, semantics.get("unit", {}).get("unitId"), created_at=(manifest or {}).get("createdAt", ""))
            diagnostics.extend(validate_run_metadata(scope, metadata))
        except (KeyError, ValueError, AttributeError) as exc:
            diagnostics.append(_diagnostic("INPUT_BOUNDARY", str(exc)))
    if manifest is not None and metadata is not None and manifest.get("createdAt") != metadata.get("startedAt"):
        diagnostics.append(_diagnostic("DETERMINISTIC_MISMATCH", "manifest createdAt must equal translator-run startedAt", "$.createdAt"))
    return diagnostics
