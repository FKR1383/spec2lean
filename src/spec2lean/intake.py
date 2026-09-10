"""PDF intake shared by the CLI and local GUI, using the existing pipeline artifacts."""
from __future__ import annotations

import fcntl
import json
import os
import re
import shlex
import tempfile
import urllib.request
import uuid
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
from typing import Any, BinaryIO, Callable
from urllib.parse import urlsplit

from .pipeline.runner import PipelineOptions, _write_json_atomic, run_pipeline, utc_now
from .planning.models import PlanningRequest
from .runtime import runtime_name
from .util import sha256_file


MAX_PDF_BYTES = 256 * 1024 * 1024
COMPONENT = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,99}\Z")
INTAKE_ID = re.compile(r"[a-f0-9]{32}\Z")


def validate_request(request: PlanningRequest) -> None:
    for label, value in (("language", request.language), ("version", request.version)):
        if not COMPONENT.fullmatch(value):
            raise ValueError(f"{label} must start with a letter or number and contain only letters, numbers, '.', '_' or '-' (up to 100 characters)")


def validate_url(value: str | None) -> str | None:
    if not value:
        return None
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("source URL must be an HTTP(S) URL without credentials")
    return value


def intake_root(workspace: Path) -> Path:
    return workspace.resolve() / "runs" / "intake"


def intake_path(workspace: Path, intake_id: str) -> Path:
    if not INTAKE_ID.fullmatch(intake_id):
        raise ValueError("invalid specification ID")
    return intake_root(workspace) / intake_id / "intake.json"


def load_intake(workspace: Path, intake_id: str) -> dict[str, Any]:
    return json.loads(intake_path(workspace, intake_id).read_text(encoding="utf-8"))


def list_intakes(workspace: Path) -> list[dict[str, Any]]:
    records = []
    for path in intake_root(workspace).glob("*/intake.json"):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(record, dict) and INTAKE_ID.fullmatch(record.get("id", "")):
                records.append(record)
        except (OSError, ValueError):
            continue
    return sorted(records, key=lambda item: item["createdAt"], reverse=True)


