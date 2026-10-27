"""JSON-over-stdio entry point for TARA-App's local router."""
from __future__ import annotations

import json
import sys
from collections.abc import Mapping
from typing import Any

from tara_app.builtin_router import BuiltinRouter

MAX_REQUEST_BYTES = 1_000_000


def _payload(decision) -> dict[str, Any]:
    return {
        "schema_version": decision.schema_version,
        "request_id": decision.request_id,
        "status": decision.status,
        "module": decision.module,
        "action": decision.action,
        "reason_code": decision.reason_code,
        "reason": decision.reason,
        "intended_module": decision.intended_module,
        "intended_action": decision.intended_action,
        "requires_approval": decision.requires_approval,
        "policy_tags": list(decision.policy_tags),
    }


def main() -> int:
    raw = sys.stdin.buffer.read(MAX_REQUEST_BYTES + 1)
    if len(raw) > MAX_REQUEST_BYTES:
        result = {
            "schema_version": "1.0", "request_id": "unknown", "status": "invalid_request",
            "module": None, "action": None, "reason_code": "request_too_large",
            "reason": "Routing request exceeds the size limit.",
        }
    else:
        try:
            request = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            request = None
        if not isinstance(request, Mapping):
            result = {
                "schema_version": "1.0", "request_id": "unknown", "status": "invalid_request",
                "module": None, "action": None, "reason_code": "invalid_request",
                "reason": "Routing request must be a JSON object.",
            }
        else:
            result = _payload(BuiltinRouter().route(request))
    sys.stdout.write(json.dumps(result, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
