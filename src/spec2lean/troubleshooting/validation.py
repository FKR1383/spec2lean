from __future__ import annotations

from collections import Counter
from typing import Any

from ..translation.models import TranslationGroupScope
from ..translation.validation import validate_submission


REPAIR_FIELDS = {"leanSource", "declarations", "changes"}
CHANGE_FIELDS = {"description", "affectedDeclarations"}


def _mapping_signature(
    mappings: list[dict[str, Any]],
) -> Counter[tuple[str, tuple[tuple[str, str], ...]]]:
    """Ignore mechanical renames while preserving resolved semantic responsibility."""
    by_name = {str(item.get("declaration", "")): item for item in mappings}

    def claims_for(item: dict[str, Any], seen: set[str]) -> set[tuple[str, str]]:
        name = str(item.get("declaration", ""))
        if name in seen:
            return set()
        claims = {
            (str(ref.get("unitId", "")), str(ref.get("claimId", "")))
            for ref in item.get("claimRefs", [])
            if isinstance(ref, dict)
        }
        for supported in item.get("supportsDeclarations", []):
            target = by_name.get(str(supported))
            if target is not None:
                claims.update(claims_for(target, {*seen, name}))
        return claims

    return Counter(
        (str(item.get("role", "")), tuple(sorted(claims_for(item, set()))))
        for item in mappings
    )


def validate_repair_submission(
    scope: TranslationGroupScope,
    semantics_by_unit: dict[str, dict[str, Any]],
    original_source: str,
    original_manifest: dict[str, Any],
    submission: Any,
) -> tuple[dict[str, Any] | None, list[dict[str, str]]]:
    diagnostics: list[dict[str, str]] = []
    if not isinstance(submission, dict):
        return None, [{"code": "EXPECTED_OBJECT", "message": "repair submission must be an object", "path": "$"}]
    for field in sorted(set(submission) - REPAIR_FIELDS):
        diagnostics.append({
            "code": "UNEXPECTED_FIELD",
            "message": f"unsupported repair field: {field}",
            "path": f"$.{field}",
        })
    candidate, translation_diagnostics = validate_submission(
        scope,
        semantics_by_unit,
        {
            "leanSource": submission.get("leanSource"),
            "declarations": submission.get("declarations"),
        },
    )
    diagnostics.extend(translation_diagnostics)

    changes = submission.get("changes")
    normalized_changes: list[dict[str, Any]] = []
    if not isinstance(changes, list) or not changes:
        diagnostics.append({
            "code": "MISSING_CHANGES",
            "message": "changes must be a non-empty array",
            "path": "$.changes",
        })
        changes = []
    known_declarations = {
        str(item.get("declaration", ""))
        for item in (submission.get("declarations") or [])
        if isinstance(item, dict)
    } | {
        str(item.get("declaration", ""))
        for item in original_manifest.get("declarations", [])
        if isinstance(item, dict)
    }
    for index, change in enumerate(changes):
        path = f"$.changes[{index}]"
        if not isinstance(change, dict):
            diagnostics.append({"code": "EXPECTED_OBJECT", "message": "change must be an object", "path": path})
            continue
        for field in sorted(set(change) - CHANGE_FIELDS):
            diagnostics.append({
                "code": "UNEXPECTED_FIELD",
                "message": f"unsupported change field: {field}",
                "path": f"{path}.{field}",
            })
        description = change.get("description")
        affected = change.get("affectedDeclarations")
        if not isinstance(description, str) or not description.strip():
            diagnostics.append({"code": "EMPTY_DESCRIPTION", "message": "change description must be non-empty", "path": f"{path}.description"})
        if not isinstance(affected, list) or not all(isinstance(item, str) for item in affected):
            diagnostics.append({"code": "INVALID_AFFECTED_DECLARATIONS", "message": "affectedDeclarations must be a string array (empty for file-level import changes)", "path": f"{path}.affectedDeclarations"})
            affected = []
        elif len(affected) != len(set(affected)):
            diagnostics.append({"code": "DUPLICATE_AFFECTED_DECLARATION", "message": "affectedDeclarations contains a duplicate", "path": f"{path}.affectedDeclarations"})
        for declaration in affected:
            if declaration not in known_declarations:
                diagnostics.append({"code": "UNKNOWN_AFFECTED_DECLARATION", "message": f"change names an unmapped declaration: {declaration}", "path": f"{path}.affectedDeclarations"})
        normalized_changes.append({
            "description": description.strip() if isinstance(description, str) else "",
            "affectedDeclarations": list(affected),
        })

    if candidate is not None:
        if (
            candidate["leanSource"] == original_source
            and candidate["manifest"] == original_manifest
        ):
            diagnostics.append({"code": "NO_REPAIR", "message": "repair did not change the translation", "path": "$"})
        before = _mapping_signature(original_manifest.get("declarations", []))
        after = _mapping_signature(candidate["manifest"].get("declarations", []))
        if before != after:
            diagnostics.append({
                "code": "SEMANTIC_MAPPING_CHANGED",
                "message": "compiler repair must preserve declaration roles and semantic-claim responsibilities",
                "path": "$.declarations",
            })
    if diagnostics or candidate is None:
        return None, diagnostics
    return {
        "leanSource": candidate["leanSource"],
        "manifest": candidate["manifest"],
        "changes": normalized_changes,
    }, []
