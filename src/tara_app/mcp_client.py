"""Allowlisted MCP tool gateway for TARA-App.

Safety rules enforced here:

- Only servers present in an enabled ``McpRegistryConfig`` may be contacted.
- ``list_tools`` is read-only metadata.
- ``call_tool`` always requires a non-empty ``approval_token`` (app-issued).
- Live stdio transport requires the optional ``mcp`` package.
- Session factories are injectable so tests never need a real MCP process.

This module does not parse model text into commands and does not spawn
servers that are not already listed in config.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Protocol

from tara_app.mcp_registry import (
    McpConfigError,
    McpRegistryConfig,
    McpServerSpec,
    mcp_package_available,
    require_mcp_ready,
)

_MAX_TOOL_NAME = 128
_MAX_RESULT_CHARS = 200_000
_MAX_TOOLS_RETURNED = 128


class McpClientError(RuntimeError):
    """Raised when an MCP tool operation fails or is refused."""


@dataclass(frozen=True)
class McpToolInfo:
    server: str
    name: str
    description: str
    input_schema: dict[str, Any]


class McpSession(Protocol):
    """Minimal session surface used by the gateway."""

    def list_tools(self) -> list[McpToolInfo]:
        ...

    def call_tool(self, name: str, arguments: Mapping[str, Any]) -> str:
        ...

    def close(self) -> None:
        ...


SessionFactory = Callable[[McpServerSpec], McpSession]


class McpToolGateway:
    """Dispatch list/call operations to allowlisted MCP servers only."""

    def __init__(
        self,
        config: McpRegistryConfig,
        *,
        session_factory: SessionFactory | None = None,
    ) -> None:
        self._config = config
        self._using_default_factory = session_factory is None
        self._session_factory = session_factory or default_stdio_session_factory()

    @property
    def config(self) -> McpRegistryConfig:
        return self._config

    def list_tools(self, server_name: str | None = None) -> list[McpToolInfo]:
        """List tools from one enabled server, or all enabled servers."""
        self._ensure_ready()
        if not self._config.enable:
            raise McpClientError("MCP is disabled")

        targets = self._select_servers(server_name)
        tools: list[McpToolInfo] = []
        for spec in targets:
            session = self._session_factory(spec)
            try:
                listed = session.list_tools()
            finally:
                session.close()
            for tool in listed:
                if not isinstance(tool, McpToolInfo):
                    raise McpClientError("session returned invalid tool info")
                if tool.server != spec.name:
                    raise McpClientError("tool server name mismatch")
                tools.append(tool)
                if len(tools) >= _MAX_TOOLS_RETURNED:
                    return tools
        return tools

    def call_tool(
        self,
        server_name: str,
        tool_name: str,
        arguments: Mapping[str, Any] | None,
        *,
        approval_token: str,
    ) -> str:
        """Call one tool on an allowlisted server.

        ``approval_token`` must be a non-empty app-issued token. Model text is
        never treated as approval.
        """
        self._ensure_ready()
        if not self._config.enable:
            raise McpClientError("MCP is disabled")
        if not isinstance(approval_token, str) or not approval_token.strip():
            raise McpClientError("approval_token is required for MCP tool calls")
        if not isinstance(tool_name, str) or not tool_name.strip() or len(tool_name) > _MAX_TOOL_NAME:
            raise McpClientError("tool_name is invalid")
        if arguments is None:
            arguments = {}
        if not isinstance(arguments, Mapping):
            raise McpClientError("arguments must be an object")

        specs = self._select_servers(server_name)
        if len(specs) != 1:
            raise McpClientError("server is not enabled")
        spec = specs[0]

        session = self._session_factory(spec)
        try:
            result = session.call_tool(tool_name.strip(), dict(arguments))
        finally:
            session.close()

        if not isinstance(result, str):
            raise McpClientError("tool result must be text")
        if len(result) > _MAX_RESULT_CHARS:
            return result[:_MAX_RESULT_CHARS] + "\n…[truncated]"
        return result

    def _ensure_ready(self) -> None:
        # Injected factories (tests/fakes) do not need the optional mcp package.
        if self._using_default_factory:
            try:
                require_mcp_ready(self._config)
            except McpConfigError as exc:
                raise McpClientError(str(exc)) from exc

    def _select_servers(self, server_name: str | None) -> list[McpServerSpec]:
        enabled = list(self._config.enabled_servers)
        if server_name is None:
            return enabled
        if not isinstance(server_name, str) or not server_name.strip():
            raise McpClientError("server_name is invalid")
        wanted = server_name.strip()
        matches = [spec for spec in enabled if spec.name == wanted]
        if not matches:
            raise McpClientError(f"MCP server not enabled: {wanted}")
        return matches


def default_stdio_session_factory() -> SessionFactory:
    """Build sessions that speak real MCP over stdio when the package exists."""

    def factory(spec: McpServerSpec) -> McpSession:
        if not mcp_package_available():
            raise McpClientError(
                "optional mcp package is not installed; run: python -m pip install -e '.[mcp]'"
            )
        return _StdioMcpSession(spec)

    return factory


class _StdioMcpSession:
    """One-shot stdio MCP session using the official SDK when available."""

    def __init__(self, spec: McpServerSpec) -> None:
        self._spec = spec
        self._closed = False

    def list_tools(self) -> list[McpToolInfo]:
        return asyncio.run(self._list_tools_async())

    def call_tool(self, name: str, arguments: Mapping[str, Any]) -> str:
        return asyncio.run(self._call_tool_async(name, arguments))

    def close(self) -> None:
        self._closed = True

    async def _list_tools_async(self) -> list[McpToolInfo]:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        params = StdioServerParameters(
            command=self._spec.command[0],
            args=list(self._spec.command[1:]),
            cwd=self._spec.working_directory,
        )
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await asyncio.wait_for(session.initialize(), timeout=self._spec.timeout_seconds)
                result = await asyncio.wait_for(
                    session.list_tools(), timeout=self._spec.timeout_seconds
                )
                tools: list[McpToolInfo] = []
                for tool in getattr(result, "tools", []) or []:
                    schema = getattr(tool, "inputSchema", None) or getattr(tool, "input_schema", None) or {}
                    if not isinstance(schema, dict):
                        schema = {}
                    tools.append(
                        McpToolInfo(
                            server=self._spec.name,
                            name=str(getattr(tool, "name", "") or ""),
                            description=str(getattr(tool, "description", "") or ""),
                            input_schema=schema,
                        )
                    )
                return tools

    async def _call_tool_async(self, name: str, arguments: Mapping[str, Any]) -> str:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        params = StdioServerParameters(
            command=self._spec.command[0],
            args=list(self._spec.command[1:]),
            cwd=self._spec.working_directory,
        )
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await asyncio.wait_for(session.initialize(), timeout=self._spec.timeout_seconds)
                result = await asyncio.wait_for(
                    session.call_tool(name, arguments=dict(arguments)),
                    timeout=self._spec.timeout_seconds,
                )
                parts: list[str] = []
                for block in getattr(result, "content", []) or []:
                    text = getattr(block, "text", None)
                    if isinstance(text, str):
                        parts.append(text)
                    else:
                        parts.append(str(block))
                return "\n".join(parts) if parts else ""


__all__ = [
    "McpClientError",
    "McpSession",
    "McpToolGateway",
    "McpToolInfo",
    "SessionFactory",
    "default_stdio_session_factory",
]
