from __future__ import annotations

import json
import mimetypes
import urllib.parse
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from .repository import ArtifactRepository


STATIC_ROOT = Path(__file__).with_name("static")


class GuiServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address: tuple[str, int], repository: ArtifactRepository, initial_run: str | None = None):
        super().__init__(address, GuiHandler)
        self.repository = repository
        self.initial_run = initial_run


class GuiHandler(BaseHTTPRequestHandler):
    server: GuiServer

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store" if content_type.startswith("application/json") else "public, max-age=300")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, value: Any, status: int = HTTPStatus.OK) -> None:
        self._send(status, json.dumps(value, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

    def do_GET(self) -> None:
        parsed = urllib.parse.urlsplit(self.path)
        try:
            if parsed.path.startswith("/api/"):
                self._api(parsed)
            else:
                self._static(parsed.path)
        except KeyError as exc:
            self._json({"error": str(exc.args[0] if exc.args else exc)}, HTTPStatus.NOT_FOUND)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            self._json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)

    def _api(self, parsed: urllib.parse.SplitResult) -> None:
        repo = self.server.repository
        parts = [urllib.parse.unquote(item) for item in parsed.path.split("/") if item][1:]
        query = urllib.parse.parse_qs(parsed.query)
        if parts == ["config"]:
            return self._json({"initialRun": self.server.initial_run})
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
        if name not in {"index.html", "app.js", "styles.css"}:
            name = "index.html"
        path = STATIC_ROOT / name
        body = path.read_bytes()
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
