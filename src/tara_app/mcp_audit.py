"""Redacted, bounded JSONL audit trail for MCP approval lifecycle events."""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from threading import RLock
from typing import Any, Mapping


class McpAuditLog:
    """Append-only local audit log; never stores approval tokens or tool arguments."""

    def __init__(self, path: str | Path | None = None, *, max_bytes: int = 1_048_576) -> None:
        self.path = Path(path) if path is not None else Path.home() / ".tara" / "audit" / "mcp.jsonl"
        self.max_bytes = max(4096, int(max_bytes))
        self._lock = RLock()

    def record(
        self,
        event: str,
        *,
        server: str = "",
        tool: str = "",
        session_digest: str = "",
        arguments_digest: str = "",
        reason: str = "",
    ) -> None:
        """Append one allowlisted event with bounded, redacted metadata."""
        allowed_events = {"approval_issued", "tool_call_succeeded", "tool_call_failed", "approval_rejected"}
        if event not in allowed_events:
            raise ValueError("unsupported MCP audit event")
        entry = {
            "timestamp": round(time.time(), 3),
            "event": event,
            "server": str(server)[:64],
            "tool": str(tool)[:128],
            "session_digest": str(session_digest)[:64],
            "arguments_digest": str(arguments_digest)[:64],
            "reason": str(reason)[:80],
        }
        payload = (json.dumps(entry, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n").encode("utf-8")
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            if self.path.exists() and self.path.stat().st_size + len(payload) > self.max_bytes:
                backup = self.path.with_suffix(self.path.suffix + ".1")
                try:
                    backup.unlink(missing_ok=True)
                    self.path.replace(backup)
                except OSError:
                    # Fail closed for this audit write rather than truncating an active log.
                    raise
            flags = os.O_APPEND | os.O_CREAT | os.O_WRONLY
            fd = os.open(self.path, flags, 0o600)
            try:
                os.write(fd, payload)
            finally:
                os.close(fd)


__all__ = ["McpAuditLog"]
