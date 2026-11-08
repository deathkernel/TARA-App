"""MCP helpers mixed into the TARA Orchestrator."""
from __future__ import annotations

import hashlib
import json
import math
import secrets
import time
from collections import OrderedDict, deque
from datetime import datetime, timezone
from threading import RLock
from typing import Any, Mapping

from tara_app.mcp_client import _APPROVAL_GRANT_SEAL, _McpApprovalGrant
from tara_app.mcp_registry import describe_registry, mcp_package_available


class McpOrchestratorMixin:
    """Provides MCP status, approval tokens, list_tools, and call_tool."""

    mcp_gateway: Any
    _mcp_approval_tokens: OrderedDict[str, tuple[float, str, str, str, str]]
    _mcp_token_lock: RLock
    _mcp_audit_events: deque[dict[str, str]]
    _mcp_audit_lock: RLock

    def _init_mcp_state(self, mcp_gateway: Any = None) -> None:
        self.mcp_gateway = mcp_gateway
        self._mcp_approval_tokens = OrderedDict()
        self._mcp_token_lock = RLock()
        self._mcp_audit_events = deque(maxlen=200)
        self._mcp_audit_lock = RLock()

    def _record_mcp_audit_event(
        self, event: str, outcome: str, *, server: str = "", tool: str = "",
        session_id: str = "",
    ) -> None:
        """Record bounded metadata only; never store arguments, tokens, or raw session IDs."""
        session_fingerprint = hashlib.sha256(session_id.encode("utf-8")).hexdigest()[:12] if session_id else ""
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": event,
            "outcome": outcome,
            "server": server[:64],
            "tool": tool[:128],
            "session": session_fingerprint,
        }
        with self._mcp_audit_lock:
            self._mcp_audit_events.append(entry)

    def mcp_audit_log(self, limit: int = 50) -> dict[str, Any]:
        """Return recent in-memory MCP audit metadata, newest first."""
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
            raise ValueError("limit must be an integer between 1 and 100")
        with self._mcp_audit_lock:
            events = list(self._mcp_audit_events)[-limit:]
        return {"status": "available", "retention": "current_process", "events": list(reversed(events))}

    def mcp_status(self) -> dict[str, Any]:
        if self.mcp_gateway is None:
            return {
                "enable": False,
                "status": "disabled",
                "package_available": mcp_package_available(),
                "enabled_server_count": 0,
                "servers": [],
            }
        summary = describe_registry(self.mcp_gateway.config)
        summary["status"] = "enabled" if self.mcp_gateway.config.enable else "disabled"
        if self.mcp_gateway.config.enable and not mcp_package_available():
            summary["status"] = "package_missing"
        return summary

    @staticmethod
    def _mcp_arguments_digest(arguments: Mapping[str, Any] | None) -> str:
        normalized = {} if arguments is None else dict(arguments) if isinstance(arguments, Mapping) else None
        if normalized is None or any(not isinstance(key, str) for key in normalized):
            raise ValueError("arguments must be a JSON object with string keys")
        try:
            payload = json.dumps(normalized, sort_keys=True, separators=(",", ":"),
                                 ensure_ascii=False, allow_nan=False)
        except (TypeError, ValueError) as exc:
            raise ValueError("arguments must contain only JSON values") from exc
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def issue_mcp_approval_token(
        self, server_name: str, tool_name: str, arguments: Mapping[str, Any] | None,
        *, session_id: str, ttl_seconds: float = 300.0,
    ) -> str:
        if self.mcp_gateway is None or not self.mcp_gateway.config.enable:
            raise ValueError("MCP is disabled")
        if not isinstance(server_name, str) or not server_name.strip() or len(server_name) > 64:
            raise ValueError("server_name is invalid")
        if not isinstance(tool_name, str) or not tool_name.strip() or len(tool_name) > 128:
            raise ValueError("tool_name is invalid")
        if not isinstance(session_id, str) or not session_id.strip() or len(session_id) > 128:
            raise ValueError("session_id is invalid")
        if isinstance(ttl_seconds, bool) or not isinstance(ttl_seconds, (int, float)) or not math.isfinite(float(ttl_seconds)) or not 30 <= float(ttl_seconds) <= 900:
            raise ValueError("ttl_seconds is invalid")
        server, tool = server_name.strip(), tool_name.strip()
        specs = [item for item in self.mcp_gateway.config.enabled_servers if item.name == server]
        if not specs:
            raise ValueError("MCP server is not enabled")
        if not specs[0].read_only or tool not in specs[0].read_only_tools:
            raise ValueError("MCP approval is restricted to explicitly allowlisted read-only tools (read-only allowlist)")
        digest = self._mcp_arguments_digest(arguments)
        token = secrets.token_urlsafe(24)
        expires = time.time() + float(ttl_seconds)
        with self._mcp_token_lock:
            self._mcp_approval_tokens[token] = (expires, session_id, server, tool, digest)
            while len(self._mcp_approval_tokens) > 64:
                self._mcp_approval_tokens.popitem(last=False)
        self._record_mcp_audit_event("approval_issued", "approved_for_review", server=server, tool=tool, session_id=session_id)
        return token

    def list_mcp_tools(self, server_name: str | None = None) -> list[dict[str, Any]]:
        if self.mcp_gateway is None or not self.mcp_gateway.config.enable:
            raise ValueError("MCP is disabled")
        tools = self.mcp_gateway.list_tools(server_name)
        return [
            {
                "server": tool.server,
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.input_schema,
            }
            for tool in tools
        ]

    def call_mcp_tool(
        self, server_name: str, tool_name: str, arguments: Mapping[str, Any] | None,
        *, approval_token: str, session_id: str,
    ) -> str:
        if self.mcp_gateway is None or not self.mcp_gateway.config.enable:
            raise ValueError("MCP is disabled")
        if not isinstance(approval_token, str) or not approval_token.strip():
            raise ValueError("approval_token is required")
        if not isinstance(session_id, str) or not session_id.strip() or len(session_id) > 128:
            raise ValueError("session_id is invalid")
        if not isinstance(server_name, str) or not isinstance(tool_name, str):
            raise ValueError("MCP tool target is invalid")
        server, tool = server_name.strip(), tool_name.strip()
        digest = self._mcp_arguments_digest(arguments)
        token, now = approval_token.strip(), time.time()
        with self._mcp_token_lock:
            entry = self._mcp_approval_tokens.get(token)
            expired = [key for key, value in self._mcp_approval_tokens.items() if value[0] <= now]
            for key in expired:
                self._mcp_approval_tokens.pop(key, None)
            if entry is None or entry[0] <= now:
                self._mcp_approval_tokens.pop(token, None)
                self._record_mcp_audit_event("tool_call", "denied_invalid_or_expired_approval", server=server, tool=tool, session_id=session_id)
                raise ValueError("approval_token is invalid or expired")
            if entry[1:] != (session_id, server, tool, digest):
                self._record_mcp_audit_event("tool_call", "denied_approval_mismatch", server=server, tool=tool, session_id=session_id)
                raise ValueError("approval_token does not match this session and tool call")
            self._mcp_approval_tokens.pop(token, None)
        grant = _McpApprovalGrant(_APPROVAL_GRANT_SEAL)
        try:
            result = self.mcp_gateway.call_tool(server, tool, arguments, approval_grant=grant)
        except Exception:
            self._record_mcp_audit_event("tool_call", "failed", server=server, tool=tool, session_id=session_id)
            raise
        self._record_mcp_audit_event("tool_call", "succeeded", server=server, tool=tool, session_id=session_id)
        return result
