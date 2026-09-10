from __future__ import annotations

import json
import re
import shutil
import sqlite3
import urllib.parse
from pathlib import Path
from types import SimpleNamespace

import pymupdf as fitz
import pytest

from spec2lean.gui.repository import ArtifactRepository
from spec2lean.gui.server import GuiHandler


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
        "schemaVersion": 1, "language": language, "version": version, "planRunId": plan_id, "graphStatus": "ACYCLIC",
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
        "unit": {"unitId": unit_id, "name": "shl.b32"}, "semantics": {"claims": claims, "operation": {"description": "Shift left", "evidenceIds": ["evidence:html"]}, "edgeCases": [{"behavior": "Clamp", "evidenceIds": ["evidence:pdf"]}]},
    })
    put(tmp_path / "semantics" / language / version / plan_id / artifact_dir / "extractor-run.json", {"unitId": unit_id, "outcome": "SUCCESS"})
    translation = tmp_path / "translations" / language / version / plan_id / artifact_dir
    translation.mkdir(parents=True)
    (translation / "Unit.lean").write_text("namespace Spec2Lean.Ptx.ShlB32\n\ndef shlResult (a b : UInt32) := a <<< b.toNat\n\ndef execute (a b : UInt32) := shlResult a b\n\nend Spec2Lean.Ptx.ShlB32\n", encoding="utf-8")
    put(translation / "translation-manifest.json", {
        "schemaVersion": 1, "language": language, "version": version, "planRunId": plan_id, "leanFile": "Unit.lean",
        "unit": {"unitId": unit_id, "name": "shl.b32"}, "declarations": [
            {"declaration": "Spec2Lean.Ptx.ShlB32.shlResult", "role": "OPERATION", "semanticClaimIds": ["claim:op", "claim:broken"]},
            {"declaration": "Spec2Lean.Ptx.ShlB32.execute", "role": "EXECUTION", "semanticClaimIds": ["claim:op"]},
            {"declaration": "Spec2Lean.Ptx.ShlB32.notInSource", "role": "SEMANTIC_HELPER", "semanticClaimIds": ["claim:op"]},
        ],
    })
    check = {
        "unit": {"unitId": unit_id}, "status": "PASS",
        "build": {"status": "PASS", "durationMs": 42, "diagnostics": [{"severity": "INFO", "message": "clean"}]},
        "coverage": {"status": "PASS", "covered": [{"itemId": "claim:op", "declarations": ["Spec2Lean.Ptx.ShlB32.shlResult"]}], "uncovered": []},
        "traceability": {"status": "PASS", "validMappings": [{"declaration": "Spec2Lean.Ptx.ShlB32.shlResult", "semanticClaimIds": ["claim:op"]}], "brokenMappings": []},
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
    assert operation["startLine"] == 3
    assert operation["claims"] == ["claim:op", "claim:broken"]
    claim = next(item for item in unit["claims"] if item["claimId"] == "claim:op")
    assert claim["evidenceIds"] == ["evidence:html", "evidence:pdf"]
    html = next(item for item in unit["evidence"] if item["evidenceId"] == "evidence:html")
    assert html["usedByClaims"] == ["claim:op"]
    assert "Spec2Lean.Ptx.ShlB32.shlResult" in html["implementedByDeclarations"]
    trace = gui_repository.get_trace("pipeline-run:complete", "unit:shl", "Spec2Lean.Ptx.ShlB32.shlResult")
    assert trace["claims"][0]["evidence"][0]["exactText"] == "Shift a left by b."
    assert any(item["type"] == "BROKEN_EVIDENCE_REFERENCE" for item in unit["warnings"])
    assert next(item for item in unit["lean"]["declarations"] if item["declaration"].endswith("notInSource"))["broken"]


def test_failed_subtree_run_shows_planned_scope_before_unit_execution(gui_repository: ArtifactRepository) -> None:
    root = gui_repository.roots.repository
    put(root / "runs/ptx/9.3/pipeline-run:blocked/run.json", {
        "pipelineRunId": "pipeline-run:blocked", "planRunId": "plan:complete", "status": "FAILED",
        "request": {"language": "ptx", "version": "9.3", "scope": {"mode": "SOURCE_SUBTREE", "sourceNodeId": "node:html"}},
        "units": {}, "error": "Dependency cycle",
    })
    run = gui_repository.get_run("pipeline-run:blocked")
    assert run["requested"] == 1
    assert run["requestedNames"] == ["shl.b32"]
    assert run["completed"] == 0
    assert run["units"][0]["stages"]["evidence"] == "NOT_STARTED"


def test_html_and_pdf_phase1_provenance_and_preview(gui_repository: ArtifactRepository) -> None:
    html = gui_repository.get_evidence_source("pipeline-run:complete", "unit:shl", "evidence:html")
    assert html["preview"] == {"type": "html", "anchor": "logic-shl", "domPath": "/html/body/section", "sourceLineStart": 12, "sourceLineEnd": 12, "exactText": "Shift a left by b."}
    assert html["sourceNodes"][0]["raw_text"] == "Shift a left by b."
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
    assert unit["checks"]["traceability"]["brokenMappings"] == []
    assert unit["repairs"][0]["hashes"]["after"]["Unit.lean"] == "new"
    durations = {item["phase"]: item["durationMs"] for item in unit["timeline"]}
    assert durations["Evidence"] == 2000
    assert durations["Check"] == 42
    assert durations["Semantics"] is None
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


def test_experiment_runs_keep_their_own_artifacts_and_indexes(gui_repository: ArtifactRepository) -> None:
    root = gui_repository.roots.repository
    original = root / "runs/ptx/9.3/pipeline-run:complete/run.json"
    original_bytes = original.read_bytes()
    # Deliberately reuse plan and unit IDs with different contents in two jobs.
    # Only their run IDs differ; resolving by language/version would mix them.
    for runtime in ("opencode", "rust-harness"):
        job = root / "runs/experiments/paired/jobs" / runtime
        run_id = f"pipeline-run:{runtime}"
        run = json.loads(original_bytes)
        run["pipelineRunId"] = run_id
        put(job / "runs/ptx/9.3" / run_id / "run.json", run)
        put(job / "state.json", {"runtime": runtime, "indexMode": "semantic"})
        for category in ("plans", "evidence", "semantics", "translations", "checks", "troubleshooting", "indexes"):
            shutil.copytree(root / category / "ptx", job / ("index" if category == "indexes" else category) / "ptx")
        lean = job / "translations/ptx/9.3/plan:complete/shl-b32-shl/Unit.lean"
        lean.write_text(lean.read_text() + f"\n-- {runtime}\n")
        with sqlite3.connect(job / "index/ptx/9.3/specification.sqlite") as db:
            db.execute("UPDATE nodes SET raw_text=? WHERE node_id='node:html'", (runtime,))

        # The explorer existed before this job was created; discovery stays live.
        item = next(item for item in gui_repository.list_runs() if item["runId"] == run_id)
        assert (item["experiment"], item["runtime"], item["indexMode"]) == ("paired", runtime, "semantic")
        overview = gui_repository.get_run(run_id)
        assert overview["runtime"] == runtime
        assert overview["layers"][0]["units"][0]["unitId"] == "unit:shl"
        assert gui_repository.get_lean(run_id, "unit:shl")["source"].endswith(f"-- {runtime}\n")
        assert gui_repository.get_check(run_id, "unit:shl")["status"] == "PASS"
        assert gui_repository.get_semantics(run_id, "unit:shl")["operation"]["description"] == "Shift left"
        assert gui_repository.get_repairs(run_id, "unit:shl")
        assert gui_repository.search(run_id, "shift")
        trace = gui_repository.get_trace(run_id, "unit:shl", "Spec2Lean.Ptx.ShlB32.shlResult")
        assert trace["claims"][0]["evidence"]
        source = gui_repository.get_evidence_source(run_id, "unit:shl", "evidence:html")
        assert source["sourceNodes"][0]["raw_text"] == runtime
        assert source["preview"]["domPath"] == "/html/body/section"
        assert gui_repository.render_pdf_preview(run_id, "unit:shl", "evidence:pdf").startswith(b"\x89PNG")

    assert len(gui_repository.list_runs()) == 4
    assert original.read_bytes() == original_bytes
    assert "-- opencode" not in gui_repository.get_lean("pipeline-run:complete", "unit:shl")["source"]
    with pytest.raises(KeyError, match="unknown or ambiguous"):
        gui_repository.get_run("pipeline-run:unknown")
    # A duplicate run ID must not silently select a different job's artifacts.
    duplicate = json.loads(original_bytes)
    duplicate["pipelineRunId"] = "pipeline-run:opencode"
    put(root / "runs/ptx/9.3/pipeline-run:opencode/run.json", duplicate)
    with pytest.raises(KeyError, match="unknown or ambiguous"):
        gui_repository.get_unit("pipeline-run:opencode", "unit:shl")


def test_frontend_contains_primary_traceability_interactions() -> None:
    static = Path(__file__).parents[1] / "src/spec2lean/gui/static"
    script = (static / "app.js").read_text(encoding="utf-8")
    stylesheet = (static / "styles.css").read_text(encoding="utf-8")
    for interaction in ("selectDeclaration", "selectClaim", "selectEvidence", "implementedByDeclarations", "global-search"):
        assert interaction in script
    assert ".trace-grid" in stylesheet and ".pdf-preview" in stylesheet


def test_frontend_serves_one_script_and_versions_updated_assets(tmp_path, monkeypatch) -> None:
    from spec2lean.gui import server

    static = tmp_path / "static"
    shutil.copytree(server.STATIC_ROOT, static)
    monkeypatch.setattr(server, "STATIC_ROOT", static)
    handler = object.__new__(GuiHandler)
    captured = []
    handler._send = lambda status, body, content_type: captured.append(body.decode())

    handler._static("/")
    original = captured.pop()
    script_urls = re.findall(r'<script src="([^"]+)"', original)
    assert len(script_urls) == 1
    assert script_urls[0].startswith("/app.js?v=")
    assert '/styles.css?v=' in original

    # A cached older shell only requests /app.js; it must get intake as well.
    handler._static("/app.js")
    script = captured.pop()
    assert "function showNewSpecification()" in script
    assert "function showHome()" in script
    assert script.startswith("(() => {")  # Isolate it from a cached intake.js.

    for name in ("intake.js", "app.js", "styles.css"):
        with (static / name).open("a") as output:
            output.write("\n/* updated */\n")
        handler._static("/")
        updated = captured.pop()
        assert re.findall(r'<script src="([^"]+)"', updated) != script_urls
        script_urls = re.findall(r'<script src="([^"]+)"', updated)
