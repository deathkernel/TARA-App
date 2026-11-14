"""MCP helpers mixed into the SITA Orchestrator."""
from __future__ import annotations

import hashlib
import json
import math
import secrets
import time
from collections import OrderedDict
from pathlib import Path
from threading import RLock
from typing import Any, Mapping

from tara_app.audit import AuditLogError, JsonlAuditLog
from tara_app.mcp_client import _APPROVAL_GRANT_SEAL, _McpApprovalGrant
from tara_app.mcp_registry import describe_registry, mcp_package_available


class McpOrchestratorMixin:
    """Provides MCP status, approval tokens, list_tools, and call_tool."""

    mcp_gateway: Any
    _mcp_approval_tokens: OrderedDict[str, tuple[float, str, str, str, str]]
    _mcp_token_lock: RLock
    _mcp_audit: JsonlAuditLog
    _mcp_audit_degraded: bool

    def _init_mcp_state(
        self, mcp_gateway: Any = None, *, audit_log: JsonlAuditLog | None = None,
    ) -> None:
        self.mcp_gateway = mcp_gateway
        self._mcp_approval_tokens = OrderedDict()
        self._mcp_token_lock = RLock()
        self._mcp_audit = audit_log if audit_log is not None else JsonlAuditLog(
            Path.home() / ".tara" / "audit" / "mcp.jsonl",
            max_bytes=1_048_576,
            max_record_bytes=4096,
        )
        self._mcp_audit_degraded = False

    @staticmethod
    def _mcp_session_digest(session_id: str) -> str:
        return hashlib.sha256(session_id.encode("utf-8")).hexdigest()

    def _audit_mcp(
        self, event: str, *, server: str = "", tool: str = "", session_id: str = "",
        arguments_digest: str = "", reason: str = "", expires_at: float | None = None,
    ) -> None:
        try:
            self._mcp_audit.record(event, {
                "server": server,
                "tool": tool,
                "session_digest": self._mcp_session_digest(session_id) if session_id else "",
                "arguments_digest": arguments_digest,
                "expires_at": expires_at,
                "reason": reason,
            })
        except AuditLogError:
            self._mcp_audit_degraded = True
            raise

    def mcp_status(self) -> dict[str, Any]:
        if self.mcp_gateway is None:
            return {
                "enable": False,
                "status": "disabled",
                "package_available": mcp_package_available(),
                "enabled_server_count": 0,
                "servers": [],
                "audit_status": "degraded" if self._mcp_audit_degraded else "available",
            }
        summary = describe_registry(self.mcp_gateway.config)
        summary["status"] = "enabled" if self.mcp_gateway.config.enable else "disabled"
        if self.mcp_gateway.config.enable and not mcp_package_available():
            summary["status"] = "package_missing"
        summary["audit_status"] = "degraded" if self._mcp_audit_degraded else "available"
        return summary

    @staticmethod
    def _mcp_arguments_snapshot(arguments: Mapping[str, Any] | None) -> tuple[dict[str, Any], str]:
        normalized = {} if arguments is None else dict(arguments) if isinstance(arguments, Mapping) else None
        if normalized is None or any(not isinstance(key, str) for key in normalized):
            raise ValueError("arguments must be a JSON object with string keys")
        try:
            payload = json.dumps(normalized, sort_keys=True, separators=(",", ":"),
                                 ensure_ascii=False, allow_nan=False)
        except (TypeError, ValueError) as exc:
            raise ValueError("arguments must contain only JSON values") from exc
        if len(payload.encode("utf-8")) > 65_536:
            raise ValueError("arguments exceed the 64 KiB approval limit")
        snapshot = json.loads(payload)
        return snapshot, hashlib.sha256(payload.encode("utf-8")).hexdigest()

    @staticmethod
    def _mcp_arguments_digest(arguments: Mapping[str, Any] | None) -> str:
        return McpOrchestratorMixin._mcp_arguments_snapshot(arguments)[1]

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
        try:
            self._audit_mcp(
                "approval_issued", server=server, tool=tool,
                session_id=session_id, arguments_digest=digest, expires_at=expires,
            )
        except AuditLogError:
            with self._mcp_token_lock:
                self._mcp_approval_tokens.pop(token, None)
            raise
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
        safe_arguments, digest = self._mcp_arguments_snapshot(arguments)
        token, now = approval_token.strip(), time.time()
        rejection_reason = ""
        with self._mcp_token_lock:
            entry = self._mcp_approval_tokens.get(token)
            expired = [key for key, value in self._mcp_approval_tokens.items() if value[0] <= now]
            for key in expired:
                self._mcp_approval_tokens.pop(key, None)
            if entry is None or entry[0] <= now:
                self._mcp_approval_tokens.pop(token, None)
                rejection_reason = "invalid_or_expired"
            elif entry[1:] != (session_id, server, tool, digest):
                rejection_reason = "call_binding_mismatch"
            else:
                self._mcp_approval_tokens.pop(token, None)

        if rejection_reason:
            self._audit_mcp(
                "approval_rejected", server=server, tool=tool, session_id=session_id,
                arguments_digest=digest, reason=rejection_reason,
            )
            if rejection_reason == "invalid_or_expired":
                raise ValueError("approval_token is invalid or expired")
            raise ValueError("approval_token does not match this session and tool call")

        # Persist the dispatch intent before crossing the external tool boundary.
        # If this write fails, the one-shot approval stays consumed and no tool runs.
        self._audit_mcp(
            "tool_call_started", server=server, tool=tool,
            session_id=session_id, arguments_digest=digest,
        )
        grant = _McpApprovalGrant(_APPROVAL_GRANT_SEAL)
        try:
            result = self.mcp_gateway.call_tool(server, tool, safe_arguments, approval_grant=grant)
        except Exception:
            try:
                self._audit_mcp(
                    "tool_call_failed", server=server, tool=tool,
                    session_id=session_id, arguments_digest=digest, reason="gateway_error",
                )
            except AuditLogError:
                self._mcp_audit_degraded = True
            raise
        try:
            self._audit_mcp(
                "tool_call_succeeded", server=server, tool=tool,
                session_id=session_id, arguments_digest=digest,
            )
        except AuditLogError:
            # The pre-dispatch record is durable. Do not invite a duplicate
            # external action by turning a completed call into a retry signal.
            self._mcp_audit_degraded = True
        return result
