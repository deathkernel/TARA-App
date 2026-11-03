"""MCP helpers mixed into the TARA Orchestrator."""
from __future__ import annotations

import secrets
import time
from collections import OrderedDict
from threading import RLock
from typing import Any, Mapping

from tara_app.mcp_registry import describe_registry, mcp_package_available


class McpOrchestratorMixin:
    """Provides MCP status, approval tokens, list_tools, and call_tool."""

    mcp_gateway: Any
    _mcp_approval_tokens: OrderedDict[str, float]
    _mcp_token_lock: RLock

    def _init_mcp_state(self, mcp_gateway: Any = None) -> None:
        self.mcp_gateway = mcp_gateway
        self._mcp_approval_tokens = OrderedDict()
        self._mcp_token_lock = RLock()

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

    def issue_mcp_approval_token(self, *, ttl_seconds: float = 300.0) -> str:
        if self.mcp_gateway is None or not self.mcp_gateway.config.enable:
            raise ValueError("MCP is disabled")
        if not isinstance(ttl_seconds, (int, float)) or not 30 <= float(ttl_seconds) <= 900:
            raise ValueError("ttl_seconds is invalid")
        token = secrets.token_urlsafe(24)
        expires = time.time() + float(ttl_seconds)
        with self._mcp_token_lock:
            self._mcp_approval_tokens[token] = expires
            while len(self._mcp_approval_tokens) > 64:
                self._mcp_approval_tokens.popitem(last=False)
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
        self,
        server_name: str,
        tool_name: str,
        arguments: Mapping[str, Any] | None,
        *,
        approval_token: str,
    ) -> str:
        if self.mcp_gateway is None or not self.mcp_gateway.config.enable:
            raise ValueError("MCP is disabled")
        if not isinstance(approval_token, str) or not approval_token.strip():
            raise ValueError("approval_token is required")
        token = approval_token.strip()
        now = time.time()
        with self._mcp_token_lock:
            expires = self._mcp_approval_tokens.pop(token, None)
            expired = [key for key, value in self._mcp_approval_tokens.items() if value <= now]
            for key in expired:
                self._mcp_approval_tokens.pop(key, None)
        if expires is None or expires <= now:
            raise ValueError("approval_token is invalid or expired")
        return self.mcp_gateway.call_tool(server_name, tool_name, arguments, approval_token=token)
