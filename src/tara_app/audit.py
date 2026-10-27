"""Small JSONL audit sink with conservative recursive redaction."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Mapping
from uuid import uuid4


_REDACTED = "[REDACTED]"
_SENSITIVE_KEY_PARTS = ("password", "secret", "token", "api_key", "authorization", "credential", "prompt", "messages", "content")
_LOCK = Lock()


def _redact(value: Any, key: str = "") -> Any:
    normalized_key = key.lower().replace("-", "_")
    if any(part in normalized_key for part in _SENSITIVE_KEY_PARTS):
        return _REDACTED
    if isinstance(value, Mapping):
        return {str(k): _redact(v, str(k)) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_redact(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return f"<{type(value).__name__}>"


class AuditLogError(RuntimeError):
    """Raised when an audit record cannot be persisted."""


class JsonlAuditLog:
    """Append one structured event per line; failures are surfaced to the caller."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def record(self, event_type: str, fields: Mapping[str, Any] | None = None) -> dict[str, Any]:
        if not isinstance(event_type, str) or not event_type.strip():
            raise ValueError("event_type must be a non-empty string")
        record = {
            "event_id": str(uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "fields": _redact(fields or {}),
        }
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            encoded = json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n"
            with _LOCK:
                with self.path.open("a", encoding="utf-8", newline="") as handle:
                    handle.write(encoded)
                    handle.flush()
                    os.fsync(handle.fileno())
        except (OSError, TypeError, ValueError):
            raise AuditLogError("audit event could not be persisted") from None
        return record
