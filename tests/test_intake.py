from __future__ import annotations

import io
import json
import subprocess
import sys
import time
from pathlib import Path

import fitz
import pytest

from spec2lean.database import connect
from spec2lean.gui.intake import IntakeJobs
from spec2lean.gui.repository import ArtifactRepository
from spec2lean.intake import copy_pdf, load_intake, prepare_specification, start_specification
from spec2lean.planning.models import PlanningRequest
from spec2lean.util import sha256_file
from spec2lean.validation import validate_database


@pytest.fixture
def intake_pdf(tmp_path: Path) -> Path:
    path = tmp_path / "input.pdf"
    with fitz.open() as document:
        page = document.new_page()
        page.insert_text((72, 72), "1 Message specification", fontsize=20)
        page.insert_text((72, 120), "Get reads a value. Put writes a value.")
        document.set_metadata({"title": "Message specification", "author": "Example publisher"})
        document.set_toc([[1, "1 Message specification", 1]])
        document.save(path)
    return path


def test_import_build_and_reuse_preserve_source_provenance(tmp_path, intake_pdf):
    workspace = tmp_path / "workspace"
    request = PlanningRequest.exact("messages", "1.0", ["Get", "Put"])
    record = prepare_specification(workspace, request, pdf=intake_pdf, source_url="https://example.test/spec.pdf")
    manifest_path = Path(record["sourceManifest"])
    manifest = json.loads(manifest_path.read_text())
    assert record["title"] == "Message specification"
    assert record["sha256"] == sha256_file(intake_pdf)
    assert Path(record["pdfPath"]).read_bytes() == intake_pdf.read_bytes()
    assert manifest["source_classification"] == "user_supplied"
    assert manifest["artifacts"][0]["local_path"] == "raw/specification.pdf"
    assert record["sha256"] in (manifest_path.parent / "SHA256SUMS").read_text()
    assert json.loads(Path(record["requestPath"]).read_text()) == request.to_dict()
    original_manifest = manifest_path.read_bytes()

    indexed = start_specification(workspace, record["id"], until="index")
    assert indexed["status"] == "INDEXED"
    with connect(Path(indexed["phase1"]["database"]), read_only=True) as db:
        assert validate_database(db)["ok"]
        document = db.execute("SELECT * FROM documents").fetchone()
        assert document["official_url"] == "https://example.test/spec.pdf"
        assert document["sha256"] == record["sha256"]
    assert list((workspace / "indexes/messages/1.0/text").glob("*.pages.txt"))
    run = ArtifactRepository.at(workspace).get_run(indexed["pipelineRunId"])
    assert run["status"] == "COMPLETE"
    again = prepare_specification(workspace, PlanningRequest.full("messages", "1.0"), pdf=intake_pdf)
    assert again["sourceReused"] and again["id"] != record["id"]
    assert manifest_path.read_bytes() == original_manifest
    reused = start_specification(workspace, again["id"], until="index")
    assert reused["phase1"]["disposition"] == "REUSED"


