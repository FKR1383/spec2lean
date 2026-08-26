from __future__ import annotations

from typing import Any, Iterable

from ..util import normalize_text
from .models import CLAIM_KINDS, RESTRICTION_KINDS, UNIT_KINDS, SemanticScope, evidence_bundle_hash


SUCCESS_FIELDS = {
    "outcome", "unitKind", "identity", "syntaxForms", "inputs", "result", "operation",
    "edgeCases", "stateEffects", "predication", "restrictions", "dependencies", "claims",
}
FAILURE_FIELDS = {"outcome", "missingAspects", "explanation", "evidenceIds"}
COMPONENT_FIELDS: dict[str, set[str]] = {
    "identity": {"name", "form", "description", "evidenceIds"},
    "syntax": {"form", "description", "evidenceIds"},
    "input": {"name", "role", "description", "constraints", "evidenceIds"},
    "result": {"name", "description", "constraints", "evidenceIds"},
    "operation": {"description", "inputs", "result", "branches", "evidenceIds"},
    "branch": {"condition", "behavior", "evidenceIds"},
    "edge": {"condition", "behavior", "evidenceIds"},
    "state": {"target", "effect", "evidenceIds"},
    "predication": {"guard", "whenTrue", "whenFalse", "evidenceIds"},
    "restriction": {"kind", "description", "evidenceIds"},
    "dependency": {"concept", "description", "artifactId", "evidenceIds"},
    "claim": {"claimId", "kind", "statement", "evidenceIds"},
}


def _diagnostic(code: str, message: str, path: str = "$") -> dict[str, str]:
    return {"code": code, "message": message, "path": path}


def _object(value: Any, path: str, diagnostics: list[dict[str, str]]) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        diagnostics.append(_diagnostic("EXPECTED_OBJECT", "value must be an object", path))
        return None
    return value


def _fields(value: dict[str, Any], allowed: set[str], path: str, diagnostics: list[dict[str, str]]) -> None:
    for key in sorted(set(value) - allowed):
        diagnostics.append(_diagnostic("UNEXPECTED_FIELD", f"unsupported semantic field: {key}", f"{path}.{key}"))


def _text(value: Any, path: str, diagnostics: list[dict[str, str]], *, minimum: int = 1) -> None:
    if not isinstance(value, str) or len(normalize_text(value)) < minimum:
        diagnostics.append(_diagnostic("INVALID_TEXT", f"must be non-empty semantic text (minimum {minimum} characters)", path))


def _evidence_ids(
    value: Any, allowed: set[str], path: str, diagnostics: list[dict[str, str]], *, required: bool
) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        diagnostics.append(_diagnostic("INVALID_EVIDENCE_IDS", "evidenceIds must be an array of strings", path))
        return []
    if required and not value:
        diagnostics.append(_diagnostic("MISSING_EVIDENCE", "at least one evidence ID is required", path))
    if len(value) != len(set(value)):
        diagnostics.append(_diagnostic("DUPLICATE_EVIDENCE_ID", "evidenceIds contains a duplicate", path))
    for item in value:
        if item not in allowed:
            diagnostics.append(_diagnostic("UNKNOWN_EVIDENCE_ID", f"evidence ID is not in this unit bundle: {item}", path))
    return value


def _list(value: Any, path: str, diagnostics: list[dict[str, str]]) -> list[Any]:
    if not isinstance(value, list):
        diagnostics.append(_diagnostic("EXPECTED_ARRAY", "value must be an array", path))
        return []
    return value


def _component(
    raw: Any, kind: str, path: str, allowed_evidence: set[str], diagnostics: list[dict[str, str]],
    *, evidence_required: bool = True,
) -> dict[str, Any] | None:
    value = _object(raw, path, diagnostics)
    if value is None:
        return None
    _fields(value, COMPONENT_FIELDS[kind], path, diagnostics)
    _evidence_ids(value.get("evidenceIds", []), allowed_evidence, f"{path}.evidenceIds", diagnostics, required=evidence_required)
    return value


def _require_component_texts(value: dict[str, Any], names: Iterable[str], path: str, diagnostics: list[dict[str, str]]) -> None:
    for name in names:
        _text(value.get(name), f"{path}.{name}", diagnostics)


