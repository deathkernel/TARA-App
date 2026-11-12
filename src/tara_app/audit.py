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
    """Append structured JSONL events with optional bounded single-backup rotation."""

    def __init__(
        self,
        path: Path,
        *,
        max_bytes: int | None = None,
        max_record_bytes: int = 65_536,
    ) -> None:
        if max_bytes is not None and (
            isinstance(max_bytes, bool) or not isinstance(max_bytes, int) or max_bytes < 4096
        ):
            raise ValueError("max_bytes must be at least 4096")
        if (
            isinstance(max_record_bytes, bool)
            or not isinstance(max_record_bytes, int)
            or max_record_bytes < 256
        ):
            raise ValueError("max_record_bytes must be at least 256")
        self.path = Path(path)
        self.max_bytes = max_bytes
        self.max_record_bytes = max_record_bytes

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
            encoded = (json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
            if len(encoded) > self.max_record_bytes or (
                self.max_bytes is not None and len(encoded) > self.max_bytes
            ):
                raise AuditLogError("audit record exceeds the configured size limit")
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with _LOCK:
                if self.max_bytes is not None and self.path.exists():
                    if self.path.stat().st_size + len(encoded) > self.max_bytes:
                        backup = self.path.with_suffix(self.path.suffix + ".1")
                        backup.unlink(missing_ok=True)
                        self.path.replace(backup)
                flags = os.O_APPEND | os.O_CREAT | os.O_WRONLY
                descriptor = os.open(self.path, flags, 0o600)
                try:
                    remaining = memoryview(encoded)
                    while remaining:
                        written = os.write(descriptor, remaining)
                        if written <= 0:
                            raise OSError("audit write did not make progress")
                        remaining = remaining[written:]
                    os.fsync(descriptor)
                finally:
                    os.close(descriptor)
        except AuditLogError:
            raise
        except (OSError, TypeError, ValueError):
            raise AuditLogError("audit event could not be persisted") from None
        return record
