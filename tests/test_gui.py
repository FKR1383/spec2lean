from __future__ import annotations

import json
import sqlite3
import urllib.parse
from pathlib import Path
from types import SimpleNamespace

import pymupdf as fitz
import pytest

from spec2lean.gui.repository import ArtifactRepository
from spec2lean.gui.server import GuiHandler
from spec2lean.translation.shared_core.models import json_hash, text_hash


def put(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


@pytest.fixture()
def gui_repository(tmp_path: Path) -> ArtifactRepository:
    language, version = "ptx", "9.3"
    run_id, plan_id, unit_id = "pipeline-run:complete", "plan:complete", "unit:shl"
    partial_id = "pipeline-run:partial"
    run = {
        "schemaVersion": 1, "pipelineRunId": run_id, "planRunId": plan_id,
        "createdAt": "2026-08-28T10:00:00Z", "updatedAt": "2026-08-28T10:01:00Z", "status": "COMPLETE",
        "request": {"language": language, "version": version, "scope": {"mode": "EXACT_INSTRUCTIONS", "instructions": ["shl.b32"]}},
        "phase1": {"disposition": "REUSED", "ok": True},
        "units": {unit_id: {"name": "shl.b32", "status": "PASS", "stages": {"evidence": "BUILT", "semantics": "BUILT", "translate": "BUILT", "check": {"status": "PASS"}, "troubleshoot": {"outcome": "COMPLETE"}}}},
    }
    put(tmp_path / "runs" / language / version / run_id / "run.json", run)
    put(tmp_path / "runs" / language / version / partial_id / "run.json", {
        "pipelineRunId": partial_id, "planRunId": "plan:missing", "createdAt": "2026-08-28T11:00:00Z", "status": "FAILED", "error": "planner stopped",
        "request": {"language": language, "version": version, "scope": {"mode": "EXACT_INSTRUCTIONS", "instructions": ["broken.op"]}},
        "units": {"unit:broken": {"name": "broken.op", "status": "FAILED", "stages": {"evidence": "NOT_STARTED"}}},
    })
    plan = {
        "schemaVersion": 3, "language": language, "version": version, "planRunId": plan_id, "graphStatus": "ACYCLIC",
        "sourceDatabaseDigest": "sha256:" + "d" * 64,
        "requestedUnits": [{"unitId": unit_id, "name": "shl.b32", "sourceNodeIds": ["node:html", "node:pdf"]}],
        "processingLayers": [{"layer": 0, "unitIds": [unit_id]}], "dependencies": [],
    }
    put(tmp_path / "plans" / language / version / plan_id / "plan.json", plan)
    artifact_dir = "shl-b32-shl"
    html_evidence = {
        "evidenceId": "evidence:html", "unitId": unit_id, "tier": "CORE", "role": "OPERATION", "sourceType": "html",
        "sourceNodeId": "node:html", "sourceNodeIds": ["node:html"], "exactText": "Shift a left by b.", "sectionNumber": "9.7.8.8",
        "sectionTitle": "Logic and Shift Instructions: shl", "htmlAnchor": "logic-shl", "sourcePath": str(tmp_path / "source.html"),
    }
    pdf_path = tmp_path / "source.pdf"
    document = fitz.open(); page = document.new_page(); page.insert_text((72, 100), "Shift amounts greater than width are clamped."); document.save(pdf_path); document.close()
    (tmp_path / "source.html").write_text("<section id='logic-shl'>Shift a left by b.</section>", encoding="utf-8")
    pdf_evidence = {
        "evidenceId": "evidence:pdf", "unitId": unit_id, "tier": "SUPPORTING", "role": "EDGE_CASE", "sourceType": "pdf",
        "sourceNodeId": "node:pdf", "sourceNodeIds": ["node:pdf"], "exactText": "Shift amounts greater than width are clamped.",
        "sectionNumber": "9.7.8.8", "sectionTitle": "Logic and Shift Instructions: shl", "pdfPage": 1,
        "bbox": [70, 85, 340, 110], "sourcePath": str(pdf_path),
    }
    put(tmp_path / "evidence" / language / version / plan_id / artifact_dir / "evidence.json", {
        "unit": {"unitId": unit_id, "name": "shl.b32"}, "evidence": [html_evidence, pdf_evidence],
    })
    put(tmp_path / "evidence" / language / version / plan_id / artifact_dir / "retriever-run.json", {
        "unitId": unit_id, "outcome": "SUCCESS", "startedAt": "2026-08-28T10:00:00Z", "finishedAt": "2026-08-28T10:00:02Z",
    })
    claims = [
        {"claimId": "claim:op", "kind": "DERIVED_INTERPRETATION", "statement": "The result is a shifted left by b.", "evidenceIds": ["evidence:html", "evidence:pdf"]},
        {"claimId": "claim:broken", "kind": "ASSUMPTION", "statement": "A deliberately broken reference.", "evidenceIds": ["evidence:missing"]},
    ]
    put(tmp_path / "semantics" / language / version / plan_id / artifact_dir / "semantics.json", {
        "unit": {"unitId": unit_id, "name": "shl.b32"}, "semantics": {
            "claims": claims,
            "operation": {"description": "Shift left", "evidenceIds": ["evidence:html"]},
            "edgeCases": [{"behavior": "Clamp", "evidenceIds": ["evidence:pdf"]}],
            "dependencies": [{
                "dependencyId": "shared:value", "concept": "Shared shift operation",
                "semanticClaimIds": ["claim:op"], "evidenceIds": ["evidence:html"],
            }],
        },
    })
    put(tmp_path / "semantics" / language / version / plan_id / artifact_dir / "extractor-run.json", {"unitId": unit_id, "outcome": "SUCCESS"})
    translation = tmp_path / "translations" / language / version / plan_id / artifact_dir
    translation.mkdir(parents=True)
    unit_source = """namespace Spec2Lean.Ptx.ShlB32

/-- Exact operation documentation. -/
def shlResult (a b : UInt32) := a <<< b.toNat

def execute (a b : UInt32) := shlResult a b

def _unmappedIdentifier : Nat := 0

end Spec2Lean.Ptx.ShlB32
"""
    (translation / "Unit.lean").write_text(unit_source, encoding="utf-8")

    core_run_id = "shared-core-run:" + "a" * 24
    core_module = "Spec2LeanShared.Ptx.V93.Cfixture.Core"
    core_source = """namespace Spec2LeanShared.Ptx.V93.Cfixture

/-- Shared operation documentation. -/
def sharedShift (a b : UInt32) := a <<< b.toNat

def _sharedAdapter (a b : UInt32) := sharedShift a b

def unusedCore : Nat := 0

end Spec2LeanShared.Ptx.V93.Cfixture
"""
    core_manifest = {
        "schemaVersion": 1, "phase": "SHARED_CORE", "language": language,
        "version": version, "sourceDatabaseDigest": plan["sourceDatabaseDigest"],
        "coreRunId": core_run_id,
        "leanFile": "modules/Spec2LeanShared/Ptx/V93/Cfixture/Core.lean",
        "leanModule": core_module, "sourceHash": text_hash(core_source),
        "concepts": [{
            "dependencyId": "shared:value",
            "leanDeclarations": [
                "Spec2LeanShared.Ptx.V93.Cfixture.sharedShift",
                "Spec2LeanShared.Ptx.V93.Cfixture._sharedAdapter",
            ],
            "claimRefs": [{"unitId": unit_id, "claimId": "claim:op"}],
        }],
        "declarations": [
            {
                "declaration": "Spec2LeanShared.Ptx.V93.Cfixture.sharedShift",
                "role": "OPERATION", "dependencyIds": ["shared:value"],
                "claimRefs": [{"unitId": unit_id, "claimId": "claim:op"}],
            },
            {
                "declaration": "Spec2LeanShared.Ptx.V93.Cfixture._sharedAdapter",
                "role": "IMPLEMENTATION_HELPER", "dependencyIds": ["shared:value"],
                "claimRefs": [],
                "supportsDeclarations": ["Spec2LeanShared.Ptx.V93.Cfixture.sharedShift"],
            },
            {
                "declaration": "Spec2LeanShared.Ptx.V93.Cfixture.unusedCore",
                "role": "SEMANTIC_HELPER", "dependencyIds": ["shared:value"],
                "claimRefs": [{"unitId": "unit:other", "claimId": "claim:other"}],
            },
        ],
    }
    core_reference = {
        "coreRunId": core_run_id, "manifestHash": json_hash(core_manifest),
        "sourceHash": text_hash(core_source), "leanModule": core_module,
    }
    core_directory = tmp_path / "translations" / language / version / "shared" / "versions" / core_run_id
    (core_directory / "modules" / "Spec2LeanShared" / "Ptx" / "V93" / "Cfixture").mkdir(parents=True)
    (core_directory / "modules" / "Spec2LeanShared" / "Ptx" / "V93" / "Cfixture" / "Core.lean").write_text(core_source, encoding="utf-8")
    put(core_directory / "core-manifest.json", core_manifest)
    put(core_directory / "core-run.json", {"outcome": "SUCCESS"})

    put(translation / "translation-manifest.json", {
        "schemaVersion": 3, "language": language, "version": version,
        "planRunId": plan_id, "leanFile": "Unit.lean",
        "group": {"name": "ShiftInstructions", "unitIds": [unit_id]},
        "sharedCore": core_reference,
        "sharedUses": [{
            "dependencyId": "shared:value",
            "leanDeclarations": [
                "Spec2LeanShared.Ptx.V93.Cfixture.sharedShift",
                "Spec2LeanShared.Ptx.V93.Cfixture._sharedAdapter",
            ],
            "claimRefs": [{"unitId": unit_id, "claimId": "claim:op"}],
        }],
        "declarations": [
            {"declaration": "Spec2Lean.Ptx.ShlB32.shlResult", "role": "OPERATION", "claimRefs": [{"unitId": unit_id, "claimId": "claim:op"}, {"unitId": unit_id, "claimId": "claim:broken"}]},
            {"declaration": "Spec2Lean.Ptx.ShlB32.execute", "role": "EXECUTION", "claimRefs": [{"unitId": unit_id, "claimId": "claim:op"}]},
            {"declaration": "Spec2Lean.Ptx.ShlB32.notInSource", "role": "SEMANTIC_HELPER", "claimRefs": [{"unitId": unit_id, "claimId": "claim:op"}]},
        ],
    })
    check = {
        "unit": {"unitId": unit_id}, "status": "PASS",
        "build": {"status": "PASS", "durationMs": 42, "diagnostics": [{"severity": "INFO", "message": "clean"}]},
        "coverage": {"status": "PASS", "covered": [{"itemType": "SEMANTIC_CLAIM", "itemId": "claim:op", "declarations": ["Spec2Lean.Ptx.ShlB32.shlResult"]}], "uncovered": []},
        "traceability": {"status": "FAIL", "validMappings": [{"declaration": "Spec2Lean.Ptx.ShlB32.shlResult", "semanticClaimIds": ["claim:op"]}], "brokenMappings": [{"code": "MISSING_CLAIM_MAPPING", "declaration": "Spec2Lean.Ptx.ShlB32._unmappedIdentifier", "semanticClaimId": "claim:op", "evidenceId": "evidence:html"}]},
    }
    put(tmp_path / "checks" / language / version / plan_id / artifact_dir / "check.json", check)
    put(tmp_path / "troubleshooting" / language / version / plan_id / artifact_dir / "troubleshoot.json", {
        "unit": {"unitId": unit_id}, "startedAt": "2026-08-28T10:00:10Z", "reason": "BUILD_FAILURE",
        "hashes": {"before": {"Unit.lean": "old"}, "after": {"Unit.lean": "new"}},
        "changes": [{"description": "Added an instance.", "affectedDeclarations": ["execute"]}], "diagnostics": {"build": []},
    })
    database = tmp_path / "indexes" / language / version / "specification.sqlite"
    database.parent.mkdir(parents=True)
    connection = sqlite3.connect(database)
    connection.executescript("""
        CREATE TABLE documents(document_id TEXT PRIMARY KEY,source_type TEXT,title TEXT,local_path TEXT,official_url TEXT);
        CREATE TABLE nodes(node_id TEXT PRIMARY KEY,document_id TEXT,node_type TEXT,title TEXT,section_number TEXT,raw_text TEXT,page_start INTEGER,page_end INTEGER,html_anchor TEXT);
        CREATE TABLE source_spans(span_id TEXT PRIMARY KEY,node_id TEXT,document_id TEXT,ordinal INTEGER,page_number INTEGER,bbox_x0 REAL,bbox_y0 REAL,bbox_x1 REAL,bbox_y1 REAL,block_index INTEGER,line_index INTEGER,span_index INTEGER,dom_path TEXT,source_line_start INTEGER,source_line_end INTEGER,raw_text TEXT);
    """)
    connection.executemany("INSERT INTO documents VALUES(?,?,?,?,?)", [
        ("doc:html", "html", "PTX HTML", str(tmp_path / "source.html"), "https://example.test/ptx"),
        ("doc:pdf", "pdf", "PTX PDF", str(pdf_path), "https://example.test/ptx.pdf"),
    ])
    connection.executemany("INSERT INTO nodes VALUES(?,?,?,?,?,?,?,?,?)", [
        ("node:html", "doc:html", "paragraph", "Logic and Shift Instructions: shl", "9.7.8.8", html_evidence["exactText"], None, None, "logic-shl"),
        ("node:pdf", "doc:pdf", "paragraph", "Logic and Shift Instructions: shl", "9.7.8.8", pdf_evidence["exactText"], 1, 1, None),
    ])
    connection.executemany("INSERT INTO source_spans VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", [
        ("span:html", "node:html", "doc:html", 0, None, None, None, None, None, None, None, None, "/html/body/section", 12, 12, html_evidence["exactText"]),
        ("span:pdf", "node:pdf", "doc:pdf", 0, 1, 70, 85, 340, 110, 0, 0, 0, None, None, None, pdf_evidence["exactText"]),
    ])
    connection.commit(); connection.close()
    return ArtifactRepository.at(tmp_path)


def test_lists_complete_and_partial_runs_and_preserves_layer_order(gui_repository: ArtifactRepository) -> None:
    runs = gui_repository.list_runs()
    assert {item["runId"] for item in runs} == {"pipeline-run:complete", "pipeline-run:partial"}
    complete = gui_repository.get_run("pipeline-run:complete")
    assert complete["layers"][0]["units"][0]["name"] == "shl.b32"
    assert complete["units"][0]["stages"]["check"]["status"] == "PASS"
    partial = gui_repository.get_unit("pipeline-run:partial", "unit:broken")
    assert partial["availability"] == {"evidence": False, "semantics": False, "translation": False, "check": False}
    assert partial["lean"]["source"] == ""


def test_code_claim_evidence_and_reverse_traceability(gui_repository: ArtifactRepository) -> None:
    unit = gui_repository.get_unit("pipeline-run:complete", "unit:shl")
    operation = next(item for item in unit["lean"]["declarations"] if item["role"] == "OPERATION")
    assert operation["startLine"] == 4
    assert operation["claims"] == ["claim:op", "claim:broken"]
    execute = next(item for item in unit["lean"]["declarations"] if item.get("role") == "EXECUTION")
    assert execute["claims"] == ["claim:op"]
    claim = next(item for item in unit["claims"] if item["claimId"] == "claim:op")
    assert claim["evidenceIds"] == ["evidence:html", "evidence:pdf"]
    html = next(item for item in unit["evidence"] if item["evidenceId"] == "evidence:html")
    assert html["usedByClaims"] == ["claim:op"]
    assert "Spec2Lean.Ptx.ShlB32.shlResult" in html["implementedByDeclarations"]
    trace = gui_repository.get_trace("pipeline-run:complete", "unit:shl", "Spec2Lean.Ptx.ShlB32.shlResult")
    assert trace["claims"][0]["evidence"][0]["exactText"] == "Shift a left by b."
    assert any(item["type"] == "BROKEN_EVIDENCE_REFERENCE" for item in unit["warnings"])
    assert next(item for item in unit["lean"]["declarations"] if item["declaration"].endswith("notInSource"))["broken"]


def test_shared_core_and_reverse_relationships_are_exact_and_inspectable(
    gui_repository: ArtifactRepository,
) -> None:
    unit = gui_repository.get_unit("pipeline-run:complete", "unit:shl")
    documents = {item["documentId"]: item for item in unit["lean"]["documents"]}
    assert documents["shared-core"]["origin"] == "SHARED_CORE_DECLARATION"
    assert documents["shared-core"]["reference"] == unit["lean"]["sharedCore"]
    shared = next(
        item for item in unit["lean"]["declarations"]
        if item["declaration"].endswith(".sharedShift")
    )
    assert shared["origin"] == "SHARED_CORE_DECLARATION"
    assert shared["claims"] == ["claim:op"]
    helper = next(
        item for item in unit["lean"]["declarations"]
        if item["declaration"].endswith("._sharedAdapter")
    )
    assert helper["claims"] == ["claim:op"]
    assert helper["supportsDeclarations"] == [shared["declaration"]]
    unused = next(
        item for item in unit["lean"]["declarations"]
        if item["declaration"].endswith(".unusedCore")
    )
    assert unused["mapped"] is False and unused["claims"] == []
    trace = gui_repository.get_trace(
        "pipeline-run:complete", "unit:shl", helper["declaration"]
    )
    assert [item["claimId"] for item in trace["claims"]] == ["claim:op"]

    claim = next(item for item in unit["claims"] if item["claimId"] == "claim:op")
    assert shared["declaration"] in claim["declarations"]
    assert helper["declaration"] in claim["declarations"]
    html = next(item for item in unit["evidence"] if item["evidenceId"] == "evidence:html")
    assert html["usedByClaims"] == ["claim:op"]
    assert shared["declaration"] in html["implementedByDeclarations"]
    assert helper["declaration"] in html["implementedByDeclarations"]


def test_unmapped_code_and_check_diagnostic_navigation_use_only_recorded_ids(
    gui_repository: ArtifactRepository,
) -> None:
    unit = gui_repository.get_unit("pipeline-run:complete", "unit:shl")
    unmapped = next(
        item for item in unit["lean"]["declarations"]
        if item["declaration"].endswith("._unmappedIdentifier")
    )
    assert unmapped["mappingRecorded"] is False
    assert unmapped["mapped"] is False
    assert unmapped["claims"] == []
    diagnostic = unit["checks"]["traceability"]["brokenMappings"][0]
    assert diagnostic["navigation"] == {
        "declarations": [unmapped["declaration"]],
        "claims": ["claim:op"],
        "evidence": ["evidence:html"],
    }


def test_html_and_pdf_phase1_provenance_and_preview(gui_repository: ArtifactRepository) -> None:
    html = gui_repository.get_evidence_source("pipeline-run:complete", "unit:shl", "evidence:html")
    assert html["preview"] == {"type": "html", "anchor": "logic-shl", "domPath": "/html/body/section", "sourceLineStart": 12, "sourceLineEnd": 12, "exactText": "Shift a left by b."}
    assert html["sourceNodes"][0]["raw_text"] == "Shift a left by b."
    assert html["sourceNodes"][0]["document_id"] == "doc:html"
    assert html["sourceNodes"][0]["sourceSpans"][0]["span_id"] == "span:html"
    pdf = gui_repository.get_evidence_source("pipeline-run:complete", "unit:shl", "evidence:pdf")
    assert pdf["preview"]["page"] == 1
    assert pdf["preview"]["bbox"] == [70, 85, 340, 110]
    assert pdf["preview"]["rendered"] is True
    image = gui_repository.render_pdf_preview("pipeline-run:complete", "unit:shl", "evidence:pdf")
    assert image.startswith(b"\x89PNG")


def test_checks_repairs_search_and_read_only_http_api(gui_repository: ArtifactRepository) -> None:
    unit = gui_repository.get_unit("pipeline-run:complete", "unit:shl")
    assert unit["checks"]["build"]["diagnostics"][0]["message"] == "clean"
    assert unit["checks"]["coverage"]["uncovered"] == []
    assert unit["checks"]["traceability"]["brokenMappings"][0]["code"] == "MISSING_CLAIM_MAPPING"
    assert unit["repairs"][0]["hashes"]["after"]["Unit.lean"] == "new"
    assert {item["type"] for item in gui_repository.search("pipeline-run:complete", "shift")} >= {"claim", "evidence"}

    handler = object.__new__(GuiHandler)
    handler.server = SimpleNamespace(repository=gui_repository, initial_run=None)
    captured = []
    handler._json = lambda value, status=200: captured.append((status, value))
    handler._api(urllib.parse.urlsplit("/api/runs"))
    assert len(captured[0][1]) == 2
    captured.clear()
    handler._api(urllib.parse.urlsplit("/api/runs/pipeline-run%3Acomplete/units/unit%3Ashl"))
    assert captured[0][1]["unit"]["name"] == "shl.b32"


def test_frontend_contains_primary_traceability_interactions() -> None:
    static = Path(__file__).parents[1] / "src/spec2lean/gui/static"
    script = (static / "app.js").read_text(encoding="utf-8")
    stylesheet = (static / "styles.css").read_text(encoding="utf-8")
    for interaction in (
        "selectDeclaration", "selectClaim", "selectEvidence",
        "implementedByDeclarations", "global-search", "copyLeanSource",
        "SHARED_CORE_DECLARATION", "No semantic claim mapping recorded.",
        "data-check-declaration", "data-nav-claim",
    ):
        assert interaction in script
    assert ".trace-grid" in stylesheet and ".pdf-preview" in stylesheet
    assert ".claim-gutter" in stylesheet and "user-select:none" in stylesheet
    assert "navigator.clipboard.writeText(source)" in script


def test_copy_source_buffer_preserves_exact_lean_without_gui_annotations(
    gui_repository: ArtifactRepository,
) -> None:
    lean = gui_repository.get_lean("pipeline-run:complete", "unit:shl")
    assert "/-- Exact operation documentation. -/" in lean["source"]
    assert "def _unmappedIdentifier : Nat := 0" in lean["source"]
    assert "3 claims" not in lean["source"]
    assert "1 claim" not in lean["source"]
    assert lean["source"] == next(
        item["source"] for item in lean["documents"] if item["documentId"] == "unit"
    )
    shared = next(
        item["source"] for item in lean["documents"]
        if item["documentId"] == "shared-core"
    )
    assert "/-- Shared operation documentation. -/" in shared
    assert "def _sharedAdapter" in shared
    assert "3 claims" not in shared and "1 claim" not in shared
