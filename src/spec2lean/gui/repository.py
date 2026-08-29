from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from ..translation.shared_core.store import load_core
from ..translation.validation import declaration_source_ranges, lean_declarations


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _duration_ms(value: dict[str, Any] | None) -> int | None:
    if not value:
        return None
    direct = value.get("durationMs")
    if isinstance(direct, (int, float)):
        return int(direct)
    from datetime import datetime

    try:
        start = datetime.fromisoformat(str(value["startedAt"]).replace("Z", "+00:00"))
        finish = datetime.fromisoformat(str(value["finishedAt"]).replace("Z", "+00:00"))
        return max(0, int((finish - start).total_seconds() * 1000))
    except (KeyError, TypeError, ValueError):
        return None


def _unit_failed(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    check = (value.get("stages") or {}).get("check") if isinstance(value.get("stages"), dict) else None
    return value.get("status") in {"FAIL", "FAILED"} or (isinstance(check, dict) and check.get("status") == "FAIL")


@dataclass(frozen=True)
class ArtifactRoots:
    repository: Path
    runs: Path
    plans: Path
    evidence: Path
    semantics: Path
    translations: Path
    checks: Path
    troubleshooting: Path
    indexes: Path

    @classmethod
    def at(cls, repository: Path, *, runs: Path | None = None) -> "ArtifactRoots":
        root = repository.resolve()
        return cls(
            repository=root,
            runs=(runs or root / "runs").resolve(),
            plans=root / "plans",
            evidence=root / "evidence",
            semantics=root / "semantics",
            translations=root / "translations",
            checks=root / "checks",
            troubleshooting=root / "troubleshooting",
            indexes=root / "indexes",
        )


class ArtifactRepository:
    """A tolerant, on-demand projection over existing V1 artifacts."""

    def __init__(self, roots: ArtifactRoots):
        self.roots = roots

    @classmethod
    def at(cls, repository: Path, *, runs: Path | None = None) -> "ArtifactRepository":
        return cls(ArtifactRoots.at(repository, runs=runs))

    def _run_paths(self) -> Iterable[Path]:
        return self.roots.runs.glob("*/*/*/run.json")

    def _find_run(self, run_id: str) -> tuple[Path, dict[str, Any]]:
        if "/" in run_id or "\\" in run_id or run_id in {".", ".."}:
            raise KeyError("invalid run ID")
        matches = []
        for path in self._run_paths():
            data = _read_json(path)
            if data and data.get("pipelineRunId") == run_id:
                matches.append((path, data))
        if len(matches) != 1:
            raise KeyError(f"unknown or ambiguous run: {run_id}")
        return matches[0]

    def _plan(self, run: dict[str, Any]) -> tuple[Path | None, dict[str, Any] | None]:
        language = str((run.get("request") or {}).get("language", "")).casefold()
        version = str((run.get("request") or {}).get("version", ""))
        plan_id = run.get("planRunId")
        if not (language and version and plan_id):
            return None, None
        path = self.roots.plans / language / version / str(plan_id) / "plan.json"
        return path, _read_json(path)

    def list_runs(self) -> list[dict[str, Any]]:
        result = []
        for path in self._run_paths():
            run = _read_json(path)
            if not run:
                continue
            units = run.get("units") if isinstance(run.get("units"), dict) else {}
            requested = list(((run.get("request") or {}).get("scope") or {}).get("instructions") or [])
            complete = sum((item or {}).get("status") == "PASS" for item in units.values())
            failed = sum(_unit_failed(item) for item in units.values())
            result.append({
                "runId": run.get("pipelineRunId"),
                "language": (run.get("request") or {}).get("language"),
                "version": (run.get("request") or {}).get("version"),
                "scope": (run.get("request") or {}).get("scope") or {},
                "requestedNames": requested or [item.get("name") for item in units.values() if isinstance(item, dict)],
                "planRunId": run.get("planRunId"),
                "createdAt": run.get("createdAt"),
                "updatedAt": run.get("updatedAt"),
                "status": run.get("status", "UNKNOWN"),
                "requested": len(requested) or len(units),
                "completed": complete,
                "failed": failed,
                "error": run.get("error"),
            })
        return sorted(result, key=lambda item: item.get("createdAt") or "", reverse=True)

    def get_run(self, run_id: str) -> dict[str, Any]:
        _, run = self._find_run(run_id)
        _, plan = self._plan(run)
        units = self.list_units(run_id)
        return {
            **next(item for item in self.list_runs() if item["runId"] == run_id),
            "phase1": run.get("phase1"),
            "plan": {key: plan.get(key) for key in (
                "graphStatus", "dependencies", "externalPrerequisites",
                "sharedPrerequisites", "blockedUnitIds",
            )}
            if plan else None,
            "layers": self._layers(plan, units),
            "units": units,
            "raw": run,
        }

    @staticmethod
    def _layers(plan: dict[str, Any] | None, units: list[dict[str, Any]]) -> list[dict[str, Any]]:
        by_id = {item["unitId"]: item for item in units}
        if not plan:
            return [{"layer": 0, "units": units}] if units else []
        result = []
        seen: set[str] = set()
        for layer in plan.get("processingLayers", []):
            items = [by_id[item] for item in layer.get("unitIds", []) if item in by_id]
            seen.update(item["unitId"] for item in items)
            result.append({"layer": layer.get("layer", len(result)), "units": items})
        extras = [item for item in units if item["unitId"] not in seen]
        if extras:
            result.append({"layer": len(result), "units": extras, "unplanned": True})
        return result

    def list_units(self, run_id: str) -> list[dict[str, Any]]:
        _, run = self._find_run(run_id)
        _, plan = self._plan(run)
        run_units = run.get("units") if isinstance(run.get("units"), dict) else {}
        planned = plan.get("requestedUnits", []) if plan else []
        ordered_ids = [unit for layer in (plan or {}).get("processingLayers", []) for unit in layer.get("unitIds", [])]
        planned_by_id = {item.get("unitId"): item for item in planned}
        for item in planned:
            if item.get("unitId") not in ordered_ids:
                ordered_ids.append(item.get("unitId"))
        for unit_id in run_units:
            if unit_id not in ordered_ids:
                ordered_ids.append(unit_id)
        result = []
        for unit_id in ordered_ids:
            base = planned_by_id.get(unit_id, {})
            state = run_units.get(unit_id, {}) if isinstance(run_units.get(unit_id, {}), dict) else {}
            stages = state.get("stages") if isinstance(state.get("stages"), dict) else {}
            result.append({
                "unitId": unit_id,
                "name": state.get("name") or base.get("name") or unit_id,
                "sourceNodeIds": base.get("sourceNodeIds", []),
                "status": state.get("status", "PENDING"),
                "stages": {
                    "evidence": stages.get("evidence", "NOT_STARTED"),
                    "semantics": stages.get("semantics", "NOT_STARTED"),
                    "translate": stages.get("translate", "NOT_STARTED"),
                    "check": stages.get("check", "NOT_STARTED"),
                    "troubleshoot": stages.get("troubleshoot", "NOT_REQUIRED"),
                },
            })
        return result

    def _context(self, run_id: str, unit_id: str) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
        _, run = self._find_run(run_id)
        _, plan = self._plan(run)
        if not plan:
            request = run.get("request") or {}
            plan = {
                "language": request.get("language", "unknown"),
                "version": request.get("version", "unknown"),
                "planRunId": run.get("planRunId") or "unavailable",
                "requestedUnits": [],
                "processingLayers": [],
            }
        units = [item for item in self.list_units(run_id) if item["unitId"] == unit_id]
        if len(units) != 1:
            raise KeyError(f"unit is not present in run: {unit_id}")
        return run, plan, units[0]

    @staticmethod
    def _artifact_for_unit(root: Path, plan: dict[str, Any], unit_id: str, filename: str) -> tuple[Path | None, dict[str, Any] | None]:
        base = root / str(plan["language"]).casefold() / str(plan["version"]) / str(plan["planRunId"])
        for path in base.glob(f"*/{filename}"):
            value = _read_json(path)
            if value and (value.get("unit") or {}).get("unitId") == unit_id:
                return path, value
            if value and value.get("unitId") == unit_id:
                return path, value
        return None, None

    @staticmethod
    def _claim_refs_for_mapping(
        mapping: dict[str, Any], mappings_by_name: dict[str, dict[str, Any]],
        *, default_unit_id: str | None = None, seen: tuple[str, ...] = (),
    ) -> list[tuple[str, str]]:
        """Resolve only claim relationships explicitly recorded by a manifest.

        ``supportsDeclarations`` is itself a persisted relationship, so following
        it is safe for implementation helpers. Names and source text are never
        used to manufacture a semantic association.
        """
        name = str(mapping.get("declaration", ""))
        if name in seen:
            return []
        result: list[tuple[str, str]] = []
        for ref in _list(mapping.get("claimRefs")):
            if not isinstance(ref, dict):
                continue
            unit_id, claim_id = ref.get("unitId"), ref.get("claimId")
            if isinstance(unit_id, str) and isinstance(claim_id, str):
                pair = (unit_id, claim_id)
                if pair not in result:
                    result.append(pair)
        if default_unit_id is not None:
            for claim_id in _list(mapping.get("semanticClaimIds")):
                if isinstance(claim_id, str):
                    pair = (default_unit_id, claim_id)
                    if pair not in result:
                        result.append(pair)
        for supported in _list(mapping.get("supportsDeclarations")):
            target = mappings_by_name.get(str(supported))
            if target is None:
                continue
            for pair in ArtifactRepository._claim_refs_for_mapping(
                target, mappings_by_name, default_unit_id=default_unit_id,
                seen=(*seen, name),
            ):
                if pair not in result:
                    result.append(pair)
        return result

    def _translation(self, plan: dict[str, Any], unit_id: str) -> tuple[Path | None, str, dict[str, Any] | None, list[dict[str, Any]]]:
        base = self.roots.translations / str(plan["language"]).casefold() / str(plan["version"]) / str(plan["planRunId"])
        for manifest_path in base.glob("*/translation-manifest.json"):
            manifest = _read_json(manifest_path)
            if not manifest:
                continue
            schema = manifest.get("schemaVersion")
            grouped = schema in {2, 3}
            relevant = grouped and unit_id in (manifest.get("group") or {}).get("unitIds", [])
            relevant = relevant or not grouped and (manifest.get("unit") or {}).get("unitId") == unit_id
            if not relevant:
                continue
            lean_path = manifest_path.parent / str(manifest.get("leanFile") or "Unit.lean")
            try:
                source = lean_path.read_text(encoding="utf-8")
            except OSError:
                source = ""
            raw_mappings = [
                dict(item) for item in _list(manifest.get("declarations"))
                if isinstance(item, dict)
            ]
            by_name = {
                str(item["declaration"]): item for item in raw_mappings
                if isinstance(item.get("declaration"), str)
            }
            mappings = []
            default_unit_id = None if grouped else unit_id
            for item in raw_mappings:
                refs = self._claim_refs_for_mapping(
                    item, by_name, default_unit_id=default_unit_id
                )
                mappings.append({
                    **item,
                    "semanticClaimIds": [
                        claim_id for ref_unit, claim_id in refs
                        if ref_unit == unit_id
                    ],
                    "origin": "UNIT_DECLARATION",
                    "sourceDocumentId": "unit",
                })
            return lean_path, source, manifest, mappings
        return None, "", None, []

    def _shared_translation(
        self, plan: dict[str, Any], unit_id: str,
        group_manifest: dict[str, Any] | None,
    ) -> tuple[dict[str, Any] | None, list[dict[str, str]]]:
        """Load the exact frozen core referenced by this group, if used by the unit."""
        if not isinstance(group_manifest, dict):
            return None, []
        reference = group_manifest.get("sharedCore")
        if not isinstance(reference, dict):
            return None, []
        relevant_uses = []
        for use in _list(group_manifest.get("sharedUses")):
            if not isinstance(use, dict):
                continue
            refs = _list(use.get("claimRefs"))
            if any(isinstance(ref, dict) and ref.get("unitId") == unit_id for ref in refs):
                relevant_uses.append(use)
        if not relevant_uses:
            return None, []
        warning_target = str(reference.get("coreRunId", "shared core"))
        try:
            core = load_core(
                self.roots.translations, plan, str(reference.get("coreRunId", ""))
            )
            expected = {
                key: reference.get(key)
                for key in ("coreRunId", "manifestHash", "sourceHash", "leanModule")
            }
            if core.reference() != expected:
                raise ValueError("translation binding does not match the immutable shared-core snapshot")
        except (FileNotFoundError, KeyError, OSError, TypeError, ValueError) as exc:
            return None, [{
                "type": "BROKEN_SHARED_CORE_REFERENCE",
                "source": warning_target,
                "target": str(exc),
            }]

        raw_mappings = [
            dict(item) for item in _list(core.manifest.get("declarations"))
            if isinstance(item, dict)
        ]
        by_name = {
            str(item["declaration"]): item for item in raw_mappings
            if isinstance(item.get("declaration"), str)
        }
        used_names = {
            str(name)
            for use in relevant_uses
            for name in _list(use.get("leanDeclarations"))
            if isinstance(name, str)
        }
        # A helper may explicitly support another registered declaration. Keep
        # that target inspectable, but never expand by name or source similarity.
        changed = True
        while changed:
            before = len(used_names)
            used_names.update(
                str(name)
                for declaration in tuple(used_names)
                for name in _list(by_name.get(declaration, {}).get("supportsDeclarations"))
                if isinstance(name, str)
            )
            used_names.update(
                name for name, mapping in by_name.items()
                if any(
                    isinstance(supported, str) and supported in used_names
                    for supported in _list(mapping.get("supportsDeclarations"))
                )
            )
            changed = len(used_names) != before
        mappings = []
        for item in raw_mappings:
            name = str(item.get("declaration", ""))
            refs = self._claim_refs_for_mapping(item, by_name)
            mappings.append({
                **item,
                "semanticClaimIds": [
                    claim_id for ref_unit, claim_id in refs
                    if ref_unit == unit_id and name in used_names
                ],
                "usedBySelectedUnit": name in used_names,
                "origin": "SHARED_CORE_DECLARATION",
                "sourceDocumentId": "shared-core",
            })
        return {
            "reference": core.reference(),
            "source": core.source,
            "filename": str(core.source_path.relative_to(core.directory)),
            "leanModule": core.lean_module,
            "manifest": core.manifest,
            "mappings": mappings,
        }, []

    @staticmethod
    def _declaration_ranges(
        source: str, mappings: list[dict[str, Any]], *, filename: str | None,
        origin: str, source_document_id: str,
    ) -> list[dict[str, Any]]:
        lines = source.splitlines()
        computed = declaration_source_ranges(source, filename or "Unit.lean")
        kinds = lean_declarations(source)
        found = [{
            "declaration": name,
            "localName": name.rsplit(".", 1)[-1],
            "kind": kinds.get(name),
            "startLine": value["startLine"],
            "endLine": value["endLine"],
        } for name, value in computed.items()]
        by_name = {item["declaration"]: item for item in found}
        mappings_by_name = {
            str(item["declaration"]): item for item in mappings
            if isinstance(item.get("declaration"), str)
        }
        result = []
        for location in found:
            name = location["declaration"]
            mapping = mappings_by_name.get(name)
            recorded = (mapping or {}).get("sourceRange")
            if (
                isinstance(recorded, dict)
                and isinstance(recorded.get("startLine"), int)
                and isinstance(recorded.get("endLine"), int)
                and 1 <= recorded["startLine"] <= recorded["endLine"] <= len(lines)
                and (
                    not filename
                    or recorded.get("file") in {filename, Path(filename).name}
                    or Path(str(recorded.get("file", ""))).name == Path(filename).name
                )
            ):
                location = {
                    **location,
                    "startLine": recorded["startLine"],
                    "endLine": recorded["endLine"],
                }
            result.append({
                **(mapping or {}), **location,
                "origin": origin,
                "sourceDocumentId": source_document_id,
                "mappingRecorded": mapping is not None,
                "sourceRange": {
                    "file": filename,
                    "startLine": location["startLine"],
                    "endLine": location["endLine"],
                },
                "broken": False,
            })
        for name, mapping in mappings_by_name.items():
            if name in by_name:
                continue
            recorded = mapping.get("sourceRange")
            location = None
            if (
                isinstance(recorded, dict)
                and isinstance(recorded.get("startLine"), int)
                and isinstance(recorded.get("endLine"), int)
                and 1 <= recorded["startLine"] <= recorded["endLine"] <= len(lines)
                and (
                    not filename
                    or recorded.get("file") in {filename, Path(filename).name}
                    or Path(str(recorded.get("file", ""))).name == Path(filename).name
                )
            ):
                location = {
                    "declaration": name,
                    "localName": name.rsplit(".", 1)[-1],
                    "kind": None,
                    "startLine": recorded["startLine"],
                    "endLine": recorded["endLine"],
                }
            result.append({
                **mapping,
                **(location or {
                    "declaration": name,
                    "localName": name.rsplit(".", 1)[-1],
                    "kind": None,
                    "startLine": None,
                    "endLine": None,
                }),
                "origin": origin,
                "sourceDocumentId": source_document_id,
                "mappingRecorded": True,
                "sourceRange": ({
                    "file": filename,
                    "startLine": location["startLine"],
                    "endLine": location["endLine"],
                } if location else None),
                "broken": location is None,
            })
        return sorted(
            result,
            key=lambda item: (
                item.get("startLine") is None,
                item.get("startLine") or 0,
                str(item.get("declaration", "")),
            ),
        )

    @staticmethod
    def _check_navigation(
        item: dict[str, Any], declarations: set[str], claims: set[str],
        evidence: set[str],
    ) -> dict[str, list[str]]:
        """Extract navigable artifact IDs from structured diagnostic fields only."""
        declaration_ids: list[str] = []
        claim_ids: list[str] = []
        evidence_ids: list[str] = []

        def add(target: list[str], value: Any, known: set[str]) -> None:
            if isinstance(value, str) and value in known and value not in target:
                target.append(value)

        add(declaration_ids, item.get("declaration"), declarations)
        for value in item.get("declarations", []) if isinstance(item.get("declarations"), list) else []:
            add(declaration_ids, value, declarations)
        add(claim_ids, item.get("claimId"), claims)
        add(claim_ids, item.get("semanticClaimId"), claims)
        for value in item.get("semanticClaimIds", []) if isinstance(item.get("semanticClaimIds"), list) else []:
            add(claim_ids, value, claims)
        for ref in item.get("claimRefs", []) if isinstance(item.get("claimRefs"), list) else []:
            if isinstance(ref, dict):
                add(claim_ids, ref.get("claimId"), claims)
        add(evidence_ids, item.get("evidenceId"), evidence)
        for value in item.get("evidenceIds", []) if isinstance(item.get("evidenceIds"), list) else []:
            add(evidence_ids, value, evidence)
        item_id = item.get("itemId")
        add(claim_ids, item_id, claims)
        add(evidence_ids, item_id, evidence)
        return {
            "declarations": declaration_ids,
            "claims": claim_ids,
            "evidence": evidence_ids,
        }

    @classmethod
    def _checks_with_navigation(
        cls, value: Any, declarations: set[str], claims: set[str],
        evidence: set[str],
    ) -> Any:
        if isinstance(value, list):
            return [
                cls._checks_with_navigation(item, declarations, claims, evidence)
                for item in value
            ]
        if not isinstance(value, dict):
            return value
        result = {
            key: cls._checks_with_navigation(item, declarations, claims, evidence)
            for key, item in value.items()
        }
        navigation = cls._check_navigation(value, declarations, claims, evidence)
        if any(navigation.values()):
            result["navigation"] = navigation
        return result

    def get_unit(self, run_id: str, unit_id: str) -> dict[str, Any]:
        run, plan, unit = self._context(run_id, unit_id)
        evidence_path, evidence_artifact = self._artifact_for_unit(self.roots.evidence, plan, unit_id, "evidence.json")
        semantics_path, semantic_artifact = self._artifact_for_unit(self.roots.semantics, plan, unit_id, "semantics.json")
        check_path, check = self._artifact_for_unit(self.roots.checks, plan, unit_id, "check.json")
        lean_path, source, manifest, mappings = self._translation(plan, unit_id)
        unit_filename = lean_path.name if lean_path else None
        unit_declarations = self._declaration_ranges(
            source, mappings, filename=unit_filename,
            origin="UNIT_DECLARATION", source_document_id="unit",
        )
        shared, shared_warnings = self._shared_translation(plan, unit_id, manifest)
        shared_declarations = self._declaration_ranges(
            shared["source"], shared["mappings"], filename=shared["filename"],
            origin="SHARED_CORE_DECLARATION", source_document_id="shared-core",
        ) if shared else []
        declarations = [*unit_declarations, *shared_declarations]
        claims = list(((semantic_artifact or {}).get("semantics") or {}).get("claims") or [])
        evidence = list((evidence_artifact or {}).get("evidence") or [])
        claim_by_id = {item.get("claimId"): item for item in claims}
        evidence_by_id = {item.get("evidenceId"): item for item in evidence}
        warnings: list[dict[str, str]] = list(shared_warnings)
        for declaration in declarations:
            declaration["claims"] = []
            for claim_id in declaration.get("semanticClaimIds", []):
                claim = claim_by_id.get(claim_id)
                if claim:
                    declaration["claims"].append(claim_id)
                else:
                    warnings.append({"type": "BROKEN_CLAIM_REFERENCE", "source": declaration.get("declaration", ""), "target": str(claim_id)})
            declaration["mapped"] = bool(declaration["claims"])
            if declaration.get("broken"):
                warnings.append({
                    "type": "MISSING_LEAN_DECLARATION",
                    "source": str(declaration.get("declaration", "")),
                    "target": str(declaration.get("sourceRange") or declaration.get("sourceDocumentId", "")),
                })
        declaration_by_claim: dict[str, list[dict[str, str]]] = {}
        for declaration in declarations:
            if declaration.get("broken"):
                continue
            for claim_id in declaration.get("claims", []):
                item = {
                    "declaration": declaration["declaration"],
                    "origin": declaration["origin"],
                    "sourceDocumentId": declaration["sourceDocumentId"],
                }
                if item not in declaration_by_claim.setdefault(claim_id, []):
                    declaration_by_claim[claim_id].append(item)
        normalized_claims = []
        for claim in claims:
            missing = [item for item in claim.get("evidenceIds", []) if item not in evidence_by_id]
            warnings.extend({"type": "BROKEN_EVIDENCE_REFERENCE", "source": claim.get("claimId", ""), "target": str(item)} for item in missing)
            implementation = declaration_by_claim.get(claim.get("claimId"), [])
            normalized_claims.append({
                **claim,
                "declarations": [item["declaration"] for item in implementation],
                "declarationMappings": implementation,
                "missingEvidenceIds": missing,
            })
        claims_by_evidence: dict[str, list[str]] = {}
        for claim in claims:
            for evidence_id in claim.get("evidenceIds", []):
                claims_by_evidence.setdefault(evidence_id, []).append(claim.get("claimId"))
        normalized_evidence = []
        for item in evidence:
            used_claims = claims_by_evidence.get(item.get("evidenceId"), [])
            implementation = []
            for claim_id in used_claims:
                for mapping in declaration_by_claim.get(claim_id, []):
                    if mapping not in implementation:
                        implementation.append(mapping)
            normalized_evidence.append({
                **item,
                "usedByClaims": used_claims,
                "implementedByDeclarations": [
                    mapping["declaration"] for mapping in implementation
                ],
                "implementationMappings": implementation,
            })
        documents = [{
            "documentId": "unit",
            "label": "Unit",
            "origin": "UNIT_DECLARATION",
            "source": source,
            "filename": unit_filename,
            "available": bool(source),
            "declarations": unit_declarations,
        }]
        if shared:
            documents.append({
                "documentId": "shared-core",
                "label": "Shared core",
                "origin": "SHARED_CORE_DECLARATION",
                "source": shared["source"],
                "filename": shared["filename"],
                "available": bool(shared["source"]),
                "leanModule": shared["leanModule"],
                "reference": shared["reference"],
                "declarations": shared_declarations,
            })
        normalized_check = self._checks_with_navigation(
            check,
            {
                str(item["declaration"])
                for item in declarations
                if item.get("startLine") is not None
            },
            set(claim_by_id), set(evidence_by_id),
        ) if check else None
        return {
            "runId": run_id,
            "planRunId": plan.get("planRunId"),
            "language": plan.get("language"),
            "version": plan.get("version"),
            "unit": unit,
            "lean": {
                "source": source,
                "filename": unit_filename,
                "available": bool(source),
                "declarations": declarations,
                "documents": documents,
                "sharedCore": shared["reference"] if shared else None,
            },
            "claims": normalized_claims,
            "evidence": normalized_evidence,
            "semantics": (semantic_artifact or {}).get("semantics"),
            "checks": normalized_check,
            "repairs": self._repairs(plan, unit_id),
            "timeline": self._timeline(run, plan, unit_id, check),
            "warnings": warnings,
            "availability": {
                "evidence": evidence_path is not None,
                "semantics": semantics_path is not None,
                "translation": manifest is not None,
                "check": check_path is not None,
            },
            "raw": {
                "semantics": semantic_artifact,
                "translationManifest": manifest,
                "sharedCoreManifest": shared["manifest"] if shared else None,
                "check": check,
            },
        }

    def get_lean(self, run_id: str, unit_id: str) -> dict[str, Any]:
        return self.get_unit(run_id, unit_id)["lean"]

    def get_semantics(self, run_id: str, unit_id: str) -> dict[str, Any] | None:
        return self.get_unit(run_id, unit_id)["semantics"]

    def get_claim(self, run_id: str, unit_id: str, claim_id: str) -> dict[str, Any]:
        unit = self.get_unit(run_id, unit_id)
        matches = [claim for claim in unit["claims"] if claim.get("claimId") == claim_id]
        if len(matches) != 1:
            raise KeyError(f"claim is not present in unit: {claim_id}")
        evidence_by_id = {item.get("evidenceId"): item for item in unit["evidence"]}
        return {**matches[0], "evidence": [evidence_by_id[item] for item in matches[0].get("evidenceIds", []) if item in evidence_by_id]}

    def get_check(self, run_id: str, unit_id: str) -> dict[str, Any] | None:
        return self.get_unit(run_id, unit_id)["checks"]

    def get_repairs(self, run_id: str, unit_id: str) -> list[dict[str, Any]]:
        return self.get_unit(run_id, unit_id)["repairs"]

    def get_trace(self, run_id: str, unit_id: str, declaration_name: str) -> dict[str, Any]:
        unit = self.get_unit(run_id, unit_id)
        mappings = [item for item in unit["lean"]["declarations"] if item.get("declaration") == declaration_name]
        if len(mappings) != 1:
            raise KeyError(f"declaration is not present in unit: {declaration_name}")
        claims = [self.get_claim(run_id, unit_id, claim_id) for claim_id in mappings[0].get("claims", [])]
        return {"declaration": mappings[0], "claims": claims}

    def _repairs(self, plan: dict[str, Any], unit_id: str) -> list[dict[str, Any]]:
        base = self.roots.troubleshooting / str(plan["language"]).casefold() / str(plan["version"]) / str(plan["planRunId"])
        result = []
        for path in base.glob("*/troubleshoot.json"):
            item = _read_json(path)
            if item and (item.get("unit") or {}).get("unitId") == unit_id:
                result.append({**item, "artifact": path.name})
        return sorted(result, key=lambda item: item.get("startedAt") or "")

    def _timeline(self, run: dict[str, Any], plan: dict[str, Any], unit_id: str, check: dict[str, Any] | None) -> list[dict[str, Any]]:
        phases: list[tuple[str, str, dict[str, Any] | None]] = [("Index", str((run.get("phase1") or {}).get("disposition", "UNKNOWN")), run.get("phase1"))]
        planner_path = self.roots.plans / str(plan["language"]).casefold() / str(plan["version"]) / str(plan["planRunId"]) / "planner-run.json"
        planner = _read_json(planner_path)
        phases.append(("Planner", str((run.get("plan") or {}).get("disposition") or (planner or {}).get("outcome") or "NOT_STARTED"), planner))
        _, evidence = self._artifact_for_unit(self.roots.evidence, plan, unit_id, "retriever-run.json")
        _, semantics = self._artifact_for_unit(self.roots.semantics, plan, unit_id, "extractor-run.json")
        lean_path, _, _, _ = self._translation(plan, unit_id)
        translation = _read_json(lean_path.parent / "translator-run.json") if lean_path else None
        phases.extend([("Evidence", (evidence or {}).get("outcome", "NOT_STARTED"), evidence), ("Semantics", (semantics or {}).get("outcome", "NOT_STARTED"), semantics), ("Translator", (translation or {}).get("outcome", "NOT_STARTED"), translation)])
        phases.append(("Check", (check or {}).get("status", "NOT_STARTED"), (check or {}).get("build")))
        repairs = self._repairs(plan, unit_id)
        if repairs:
            phases.append(("Troubleshooter", str(repairs[-1].get("reason") or "USED"), repairs[-1]))
        return [{"phase": name, "status": status, "durationMs": _duration_ms(metadata)} for name, status, metadata in phases]

    def get_evidence_source(self, run_id: str, unit_id: str, evidence_id: str) -> dict[str, Any]:
        data = self.get_unit(run_id, unit_id)
        items = [item for item in data["evidence"] if item.get("evidenceId") == evidence_id]
        if len(items) != 1:
            raise KeyError(f"evidence is not present in unit: {evidence_id}")
        item = items[0]
        database = self.roots.indexes / str(data["language"]).casefold() / str(data["version"]) / "specification.sqlite"
        source_nodes = []
        if database.is_file():
            try:
                connection = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
                connection.row_factory = sqlite3.Row
                for node_id in item.get("sourceNodeIds") or [item.get("sourceNodeId")]:
                    if not node_id:
                        continue
                    row = connection.execute(
                        """SELECT n.node_id,n.document_id,n.node_type,n.title,n.section_number,n.raw_text,n.page_start,n.page_end,n.html_anchor,
                                  d.source_type,d.title AS document_title,d.local_path,d.official_url
                           FROM nodes n JOIN documents d USING(document_id) WHERE n.node_id=?""", (node_id,),
                    ).fetchone()
                    if not row:
                        source_nodes.append({"nodeId": node_id, "broken": True})
                        continue
                    node = dict(row)
                    node["sourceSpans"] = [dict(span) for span in connection.execute("SELECT * FROM source_spans WHERE node_id=? ORDER BY ordinal", (node_id,))]
                    source_nodes.append(node)
                connection.close()
            except sqlite3.Error as exc:
                source_nodes.append({"broken": True, "error": str(exc)})
        preview = self._preview_metadata(item, source_nodes)
        if preview.get("type") == "pdf" and preview.get("page"):
            preview["rendered"] = True
            preview["imageUrl"] = (
                f"/api/runs/{run_id}/units/{unit_id}/evidence/{evidence_id}/preview"
            )
        return {"evidence": item, "sourceNodes": source_nodes, "preview": preview}

    def render_pdf_preview(self, run_id: str, unit_id: str, evidence_id: str) -> bytes:
        source = self.get_evidence_source(run_id, unit_id, evidence_id)
        item = source["evidence"]
        preview = source["preview"]
        if preview.get("type") != "pdf" or not preview.get("page"):
            raise KeyError("PDF preview is unavailable for this evidence")
        path = Path(str(item.get("sourcePath", ""))).resolve()
        try:
            path.relative_to(self.roots.repository)
        except ValueError as exc:
            raise KeyError("evidence source is outside the repository") from exc
        if path.suffix.casefold() != ".pdf" or not path.is_file():
            raise KeyError("evidence PDF source is unavailable")
        import pymupdf as fitz

        document = fitz.open(path)
        try:
            page_number = int(preview["page"])
            if page_number < 1 or page_number > document.page_count:
                raise KeyError("evidence PDF page is outside the document")
            page = document[page_number - 1]
            bbox = preview.get("bbox")
            if isinstance(bbox, list) and len(bbox) == 4 and all(value is not None for value in bbox):
                page.draw_rect(
                    fitz.Rect(*[float(value) for value in bbox]),
                    color=(0.10, 0.70, 0.65), fill=(0.10, 0.70, 0.65),
                    fill_opacity=0.16, width=1.6, overlay=True,
                )
            return page.get_pixmap(matrix=fitz.Matrix(1.45, 1.45), alpha=False).tobytes("png")
        finally:
            document.close()

    @staticmethod
    def _preview_metadata(item: dict[str, Any], source_nodes: list[dict[str, Any]]) -> dict[str, Any]:
        spans = [span for node in source_nodes for span in node.get("sourceSpans", [])]
        if item.get("sourceType") == "pdf":
            span = next((span for span in spans if span.get("page_number")), None)
            return {"type": "pdf", "page": item.get("pdfPage") or (span or {}).get("page_number"), "bbox": item.get("bbox") or ([span.get(k) for k in ("bbox_x0", "bbox_y0", "bbox_x1", "bbox_y1")] if span else None), "rendered": False}
        span = next((span for span in spans if span.get("dom_path")), None)
        return {"type": "html", "anchor": item.get("htmlAnchor"), "domPath": (span or {}).get("dom_path"), "sourceLineStart": (span or {}).get("source_line_start"), "sourceLineEnd": (span or {}).get("source_line_end"), "exactText": item.get("exactText")}

    def search(self, run_id: str, query: str) -> list[dict[str, Any]]:
        needle = query.casefold().strip()
        if not needle:
            return []
        results = []
        for unit in self.list_units(run_id):
            if needle in str(unit.get("name", "")).casefold() or needle in str(unit.get("unitId", "")).casefold():
                results.append({"type": "unit", "unitId": unit["unitId"], "label": unit["name"], "detail": "Instruction"})
            try:
                data = self.get_unit(run_id, unit["unitId"])
            except KeyError:
                continue
            for declaration in data["lean"]["declarations"]:
                if needle in str(declaration.get("declaration", "")).casefold():
                    results.append({
                        "type": "declaration", "unitId": unit["unitId"],
                        "id": declaration.get("declaration"),
                        "label": declaration.get("localName"),
                        "detail": declaration.get("origin"),
                    })
            for claim in data["claims"]:
                if needle in (str(claim.get("claimId", "")) + " " + str(claim.get("statement", ""))).casefold():
                    results.append({"type": "claim", "unitId": unit["unitId"], "id": claim.get("claimId"), "label": claim.get("statement"), "detail": claim.get("kind")})
            for evidence in data["evidence"]:
                haystack = " ".join(str(evidence.get(key, "")) for key in ("evidenceId", "exactText", "sourceNodeId", "role"))
                if needle in haystack.casefold():
                    results.append({"type": "evidence", "unitId": unit["unitId"], "id": evidence.get("evidenceId"), "label": evidence.get("exactText"), "detail": evidence.get("role")})
            if len(results) >= 50:
                break
        return results[:50]