@contextmanager
def _lock(workspace: Path, name: str):
    root = intake_root(workspace)
    root.mkdir(parents=True, exist_ok=True)
    with (root / f".{name}.lock").open("a") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("This specification is already being processed. Wait for it to finish and retry.") from exc
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def copy_pdf(stream: BinaryIO, destination: Path, *, length: int | None = None) -> None:
    """Copy a bounded stream, optionally reading exactly one HTTP request body."""
    if length is not None and not 0 < length <= MAX_PDF_BYTES:
        raise ValueError("PDF must be non-empty and no larger than 256 MiB")
    total = 0
    with destination.open("wb") as output:
        while length is None or total < length:
            chunk = stream.read(min(1024 * 1024, length - total) if length is not None else 1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_PDF_BYTES:
                raise ValueError("PDF exceeds the 256 MiB limit")
            output.write(chunk)
    if total == 0 or (length is not None and total != length):
        raise ValueError("PDF upload is empty or incomplete")


def _pdf_metadata(path: Path) -> dict[str, Any]:
    import fitz

    try:
        with fitz.open(path) as document:
            if not document.is_pdf or document.needs_pass or not document.page_count:
                raise ValueError("Use a valid, non-empty PDF without password protection")
            if not any(page.get_text().strip() for page in document):
                raise ValueError("This PDF has no extractable text. Apply OCR before uploading it.")
            return {"pageCount": document.page_count, "pdfMetadata": document.metadata or {}}
    except (RuntimeError, fitz.FileDataError) as exc:
        raise ValueError(f"Cannot read this PDF: {exc}") from exc


def prepare_specification(
    workspace: Path, request: PlanningRequest, *, pdf: Path | None = None,
    pdf_url: str | None = None, source_url: str | None = None,
    title: str = "", publisher: str = "", original_name: str | None = None,
) -> dict[str, Any]:
    validate_request(request)
    if (pdf is None) == (pdf_url is None):
        raise ValueError("provide exactly one PDF file or PDF URL")
    source_url = validate_url(source_url or pdf_url)
    if len(title) > 500 or len(publisher) > 500:
        raise ValueError("title and publisher must be at most 500 characters")
    workspace = workspace.resolve()
    sources = workspace / "documents" / "sources"
    sources.mkdir(parents=True, exist_ok=True)
    # Stage on the same filesystem so publishing the source directory is atomic.
    with tempfile.TemporaryDirectory(prefix=".intake-", dir=sources) as temporary:
        stage = Path(temporary) / "source"
        (stage / "raw").mkdir(parents=True)
        staged_pdf = stage / "raw" / "specification.pdf"
        if pdf is not None:
            with pdf.open("rb") as stream:
                copy_pdf(stream, staged_pdf)
        else:
            validate_url(pdf_url)
            try:
                with urllib.request.urlopen(urllib.request.Request(pdf_url, headers={"User-Agent": "Spec2Lean/1.0"}), timeout=60) as stream:
                    validate_url(stream.geturl())
                    copy_pdf(stream, staged_pdf)
            except OSError as exc:
                raise ValueError(f"Could not download PDF: {exc}") from exc
        metadata = _pdf_metadata(staged_pdf)
        digest = sha256_file(staged_pdf)
        title = title.strip() or metadata["pdfMetadata"].get("title") or f"{request.language} {request.version}"
        created = utc_now()
        manifest = {
            "schema_version": 1, "publisher": publisher.strip() or "User supplied",
            "document_title": title, "language": request.language,
            "specification_version": request.version, "source_classification": "user_supplied",
            "retrieved_at_utc": created, "semantic_status": "not_started",
            "artifacts": [{"kind": "pdf", "url": source_url, "local_path": "raw/specification.pdf",
                           "sha256": digest, "size_bytes": staged_pdf.stat().st_size,
                           "original_filename": Path(original_name or (pdf.name if pdf else urlsplit(pdf_url).path)).name,
                           "page_count": metadata["pageCount"], "pdf_metadata": metadata["pdfMetadata"]}],
        }
        _write_json_atomic(stage / "source-manifest.json", manifest)
        (stage / "SHA256SUMS").write_text(f"{digest}  raw/specification.pdf\n", encoding="utf-8")
        (stage / ".gitignore").write_text("raw/\n", encoding="utf-8")
        language = request.language.casefold()
        with _lock(workspace, "register"):
            matches = list(sources.glob(f"*/{language}/{request.version}/source-manifest.json"))
            matches += list(sources.glob(f"{language}/{request.version}/source-manifest.json"))
            reused = bool(matches)
            if matches:
                if len(matches) != 1:
                    raise ValueError("Multiple source manifests already use this language and version; choose a unique identity")
                manifest_path = matches[0]
                existing = json.loads(manifest_path.read_text(encoding="utf-8"))
                artifacts = existing.get("artifacts", [])
                matching = [item for item in artifacts if item.get("kind") == "pdf" and item.get("sha256") == digest]
                if len(matching) != 1:
                    raise FileExistsError("A different specification already uses this language and version. Choose a new version or language; existing sources are never overwritten.")
                managed_pdf = (manifest_path.parent / matching[0]["local_path"]).resolve()
                if not managed_pdf.is_relative_to(sources) or not managed_pdf.is_file() or sha256_file(managed_pdf) != digest:
                    raise ValueError("The existing source is missing or changed; restore it or choose a new version")
            else:
                if (workspace / "indexes" / language / request.version).exists():
                    raise FileExistsError("An index already uses this language and version without a source manifest; choose a new identity")
                destination = sources / "uploads" / language / request.version
                destination.parent.mkdir(parents=True, exist_ok=True)
                if destination.exists():
                    raise FileExistsError("Source directory already exists; choose a new language or version")
                stage.rename(destination)
                manifest_path = destination / "source-manifest.json"
                managed_pdf = destination / "raw" / "specification.pdf"
            intake_id = uuid.uuid4().hex
            record_path = intake_path(workspace, intake_id)
            request_path = record_path.with_name("request.json")
            _write_json_atomic(request_path, request.to_dict())
            record = {
                "schemaVersion": 1, "id": intake_id, "title": title, "publisher": publisher.strip(),
                "createdAt": created, "updatedAt": created, "status": "PREPARED",
                "request": request.to_dict(), "requestPath": str(request_path),
                "sourceManifest": str(manifest_path), "pdfPath": str(managed_pdf),
                "sha256": digest, "sourceUrl": source_url, "sourceReused": reused,
                "pageCount": metadata["pageCount"], "pipelineRunId": None,
                "nextCommand": shlex.join(["spec2lean", "start", intake_id, "--workspace", str(workspace)]),
            }
            _write_json_atomic(record_path, record)
            return record


def pipeline_options(workspace: Path, *, until: str = "index", mode: str = "lexical") -> PipelineOptions:
    workspace = workspace.resolve()
    return PipelineOptions(
        repository_root=workspace, index_root=workspace / "indexes", plans_root=workspace / "plans",
        evidence_root=workspace / "evidence", semantics_root=workspace / "semantics",
        translations_root=workspace / "translations", checks_root=workspace / "checks",
        troubleshooting_root=workspace / "troubleshooting", runs_root=workspace / "runs",
        until_phase=until, index_mode=mode,
    )


def start_specification(
    workspace: Path, intake_id: str, *, until: str = "troubleshoot", mode: str = "lexical",
    progress: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    record = load_intake(workspace, intake_id)
    request = PlanningRequest.from_dict(record["request"])
    validate_request(request)
    # A hash avoids collisions between different language/version component boundaries.
    import hashlib
    key = hashlib.sha256(json.dumps([request.language.casefold(), request.version]).encode()).hexdigest()
    with _lock(workspace, key):
        record = load_intake(workspace, intake_id)
        options = pipeline_options(workspace, until=until, mode=mode)
        if record.get("pipelineRunId") and record.get("indexMode", "lexical") == mode:
            options = replace(options, resume=record["pipelineRunId"])
        record.update(status="RUNNING", error=None, untilPhase=until, indexMode=mode, runtime=runtime_name(),
                      workerPid=os.getpid(), updatedAt=utc_now())
        path = intake_path(workspace, intake_id)
        _write_json_atomic(path, record)

        def report(message: str) -> None:
            run_id = message.split(" ", 1)[0]
            if run_id.startswith("pipeline-run:") and record.get("pipelineRunId") != run_id:
                record["pipelineRunId"] = run_id
                _write_json_atomic(path, record)
            if progress:
                progress(message)

        try:
            _, run = run_pipeline(request, options, progress=report)
            record.update(status="INDEXED" if until == "index" else run["status"], phase1=run["phase1"],
                          pipelineRunId=run["pipelineRunId"])
        except (Exception, KeyboardInterrupt) as exc:
            record.update(status="INTERRUPTED" if isinstance(exc, KeyboardInterrupt) else "FAILED", error=str(exc) or "Interrupted")
            raise
        finally:
            record["updatedAt"] = utc_now()
            _write_json_atomic(path, record)
        return record