def validate_submission(
    scope: SemanticScope, bundle: dict[str, Any], submission: Any
) -> tuple[dict[str, Any] | None, list[dict[str, str]]]:
    diagnostics: list[dict[str, str]] = []
    value = _object(submission, "$", diagnostics)
    if value is None:
        return None, diagnostics
    outcome = value.get("outcome")
    allowed_evidence = set(scope.evidence_ids)
    if outcome == "INSUFFICIENT_EVIDENCE":
        _fields(value, FAILURE_FIELDS, "$", diagnostics)
        missing = _list(value.get("missingAspects"), "$.missingAspects", diagnostics)
        if not missing:
            diagnostics.append(_diagnostic("MISSING_ASPECT", "at least one missing semantic aspect is required", "$.missingAspects"))
        for index, item in enumerate(missing):
            if not isinstance(item, str) or not normalize_text(item):
                diagnostics.append(_diagnostic("INVALID_TEXT", "missing aspect must be non-empty", f"$.missingAspects[{index}]"))
        _text(value.get("explanation"), "$.explanation", diagnostics)
        _evidence_ids(value.get("evidenceIds", []), allowed_evidence, "$.evidenceIds", diagnostics, required=False)
        return (scope.artifact(value), []) if not diagnostics else (None, diagnostics)
    if outcome != "SUCCESS":
        diagnostics.append(_diagnostic("INVALID_OUTCOME", "outcome must be SUCCESS or INSUFFICIENT_EVIDENCE", "$.outcome"))
        return None, diagnostics

    _fields(value, SUCCESS_FIELDS, "$", diagnostics)
    unit_kind = value.get("unitKind")
    if unit_kind not in UNIT_KINDS:
        diagnostics.append(_diagnostic("INVALID_UNIT_KIND", f"unitKind must be one of {UNIT_KINDS}", "$.unitKind"))

    identity = _component(value.get("identity"), "identity", "$.identity", allowed_evidence, diagnostics)
    if identity is not None:
        _text(identity.get("name"), "$.identity.name", diagnostics)
        if identity.get("name") != scope.unit.get("name"):
            diagnostics.append(_diagnostic("WRONG_IDENTITY", "identity.name must exactly match the planned unit name", "$.identity.name"))

    for field, kind, texts in (
        ("syntaxForms", "syntax", ("form",)), ("inputs", "input", ("name", "role", "description")),
        ("edgeCases", "edge", ("condition", "behavior")),
        ("stateEffects", "state", ("target", "effect")),
        ("restrictions", "restriction", ("description",)),
    ):
        for index, raw in enumerate(_list(value.get(field, []), f"$.{field}", diagnostics)):
            item = _component(raw, kind, f"$.{field}[{index}]", allowed_evidence, diagnostics)
            if item is not None:
                _require_component_texts(item, texts, f"$.{field}[{index}]", diagnostics)
                if kind == "restriction" and item.get("kind") not in RESTRICTION_KINDS:
                    diagnostics.append(_diagnostic("INVALID_RESTRICTION_KIND", f"kind must be one of {RESTRICTION_KINDS}", f"$.{field}[{index}].kind"))
                if kind == "input":
                    constraints = item.get("constraints")
                    if not isinstance(constraints, list) or not all(isinstance(entry, str) and normalize_text(entry) for entry in constraints):
                        diagnostics.append(_diagnostic("INVALID_CONSTRAINTS", "constraints must be an array of non-empty strings", f"$.{field}[{index}].constraints"))

    result = _component(value.get("result"), "result", "$.result", allowed_evidence, diagnostics)
    if result is not None:
        _require_component_texts(result, ("name", "description"), "$.result", diagnostics)
        constraints = result.get("constraints")
        if not isinstance(constraints, list) or not all(isinstance(entry, str) and normalize_text(entry) for entry in constraints):
            diagnostics.append(_diagnostic("INVALID_CONSTRAINTS", "constraints must be an array of non-empty strings", "$.result.constraints"))

    operation = value.get("operation")
    operation_item = None
    if operation is not None:
        operation_item = _component(operation, "operation", "$.operation", allowed_evidence, diagnostics)
        if operation_item is not None:
            _text(operation_item.get("description"), "$.operation.description", diagnostics, minimum=12)
            names = operation_item.get("inputs")
            if not isinstance(names, list) or not names or not all(isinstance(item, str) and normalize_text(item) for item in names):
                diagnostics.append(_diagnostic("MISSING_OPERATION_INPUTS", "operation.inputs must name at least one input", "$.operation.inputs"))
            _text(operation_item.get("result"), "$.operation.result", diagnostics)
            for index, raw in enumerate(_list(operation_item.get("branches", []), "$.operation.branches", diagnostics)):
                branch = _component(raw, "branch", f"$.operation.branches[{index}]", allowed_evidence, diagnostics)
                if branch is not None:
                    _require_component_texts(branch, ("condition", "behavior"), f"$.operation.branches[{index}]", diagnostics)

    evidence_roles = {item.get("evidenceId"): item.get("role") for item in bundle.get("evidence", [])}
    is_instruction = unit_kind == "INSTRUCTION" or any(role in {"OPERATION", "ALGORITHM"} for role in evidence_roles.values())
    if is_instruction:
        if operation_item is None:
            diagnostics.append(_diagnostic("MISSING_OPERATION", "instruction semantics require a core operation", "$.operation"))
        else:
            op_evidence = operation_item.get("evidenceIds", [])
            if not any(evidence_roles.get(item) in {"OPERATION", "ALGORITHM"} for item in op_evidence):
                diagnostics.append(_diagnostic("NONFUNCTIONAL_OPERATION", "instruction operation must cite OPERATION or ALGORITHM evidence", "$.operation.evidenceIds"))
        if result is None:
            diagnostics.append(_diagnostic("MISSING_RESULT", "instruction semantics require a result", "$.result"))
        if not isinstance(value.get("inputs"), list) or not value.get("inputs"):
            diagnostics.append(_diagnostic("MISSING_INPUTS", "instruction semantics require inputs", "$.inputs"))

    predication = value.get("predication")
    if predication is not None:
        item = _component(predication, "predication", "$.predication", allowed_evidence, diagnostics)
        if item is not None:
            _require_component_texts(item, ("guard", "whenTrue", "whenFalse"), "$.predication", diagnostics)

    for index, raw in enumerate(_list(value.get("dependencies", []), "$.dependencies", diagnostics)):
        item = _component(raw, "dependency", f"$.dependencies[{index}]", allowed_evidence, diagnostics, evidence_required=False)
        if item is not None:
            _require_component_texts(item, ("concept", "description"), f"$.dependencies[{index}]", diagnostics)

    claim_ids: set[str] = set()
    claim_meanings: set[tuple[str, str]] = set()
    for index, raw in enumerate(_list(value.get("claims"), "$.claims", diagnostics)):
        path = f"$.claims[{index}]"
        item = _component(raw, "claim", path, allowed_evidence, diagnostics, evidence_required=False)
        if item is None:
            continue
        claim_id, claim_kind = item.get("claimId"), item.get("kind")
        if not isinstance(claim_id, str) or not claim_id.startswith("claim:"):
            diagnostics.append(_diagnostic("INVALID_CLAIM_ID", "claimId must start with claim:", f"{path}.claimId"))
        elif claim_id in claim_ids:
            diagnostics.append(_diagnostic("DUPLICATE_CLAIM_ID", f"duplicate claim ID: {claim_id}", f"{path}.claimId"))
        claim_ids.add(claim_id)
        if claim_kind not in CLAIM_KINDS:
            diagnostics.append(_diagnostic("INVALID_CLAIM_KIND", f"kind must be one of {CLAIM_KINDS}", f"{path}.kind"))
        _text(item.get("statement"), f"{path}.statement", diagnostics)
        statement = normalize_text(item.get("statement", "")).casefold() if isinstance(item.get("statement"), str) else ""
        meaning = (str(claim_kind), statement)
        if statement and meaning in claim_meanings:
            diagnostics.append(_diagnostic("DUPLICATE_CLAIM", "duplicate semantic claim", path))
        claim_meanings.add(meaning)
        if claim_kind in {"SOURCE_FACT", "DERIVED_INTERPRETATION"} and not item.get("evidenceIds"):
            diagnostics.append(_diagnostic("MISSING_EVIDENCE", "SOURCE_FACT and DERIVED_INTERPRETATION claims require evidence", f"{path}.evidenceIds"))
    if not value.get("claims"):
        diagnostics.append(_diagnostic("MISSING_CLAIMS", "at least one structured semantic claim is required", "$.claims"))
    return (scope.artifact(value), []) if not diagnostics else (None, diagnostics)


