"""One-request JSON-over-stdio adapter for TARA."""
from __future__ import annotations
import json
import sys
import time
from .service import MODULE_ID, execute

MAX_REQUEST_BYTES = 1_000_000
_ALLOWED = {"schema_version", "request_id", "session_id", "module", "action", "inputs", "workspace_root", "timeout_seconds", "approval_token"}

def _reply(request_id: str, status: str, data: dict, error: str | None, duration_ms: int) -> None:
    result = {"schema_version": "1.0", "request_id": request_id, "status": status, "data": data, "error": error, "duration_ms": duration_ms}
    sys.stdout.write(json.dumps(result, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n")

def main() -> int:
    raw = sys.stdin.buffer.read(MAX_REQUEST_BYTES + 1)
    if len(raw) > MAX_REQUEST_BYTES:
        _reply("unknown", "invalid_request", {}, "request exceeds the size limit", 0)
        return 0
    try:
        request = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        _reply("unknown", "invalid_request", {}, "request must be UTF-8 JSON", 0)
        return 0
    if not isinstance(request, dict) or set(request) - _ALLOWED:
        _reply("unknown", "invalid_request", {}, "request shape is invalid", 0)
        return 0
    request_id = request.get("request_id")
    if not isinstance(request_id, str) or not request_id.strip() or len(request_id) > 128:
        _reply("unknown", "invalid_request", {}, "request_id is invalid", 0)
        return 0
    if request.get("schema_version") != "1.0" or request.get("module") != MODULE_ID:
        _reply(request_id, "invalid_request", {}, "module or schema version is invalid", 0)
        return 0
    action, inputs = request.get("action"), request.get("inputs", {})
    if not isinstance(action, str) or not isinstance(inputs, dict):
        _reply(request_id, "invalid_request", {}, "action or inputs are invalid", 0)
        return 0
    if action == "health":
        _reply(request_id, "success", {"healthy": True}, None, 0)
        return 0
    start = time.monotonic()
    try:
        status, data, error = execute(action, inputs, approval_token=request.get("approval_token"))
        if not isinstance(data, dict):
            raise ValueError("module returned invalid result data")
    except ValueError as exc:
        status, data, error = "invalid_request", {}, str(exc)[:500]
    except Exception:
        status, data, error = "failed", {}, "module operation failed"
    duration = max(0, int((time.monotonic() - start) * 1000))
    _reply(request_id, status, data, error, duration)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

