"""Loopback-only local web interface for TARA-App."""

from __future__ import annotations

import json
import mimetypes
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

from tara_app.application.facade import ApplicationFacade
from tara_app.skills.loader import SkillLoadError

_WEB_ROOT = Path(__file__).with_name("web")
_ASSETS = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/app.css": ("app.css", "text/css; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
}
_MAX_REQUEST_BYTES = 1_000_000


def _react_ui_enabled() -> bool:
    """Keep the feature-complete static UI as default until React parity is verified."""
    return os.environ.get("TARA_ENABLE_REACT_UI", "").strip() == "1"


class _Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address: tuple[str, int], app: ApplicationFacade) -> None:
        self.app = app
        super().__init__(address, _Handler)


class _Handler(BaseHTTPRequestHandler):
    server: _Server
    protocol_version = "HTTP/1.1"

    def do_GET(self) -> None:
        endpoint = urlsplit(self.path).path
        if endpoint == "/api/skills":
            if not self._local_origin():
                self._json(403, {"status": "permission_denied", "error": "request origin is not allowed"})
                return
            self._json(200, self.server.app.skill_catalogue())
            return
        if endpoint == "/api/health":
            if not self._local_origin():
                self._json(403, {"status": "permission_denied", "error": "request origin is not allowed"})
                return
            self._json(200, self.server.app.health_status())
            return
        if endpoint == "/api/mcp/catalogue":
            if not self._local_origin():
                self._json(403, {"status": "permission_denied", "error": "request origin is not allowed"})
                return
            from tara_app.mcp_catalogue import list_mcp_integrations
            self._json(200, list_mcp_integrations())
            return
        if endpoint in {"/api/mcp/status", "/api/mcp/tools", "/api/mcp/audit"}:
            if not self._local_origin():
                self._json(403, {"status": "permission_denied", "error": "request origin is not allowed"})
                return
            if endpoint == "/api/mcp/status":
                self._json(200, self.server.app.mcp_status())
                return
            query = parse_qs(urlsplit(self.path).query, keep_blank_values=True)
            if endpoint == "/api/mcp/audit":
                if set(query) - {"limit"} or any(len(values) != 1 for values in query.values()):
                    self._json(400, {"status": "invalid_request", "error": "query parameters are invalid"})
                    return
                try:
                    limit = int(query.get("limit", ["50"])[0])
                    self._json(200, self.server.app.mcp_audit_log(limit))
                except ValueError:
                    self._json(400, {"status": "invalid_request", "error": "audit limit must be between 1 and 100"})
                return
            if set(query) - {"server"} or any(len(values) != 1 for values in query.values()):
                self._json(400, {"status": "invalid_request", "error": "query parameters are invalid"})
                return
            server_name = query.get("server", [None])[0]
            if server_name == "":
                self._json(400, {"status": "invalid_request", "error": "server must not be empty"})
                return
            try:
                tools = self.server.app.list_mcp_tools(server_name)
            except ValueError:
                self._json(409, {"status": "unavailable", "error": "MCP is disabled or the server is unavailable"})
                return
            except RuntimeError:
                self._json(502, {"status": "failed", "error": "MCP tool discovery failed"})
                return
            self._json(200, {"status": "ok", "tools": tools})
            return
        if endpoint == "/api/models":
            if not self._local_origin():
                self._json(403, {"status": "permission_denied", "error": "request origin is not allowed"})
                return
            payload = self.server.app.model_catalogue()
            status_code = 200 if payload.get("status") == "available" else 503
            self._json(status_code, payload)
            return
        # Prefer the compiled React frontend when a build is present. The
        # original static UI remains a safe fallback for source-only installs.
        react_root = (_WEB_ROOT / "react-dist").resolve()
        react_file: Path | None = None
        if _react_ui_enabled() and react_root.is_dir():
            if endpoint == "/":
                react_file = react_root / "index.html"
            elif endpoint.startswith("/assets/"):
                candidate = (react_root / endpoint.lstrip("/")).resolve()
                if candidate.is_relative_to(react_root) and candidate.is_file():
                    react_file = candidate
        if react_file is not None:
            try:
                content = react_file.read_bytes()
            except OSError:
                self._json(500, {"status": "failed", "error": "compiled React asset is unavailable"})
                return
            content_type = mimetypes.guess_type(react_file.name)[0] or "application/octet-stream"
            if content_type == "text/html":
                content_type += "; charset=utf-8"
            elif content_type in {"text/css", "text/javascript"}:
                content_type += "; charset=utf-8"
        else:
            asset = _ASSETS.get(endpoint)
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
        if endpoint not in {"/api/chat", "/api/approve", "/api/cancel", "/api/models/pull", "/api/models/unload", "/api/models/remove"}:
            self._json(404, {"status": "unavailable", "error": "endpoint not found"})
            return
        if not self._local_origin(require_origin=True):
            self._json(403, {"status": "permission_denied", "error": "a valid same-origin request is required"})
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
        if endpoint == "/api/chat":
            fields = {"question", "session_id", "attachments", "history", "skill"}
        elif endpoint in {"/api/models/pull", "/api/models/unload", "/api/models/remove"}:
            fields = {"specialist"}
        else:
            fields = {"approval_id", "session_id"}
        if not isinstance(payload, dict) or set(payload) - fields:
            self._json(400, {"status": "invalid_request", "error": "request fields are invalid"})
            return
        if endpoint in {"/api/models/pull", "/api/models/unload", "/api/models/remove"}:
            if set(payload) != {"specialist"}:
                self._json(400, {"status": "invalid_request", "error": "specialist is required"})
                return
            action = {
                "/api/models/pull": "pull",
                "/api/models/unload": "unload",
                "/api/models/remove": "remove",
            }[endpoint]
            try:
                result = self.server.app.model_lifecycle_action(action, payload["specialist"])
            except ValueError:
                self._json(400, {"status": "invalid_request", "error": "specialist is not configured"})
                return
            except RuntimeError:
                self._json(409, {"status": "unavailable", "error": "model lifecycle action could not be completed"})
                return
            if result is None:
                self._json(409, {"status": "unavailable", "error": "model lifecycle is managed by OmniRoute"})
                return
            status_code = 202 if action == "pull" else 200
            result_status = "accepted" if action == "pull" else result["status"]
            response_key = "pull" if action == "pull" else "model"
            self._json(status_code, {"status": result_status, response_key: result})
            return
        if endpoint == "/api/chat":
            if "history" in payload:
                try:
                    self.server.app.replace_conversation_history(
                        payload.get("session_id", "default"),
                        payload["history"],
                    )
                except ValueError:
                    self._json(400, {"status": "invalid_request", "error": "conversation history is invalid"})
                    return
            skill = payload.get("skill")
            if skill is not None and (
                not isinstance(skill, str) or not skill.strip() or len(skill) > 64
            ):
                self._json(400, {"status": "invalid_request", "error": "skill name is invalid"})
                return
            try:
                outcome = self.server.app.handle_question(
                    payload.get("question"),
                    session_id=payload.get("session_id", "default"),
                    attachments=payload.get("attachments", []),
                    skill=skill.strip() if isinstance(skill, str) else None,
                )
            except SkillLoadError:
                self._json(400, {"status": "invalid_request", "error": "selected skill is unavailable or invalid"})
                return
        elif endpoint == "/api/approve":
            outcome = self.server.app.approve(payload.get("approval_id"), session_id=payload.get("session_id"))
        else:
            outcome = self.server.app.cancel_approval(payload.get("approval_id"), session_id=payload.get("session_id"))
        self._json(200, outcome.to_payload())

    def _local_origin(self, *, require_origin: bool = False) -> bool:
        host = self.headers.get("Host", "")
        if host not in {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}:
            return False
        origin = self.headers.get("Origin")
        if origin is None:
            return not require_origin
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


def serve(app: ApplicationFacade, *, port: int = 8765) -> None:
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
