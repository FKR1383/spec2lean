from __future__ import annotations

import hashlib
import json
import mimetypes
import secrets
import tempfile
import urllib.parse
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from .repository import ArtifactRepository
from .intake import IntakeJobs
from ..intake import MAX_PDF_BYTES, copy_pdf, prepare_specification, validate_request
from ..planning.models import PlanningRequest


STATIC_ROOT = Path(__file__).with_name("static")


def _javascript_bundle() -> bytes:
    # Keep app.js self-contained for cached pages that predate the intake script.
    # The private scope also tolerates pages that already loaded intake.js.
    scripts = [(STATIC_ROOT / name).read_bytes() for name in ("intake.js", "app.js")]
    return b"(() => {\n" + b"\n".join(scripts) + b"\n})();\n"


class GuiServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address: tuple[str, int], repository: ArtifactRepository, initial_run: str | None = None):
        self.repository = repository
        self.initial_run = initial_run
        self.csrf_token = secrets.token_urlsafe(32)
        self.intakes = IntakeJobs(repository.roots.repository)
        super().__init__(address, GuiHandler)

    def server_close(self) -> None:
        self.intakes.close()
        super().server_close()


class GuiHandler(BaseHTTPRequestHandler):
    server: GuiServer

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store" if content_type.startswith("application/json") else "no-cache")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, value: Any, status: int = HTTPStatus.OK) -> None:
        self._send(status, json.dumps(value, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

    def do_GET(self) -> None:
        parsed = urllib.parse.urlsplit(self.path)
        try:
            self._check_host()
            if parsed.path.startswith("/api/"):
                self._api(parsed)
            else:
                self._static(parsed.path)
        except KeyError as exc:
            self._json({"error": str(exc.args[0] if exc.args else exc)}, HTTPStatus.NOT_FOUND)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            self._json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)

    def _check_host(self) -> None:
        hostname = urllib.parse.urlsplit("//" + self.headers.get("Host", "")).hostname
        allowed = {"localhost", "127.0.0.1", "::1", str(self.server.server_address[0])}
        if hostname not in allowed:
            raise ValueError("unrecognized GUI host")

    def do_POST(self) -> None:
        self.close_connection = True
        try:
            self._check_host()
            if not secrets.compare_digest(self.headers.get("X-Spec2Lean-Token", ""), self.server.csrf_token):
                return self._json({"error": "Reload the GUI before submitting changes"}, HTTPStatus.FORBIDDEN)
            origin = self.headers.get("Origin")
            if origin and origin != "http://" + self.headers.get("Host", ""):
                return self._json({"error": "cross-origin changes are not allowed"}, HTTPStatus.FORBIDDEN)
            length = int(self.headers.get("Content-Length", "0"))
            path = urllib.parse.urlsplit(self.path).path
            if path == "/api/specifications":
                if self.headers.get_content_type() != "application/pdf":
                    raise ValueError("upload must use application/pdf")
                if not 0 < length <= MAX_PDF_BYTES:
                    return self._json({"error": "PDF must be non-empty and no larger than 256 MiB"}, HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
                raw_metadata = self.headers.get("X-Spec2Lean-Metadata", "")
                if len(raw_metadata) > 16000:
                    raise ValueError("specification metadata is too large")
                metadata = json.loads(urllib.parse.unquote(raw_metadata))
                if not isinstance(metadata, dict) or not isinstance(metadata.get("request"), dict):
                    raise ValueError("specification request is required")
                request = PlanningRequest.from_dict(metadata["request"])
                validate_request(request)
                for field in ("title", "publisher", "sourceUrl", "filename"):
                    if not isinstance(metadata.get(field, ""), str):
                        raise ValueError(f"{field} must be text")
                self.connection.settimeout(60)
                with tempfile.TemporaryDirectory(prefix="spec2lean-upload-") as temporary:
                    pdf = Path(temporary) / "upload.pdf"
                    copy_pdf(self.rfile, pdf, length=length)
                    record = prepare_specification(
                        self.server.repository.roots.repository, request, pdf=pdf,
                        source_url=metadata.get("sourceUrl"), title=metadata.get("title", ""),
                        publisher=metadata.get("publisher", ""), original_name=metadata.get("filename"),
                    )
                return self._json(record, HTTPStatus.CREATED)
            parts = path.strip("/").split("/")
            if len(parts) == 4 and parts[:2] == ["api", "specifications"] and parts[3] == "start":
                if not 0 < length <= 4096:
                    raise ValueError("invalid start request size")
                options = json.loads(self.rfile.read(length))
                if not isinstance(options, dict):
                    raise ValueError("start options must be an object")
                return self._json(self.server.intakes.start(
                    parts[2], until=options.get("until", "index"), runtime=options.get("runtime", "rust-harness"),
                    mode=options.get("indexMode", "lexical"),
                ), HTTPStatus.ACCEPTED)
            raise KeyError("unknown API endpoint")
        except (KeyError, FileNotFoundError) as exc:
            self._json({"error": str(exc)}, HTTPStatus.NOT_FOUND)
        except (FileExistsError, RuntimeError) as exc:
            self._json({"error": str(exc)}, HTTPStatus.CONFLICT)
        except (OSError, ValueError, TypeError, AttributeError) as exc:
            self._json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)

    def _api(self, parsed: urllib.parse.SplitResult) -> None:
        repo = self.server.repository
        parts = [urllib.parse.unquote(item) for item in parsed.path.split("/") if item][1:]
        query = urllib.parse.parse_qs(parsed.query)
        if parts == ["config"]:
            return self._json({"initialRun": self.server.initial_run, "csrfToken": self.server.csrf_token,
                               "maxPdfBytes": MAX_PDF_BYTES})
        if parts == ["specifications"]:
            return self._json(self.server.intakes.list())
        if len(parts) == 2 and parts[0] == "specifications":
            return self._json(self.server.intakes.get(parts[1]))
        if parts == ["runs"]:
            return self._json(repo.list_runs())
        if len(parts) == 2 and parts[0] == "runs":
            return self._json(repo.get_run(parts[1]))
        if len(parts) == 3 and parts[0] == "runs" and parts[2] == "units":
            return self._json(repo.list_units(parts[1]))
        if len(parts) == 4 and parts[0] == "runs" and parts[2] == "units":
            return self._json(repo.get_unit(parts[1], parts[3]))
        if len(parts) == 5 and parts[0] == "runs" and parts[2] == "units" and parts[4] == "lean":
            return self._json(repo.get_lean(parts[1], parts[3]))
        if len(parts) == 5 and parts[0] == "runs" and parts[2] == "units" and parts[4] == "semantics":
            return self._json(repo.get_semantics(parts[1], parts[3]))
        if len(parts) == 6 and parts[0] == "runs" and parts[2] == "units" and parts[4] == "claims":
            return self._json(repo.get_claim(parts[1], parts[3], parts[5]))
        if len(parts) == 5 and parts[0] == "runs" and parts[2] == "units" and parts[4] == "checks":
            return self._json(repo.get_check(parts[1], parts[3]))
        if len(parts) == 5 and parts[0] == "runs" and parts[2] == "units" and parts[4] == "repairs":
            return self._json(repo.get_repairs(parts[1], parts[3]))
        if len(parts) == 5 and parts[0] == "runs" and parts[2] == "units" and parts[4] == "trace":
            return self._json(repo.get_trace(parts[1], parts[3], (query.get("declaration") or [""])[0]))
        if len(parts) == 6 and parts[0] == "runs" and parts[2] == "units" and parts[4] == "evidence":
            return self._json(repo.get_evidence_source(parts[1], parts[3], parts[5]))
        if len(parts) == 7 and parts[0] == "runs" and parts[2] == "units" and parts[4] == "evidence" and parts[6] == "preview":
            return self._send(HTTPStatus.OK, repo.render_pdf_preview(parts[1], parts[3], parts[5]), "image/png")
        if len(parts) == 3 and parts[0] == "runs" and parts[2] == "search":
            return self._json(repo.search(parts[1], (query.get("q") or [""])[0]))
        raise KeyError("unknown API endpoint")

    def _static(self, request_path: str) -> None:
        name = request_path.lstrip("/") or "index.html"
        if name not in {"index.html", "app.js", "intake.js", "styles.css"}:
            name = "index.html"
        path = STATIC_ROOT / name
        body = _javascript_bundle() if name == "app.js" else path.read_bytes()
        if name == "index.html":
            version = hashlib.sha256(_javascript_bundle() + (STATIC_ROOT / "styles.css").read_bytes()).hexdigest()[:16]
            for asset in ("app.js", "styles.css"):
                body = body.replace(f'"/{asset}"'.encode(), f'"/{asset}?v={version}"'.encode())
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        if content_type.startswith("text/") or content_type == "application/javascript":
            content_type += "; charset=utf-8"
        self._send(HTTPStatus.OK, body, content_type)


def serve(repository: ArtifactRepository, *, host: str = "127.0.0.1", port: int = 8000, initial_run: str | None = None) -> None:
    server = GuiServer((host, port), repository, initial_run)
    actual_host, actual_port = server.server_address[:2]
    print("Spec2Lean GUI running at:")
    print(f"http://{actual_host}:{actual_port}")
    try:
        server.serve_forever()
    finally:
        server.server_close()
