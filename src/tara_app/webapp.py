"""Loopback-only local web interface for TARA-App."""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from tara_app.orchestrator import Orchestrator

_WEB_ROOT = Path(__file__).with_name("web")
_ASSETS = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/app.css": ("app.css", "text/css; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
}
_MAX_REQUEST_BYTES = 1_000_000


class _Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address: tuple[str, int], app: Orchestrator) -> None:
        self.app = app
        super().__init__(address, _Handler)


class _Handler(BaseHTTPRequestHandler):
    server: _Server
    protocol_version = "HTTP/1.1"

    def do_GET(self) -> None:
        asset = _ASSETS.get(urlsplit(self.path).path)
        if asset is None:
            self._json(404, {"status": "unavailable", "error": "page not found"})
            return
        filename, content_type = asset
        try:
            content = (_WEB_ROOT / filename).read_bytes()
        except OSError:
            self._json(500, {"status": "failed", "error": "local app asset is unavailable"})
            return
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; connect-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(content)

    def do_POST(self) -> None:
        endpoint = urlsplit(self.path).path
        if endpoint not in {"/api/chat", "/api/approve", "/api/cancel"}:
            self._json(404, {"status": "unavailable", "error": "endpoint not found"})
            return
        if not self._local_origin():
            self._json(403, {"status": "permission_denied", "error": "request origin is not allowed"})
            return
        if self.headers.get_content_type() != "application/json":
            self._json(415, {"status": "invalid_request", "error": "request must use application/json"})
            return
        try:
            length = int(self.headers.get("Content-Length", ""))
        except ValueError:
            self._json(411, {"status": "invalid_request", "error": "request length is invalid"})
            return
        if not 1 <= length <= _MAX_REQUEST_BYTES:
            self._json(413, {"status": "invalid_request", "error": "request exceeds the 1 MB limit"})
            return
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._json(400, {"status": "invalid_request", "error": "request must be UTF-8 JSON"})
            return
        fields = {"question", "session_id", "attachments"} if endpoint == "/api/chat" else {"approval_id", "session_id"}
        if not isinstance(payload, dict) or set(payload) - fields:
            self._json(400, {"status": "invalid_request", "error": "request fields are invalid"})
            return
        if endpoint == "/api/chat":
            outcome = self.server.app.handle_question(
                payload.get("question"),
                session_id=payload.get("session_id", "default"),
                attachments=payload.get("attachments", []),
            )
        elif endpoint == "/api/approve":
            outcome = self.server.app.approve(payload.get("approval_id"), session_id=payload.get("session_id"))
        else:
            outcome = self.server.app.cancel_approval(payload.get("approval_id"), session_id=payload.get("session_id"))
        self._json(200, outcome.to_payload())

    def _local_origin(self) -> bool:
        host = self.headers.get("Host", "")
        if host not in {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}:
            return False
        origin = self.headers.get("Origin")
        if origin is None:
            return True
        parsed = urlsplit(origin)
        return parsed.scheme == "http" and parsed.netloc == host and parsed.path in {"", "/"} and not parsed.query and not parsed.fragment

    def _json(self, status: int, payload: dict[str, Any]) -> None:
        encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, format: str, *args: object) -> None:
        # Do not log prompts, attachment names, or provider responses.
        return


def serve(app: Orchestrator, *, port: int = 8765) -> None:
    """Serve the local UI on loopback only until interrupted."""
    if not 1024 <= port <= 65535:
        raise ValueError("port must be between 1024 and 65535")
    server = _Server(("127.0.0.1", port), app)
    try:
        print(f"TARA-App is ready at http://127.0.0.1:{port}")
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nTARA-App stopped")
    finally:
        server.server_close()