def validate_artifact(plan: dict[str, Any], bundle: dict[str, Any], artifact: Any) -> list[dict[str, str]]:
    diagnostics: list[dict[str, str]] = []
    if not isinstance(artifact, dict):
        return [_diagnostic("EXPECTED_OBJECT", "semantic artifact must be an object")]
    try:
        scope = SemanticScope.from_inputs(plan, bundle, artifact.get("unit", {}).get("unitId"), created_at=artifact.get("createdAt", ""))
    except (KeyError, ValueError, AttributeError) as exc:
        return [_diagnostic("INPUT_BOUNDARY", str(exc))]
    if artifact.get("evidenceBundleHash") != evidence_bundle_hash(bundle):
        diagnostics.append(_diagnostic("EVIDENCE_HASH_MISMATCH", "artifact evidence bundle hash is incorrect", "$.evidenceBundleHash"))
    submission = {"outcome": artifact.get("outcome")}
    payload = artifact.get("semantics") if artifact.get("outcome") == "SUCCESS" else artifact.get("failure")
    if isinstance(payload, dict):
        submission.update(payload)
    rebuilt, inner = validate_submission(scope, bundle, submission)
    diagnostics.extend(inner)
    if rebuilt is not None and rebuilt != artifact:
        diagnostics.append(_diagnostic("DETERMINISTIC_MISMATCH", "artifact metadata or semantic payload differs from deterministic reconstruction"))
    return diagnostics
