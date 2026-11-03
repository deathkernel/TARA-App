"""One-request JSON-over-stdio adapter for TARA-App."""

from __future__ import annotations

import json
import sys
import time
from collections.abc import Mapping
from typing import Any

from tara_action.service import MODULE_ID, execute, health

MAX_REQUEST_BYTES = 1_000_000
_ALLOWED = {"schema_version", "request_id", "session_id", "module", "action", "inputs", "workspace_root", "timeout_seconds", "approval_token"}


def _reply(request_id: str, status: str, data: dict[str, Any] | None = None, error: str | None = None, duration_ms: int = 0) -> dict[str, Any]:
    return {"schema_version": "1.0", "request_id": request_id, "status": status, "data": data or {}, "error": error, "duration_ms": duration_ms}


def handle_request(request: Any) -> dict[str, Any]:
    if not isinstance(request, Mapping) or set(request) - _ALLOWED:
        return _reply("unknown", "invalid_request", error="request shape is invalid")
    request_id = request.get("request_id")
    if not isinstance(request_id, str) or not request_id.strip() or len(request_id) > 128:
        return _reply("unknown", "invalid_request", error="request_id is invalid")
    if request.get("schema_version") != "1.0" or request.get("module") != MODULE_ID:
        return _reply(request_id, "invalid_request", error="module or schema version is invalid")
    action, inputs = request.get("action"), request.get("inputs", {})
    if not isinstance(action, str) or not isinstance(inputs, Mapping):
        return _reply(request_id, "invalid_request", error="action or inputs are invalid")
    if action == "health":
        return _reply(request_id, "success", {"healthy": health()})
    start = time.monotonic()
    try:
        status, data, error = execute(action, dict(inputs), approval_token=request.get("approval_token"))
    except Exception:
        status, data, error = "failed", {}, "action execution failed"
    return _reply(request_id, status, data, error, max(0, int((time.monotonic() - start) * 1000)))


def main() -> int:
    raw = sys.stdin.buffer.read(MAX_REQUEST_BYTES + 1)
    if len(raw) > MAX_REQUEST_BYTES:
        result = _reply("unknown", "invalid_request", error="request exceeds the size limit")
    else:
        try:
            request = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            result = _reply("unknown", "invalid_request", error="request must be UTF-8 JSON")
        else:
            result = handle_request(request)
    sys.stdout.write(json.dumps(result, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