def test_cli_init_and_start_work_in_a_fresh_workspace(tmp_path, intake_pdf):
    workspace = tmp_path / "workspace with spaces"
    result = subprocess.run([sys.executable, "-m", "spec2lean", "init", "--pdf", str(intake_pdf),
                             "--language", "messages", "--version", "1.0", "--units", "Get,Put",
                             "--workspace", str(workspace)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    record = json.loads(result.stdout)
    assert record["status"] == "INDEXED"
    assert record["request"]["scope"]["instructions"] == ["Get", "Put"]
    result = subprocess.run([sys.executable, "-m", "spec2lean", "start", record["id"],
                             "--workspace", str(workspace), "--until", "index"], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["pipelineRunId"] == record["pipelineRunId"]


def test_conflicting_sources_and_bad_identifiers_never_overwrite(tmp_path, intake_pdf):
    workspace = tmp_path / "workspace"
    request = PlanningRequest.full("messages", "1.0")
    record = prepare_specification(workspace, request, pdf=intake_pdf)
    original = Path(record["pdfPath"]).read_bytes()
    with fitz.open(intake_pdf) as document:
        document[0].insert_text((72, 170), "A changed specification.")
        document.saveIncr()
    with pytest.raises(FileExistsError, match="different specification"):
        prepare_specification(workspace, request, pdf=intake_pdf)
    assert Path(record["pdfPath"]).read_bytes() == original
    for language, version in [("../outside", "1"), ("messages", "../1"), ("x*", "1"), ("/tmp", "1")]:
        with pytest.raises(ValueError, match="must start"):
            prepare_specification(workspace, PlanningRequest.full(language, version), pdf=intake_pdf)


@pytest.mark.parametrize("kind", ["invalid", "blank", "encrypted"])
def test_unusable_pdfs_leave_no_registered_source(tmp_path, intake_pdf, kind):
    if kind == "invalid":
        intake_pdf.write_bytes(b"This is not a PDF")
    elif kind == "blank":
        with fitz.open() as document:
            document.new_page()
            document.save(intake_pdf)
    else:
        encrypted = tmp_path / "encrypted.pdf"
        with fitz.open(intake_pdf) as document:
            document.save(encrypted, encryption=fitz.PDF_ENCRYPT_AES_256, owner_pw="owner", user_pw="secret")
        intake_pdf = encrypted
    workspace = tmp_path / "workspace"
    with pytest.raises(ValueError):
        prepare_specification(workspace, PlanningRequest.full("messages", "1"), pdf=intake_pdf)
    assert not list(workspace.rglob("source-manifest.json"))
    assert not list(workspace.rglob("intake.json"))


def test_download_and_stream_limits(tmp_path, intake_pdf, monkeypatch):
    class Response(io.BytesIO):
        def geturl(self):
            return "https://example.test/spec.pdf"
    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **kw: Response(intake_pdf.read_bytes()))
    record = prepare_specification(tmp_path / "workspace", PlanningRequest.full("messages", "1"), pdf_url="https://example.test/spec.pdf")
    assert record["sourceUrl"] == "https://example.test/spec.pdf"
    with pytest.raises(ValueError, match="HTTP"):
        prepare_specification(tmp_path / "workspace", PlanningRequest.full("messages", "2"), pdf_url="file:///etc/passwd")
    monkeypatch.setattr("spec2lean.intake.MAX_PDF_BYTES", 5)
    with pytest.raises(ValueError, match="limit"):
        copy_pdf(io.BytesIO(b"123456"), tmp_path / "overflow")
    with pytest.raises(ValueError, match="incomplete"):
        copy_pdf(io.BytesIO(b"123"), tmp_path / "short", length=4)


def test_gui_background_job_finishes_and_survives_reload(tmp_path, intake_pdf):
    workspace = tmp_path / "workspace"
    record = prepare_specification(workspace, PlanningRequest.exact("messages", "1", ["Get"]), pdf=intake_pdf)
    jobs = IntakeJobs(workspace)
    try:
        assert jobs.start(record["id"])["status"] == "QUEUED"
        with pytest.raises(RuntimeError, match="already running"):
            jobs.start(record["id"])
        deadline = time.monotonic() + 20
        while jobs.get(record["id"])["status"] in {"QUEUED", "RUNNING", "PREPARED"} and time.monotonic() < deadline:
            time.sleep(.05)
        result = jobs.get(record["id"])
        assert result["status"] == "INDEXED", result
        assert "phase 1/7" in result["log"]
    finally:
        jobs.close()
    reloaded = IntakeJobs(workspace)
    assert reloaded.list()[0]["status"] == "INDEXED"
    assert load_intake(workspace, record["id"])["pipelineRunId"]
    reloaded.close()


def test_failed_index_can_be_retried_with_the_saved_request(tmp_path, intake_pdf):
    workspace = tmp_path / "workspace"
    record = prepare_specification(workspace, PlanningRequest.full("messages", "1"), pdf=intake_pdf)
    source = Path(record["pdfPath"])
    original = source.read_bytes()
    source.write_bytes(b"changed")
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        start_specification(workspace, record["id"], until="index")
    failed = load_intake(workspace, record["id"])
    assert failed["status"] == "FAILED"
    assert failed["pipelineRunId"]
    source.write_bytes(original)
    recovered = start_specification(workspace, record["id"], until="index")
    assert recovered["status"] == "INDEXED"
    assert recovered["pipelineRunId"] == failed["pipelineRunId"]


def test_upload_api_requires_token_and_validates_metadata(tmp_path, intake_pdf):
    from email.message import Message
    from types import SimpleNamespace
    from urllib.parse import quote
    from spec2lean.gui.server import GuiHandler

    jobs = IntakeJobs(tmp_path / "workspace")
    server = SimpleNamespace(repository=ArtifactRepository.at(tmp_path / "workspace"),
                             server_address=("127.0.0.1", 8000), csrf_token="test-token", intakes=jobs)
    body = intake_pdf.read_bytes()
    metadata = {"request": PlanningRequest.exact("messages", "1", ["Get"]).to_dict(), "filename": "../../input.pdf"}

    def post(*, token="test-token", origin="http://127.0.0.1:8000", host="127.0.0.1:8000", content=body, data=metadata):
        handler = object.__new__(GuiHandler)
        handler.server = server
        handler.path = "/api/specifications"
        handler.headers = Message()
        for key, value in {"Host": host, "Origin": origin, "X-Spec2Lean-Token": token,
                           "Content-Length": str(len(content)), "Content-Type": "application/pdf",
                           "X-Spec2Lean-Metadata": quote(json.dumps(data))}.items():
            handler.headers[key] = value
        handler.connection = SimpleNamespace(settimeout=lambda timeout: None)
        handler.rfile = io.BytesIO(content)
        captured = []
        handler._json = lambda value, status=200: captured.append((status, value))
        handler.do_POST()
        return captured[0]

    assert post(token="")[0] == 403
    assert post(origin="https://unrelated.test")[0] == 403
    assert post(host="unrelated.test")[0] == 400
    assert post(data=[])[0] == 400
    assert post(content=b"not a pdf")[0] == 400
    assert not jobs.list()
    status, result = post()
    assert status == 201, result
    assert result["status"] == "PREPARED"
    assert Path(result["pdfPath"]).name == "specification.pdf"
    assert result["request"]["scope"]["instructions"] == ["Get"]
    assert jobs.list()[0]["id"] == result["id"]
