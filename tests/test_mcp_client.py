"""Tests for the MCP tool gateway (no live MCP process)."""
from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Mapping

from tara_app.mcp_client import McpClientError, McpToolGateway, McpToolInfo, _MAX_TOOL_PAGES, _collect_tool_pages, _APPROVAL_GRANT_SEAL, _McpApprovalGrant, _extract_tool_page, _tool_result_text
from tara_app.mcp_registry import McpConfigError, McpServerSpec, parse_mcp_config
from tara_app.mcp_toml import load_mcp_config_from_toml


class _FakeSession:
    def __init__(self, spec: McpServerSpec) -> None:
        self.spec = spec
        self.closed = False
        self.calls: list[tuple[str, Mapping[str, Any]]] = []

    def list_tools(self) -> list[McpToolInfo]:
        return [
            McpToolInfo(
                server=self.spec.name,
                name="ping",
                description="ping tool",
                input_schema={"type": "object"},
            )
        ]

    def call_tool(self, name: str, arguments: Mapping[str, Any]) -> str:
        self.calls.append((name, dict(arguments)))
        return f"ok:{name}"

    def close(self) -> None:
        self.closed = True


def _enabled_config() -> Any:
    return parse_mcp_config(
        {
            "enable": True,
            "servers": [
                {
                    "name": "time",
                    "command": ["uvx", "mcp-server-time"],
                    "enabled": True,
                    "read_only": True,
                    "read_only_tools": ["ping"],
                }
            ],
        }
    )


class McpClientTests(unittest.TestCase):
    def test_tool_page_exposes_pagination_cursor(self) -> None:
        result = SimpleNamespace(tools=[SimpleNamespace(name="ping", description="ping", inputSchema={"type": "object"})], nextCursor="next-page")
        tools, cursor = _extract_tool_page(result, "time")
        self.assertEqual([tool.name for tool in tools], ["ping"])
        self.assertEqual(cursor, "next-page")

    def test_tool_page_collection_stops_at_the_page_limit(self) -> None:
        calls = []

        async def empty_page(cursor):
            calls.append(cursor)
            return SimpleNamespace(tools=[], nextCursor=f"cursor-{len(calls)}")

        with self.assertRaisesRegex(McpClientError, "pagination page limit"):
            asyncio.run(_collect_tool_pages(
                empty_page, timeout_seconds=1, server_name="time"
            ))
        self.assertEqual(len(calls), _MAX_TOOL_PAGES)

    def test_tool_pages_are_collected_until_the_end_cursor(self) -> None:
        calls = []

        async def list_page(cursor):
            calls.append(cursor)
            if cursor is None:
                return SimpleNamespace(
                    tools=[SimpleNamespace(name="first", description="", inputSchema={})],
                    nextCursor="next",
                )
            return SimpleNamespace(
                tools=[SimpleNamespace(name="second", description="", inputSchema={})],
                nextCursor=None,
            )

        tools = asyncio.run(_collect_tool_pages(
            list_page, timeout_seconds=1, server_name="time"
        ))
        self.assertEqual([tool.name for tool in tools], ["first", "second"])
        self.assertEqual(calls, [None, "next"])

    def test_tool_page_bounds_descriptions_and_rejects_oversized_schemas(self) -> None:
        description = "d" * 3000
        result = SimpleNamespace(
            tools=[SimpleNamespace(name="ping", description=description, inputSchema={"type": "object"})],
            nextCursor=None,
        )
        tools, _ = _extract_tool_page(result, "time")
        self.assertEqual(len(tools[0].description), 2000)

        oversized = SimpleNamespace(
            tools=[SimpleNamespace(
                name="ping", description="", inputSchema={"value": "x" * 40_000}
            )],
            nextCursor=None,
        )
        with self.assertRaisesRegex(McpClientError, "32 KiB"):
            _extract_tool_page(oversized, "time")

    def test_tool_result_is_bounded(self) -> None:
        from tara_app.mcp_client import _MAX_RESULT_CHARS
        config = _enabled_config()
        gateway = McpToolGateway(
            config,
            session_factory=lambda spec: type(
                "LargeResultSession",
                (),
                {
                    "call_tool": lambda self, name, arguments: "x" * (_MAX_RESULT_CHARS + 10),
                    "list_tools": lambda self: [],
                    "close": lambda self: None,
                },
            )(),
        )
        result = gateway.call_tool(
            "time", "ping", {}, approval_grant=_McpApprovalGrant(_APPROVAL_GRANT_SEAL)
        )
        self.assertEqual(len(result), _MAX_RESULT_CHARS + 13)
        self.assertTrue(result.endswith("[truncated]"))

    def test_tool_error_is_not_returned_as_success_text(self) -> None:
        result = SimpleNamespace(isError=True, content=[SimpleNamespace(text="denied")])
        with self.assertRaises(McpClientError):
            _tool_result_text(result)

    def test_list_tools_uses_factory(self) -> None:
        sessions: list[_FakeSession] = []

        def factory(spec: McpServerSpec) -> _FakeSession:
            session = _FakeSession(spec)
            sessions.append(session)
            return session

        gateway = McpToolGateway(_enabled_config(), session_factory=factory)
        tools = gateway.list_tools()
        self.assertEqual(len(tools), 1)
        self.assertEqual(tools[0].name, "ping")
        self.assertTrue(sessions[0].closed)

    def test_list_tools_cache_reuses_metadata_until_invalidated(self) -> None:
        sessions: list[_FakeSession] = []

        def factory(spec: McpServerSpec) -> _FakeSession:
            session = _FakeSession(spec)
            sessions.append(session)
            return session

        gateway = McpToolGateway(_enabled_config(), session_factory=factory)
        gateway.list_tools()
        gateway.list_tools()
        self.assertEqual(len(sessions), 1)
        gateway.invalidate_tool_cache("time")
        gateway.list_tools()
        self.assertEqual(len(sessions), 2)

    def test_list_tools_cache_can_be_disabled(self) -> None:
        sessions = []
        def factory(spec):
            session = _FakeSession(spec)
            sessions.append(session)
            return session
        gateway = McpToolGateway(
            _enabled_config(), session_factory=factory, tool_cache_ttl_seconds=0
        )
        gateway.list_tools()
        gateway.list_tools()
        self.assertEqual(len(sessions), 2)

    def test_list_tools_disabled(self) -> None:
        config = parse_mcp_config({"enable": False, "servers": []})
        gateway = McpToolGateway(config, session_factory=lambda spec: _FakeSession(spec))
        with self.assertRaises(McpClientError):
            gateway.list_tools()

    def test_call_tool_requires_approval(self) -> None:
        gateway = McpToolGateway(_enabled_config(), session_factory=lambda spec: _FakeSession(spec))
        with self.assertRaises(McpClientError):
            gateway.call_tool("time", "ping", {}, approval_grant="")

    def test_gateway_rejects_raw_approval_tokens(self) -> None:
        gateway = McpToolGateway(_enabled_config(), session_factory=lambda spec: _FakeSession(spec))
        with self.assertRaisesRegex(McpClientError, "validated app approval grant"):
            gateway.call_tool("time", "ping", {}, approval_grant="approve-1")

    def test_approval_grant_rejects_untrusted_constructor_seal(self) -> None:
        with self.assertRaisesRegex(ValueError, "only be created by the app"):
            _McpApprovalGrant(object())

    def test_read_only_server_blocks_unlisted_tools(self) -> None:
        gateway = McpToolGateway(_enabled_config(), session_factory=lambda spec: _FakeSession(spec))
        with self.assertRaisesRegex(McpClientError, "read-only allowlist"):
            gateway.call_tool("time", "delete_file", {}, approval_grant=_McpApprovalGrant(_APPROVAL_GRANT_SEAL))

    def test_call_tool_with_approval(self) -> None:
        session_box: list[_FakeSession] = []

        def factory(spec: McpServerSpec) -> _FakeSession:
            session = _FakeSession(spec)
            session_box.append(session)
            return session

        gateway = McpToolGateway(_enabled_config(), session_factory=factory)
        grant = _McpApprovalGrant(_APPROVAL_GRANT_SEAL)
        result = gateway.call_tool("time", "ping", {"x": 1}, approval_grant=grant)
        self.assertEqual(result, "ok:ping")
        self.assertEqual(session_box[0].calls[0][0], "ping")
        with self.assertRaisesRegex(McpClientError, "validated app approval grant"):
            gateway.call_tool("time", "ping", {"x": 1}, approval_grant=grant)

    def test_unknown_server_rejected(self) -> None:
        gateway = McpToolGateway(_enabled_config(), session_factory=lambda spec: _FakeSession(spec))
        with self.assertRaises(McpClientError):
            gateway.call_tool("nope", "ping", {}, approval_grant=_McpApprovalGrant(_APPROVAL_GRANT_SEAL))

    def test_load_toml_missing_file_defaults_off(self) -> None:
        config = load_mcp_config_from_toml(Path("/nonexistent/tara-app.toml"))
        self.assertFalse(config.enable)

    def test_load_toml_rejects_non_table_mcp_value(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "tara-app.toml"
            path.write_text("mcp = true\n", encoding="utf-8")
            with self.assertRaises(McpConfigError):
                load_mcp_config_from_toml(path)

    def test_load_toml_parses_mcp_section(self) -> None:
        content = """
[mcp]
enable = true

[[mcp.servers]]
name = "time"
command = ["uvx", "mcp-server-time"]
enabled = true
read_only = true
timeout_seconds = 12
read_only_tools = ["get_time"]
"""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "tara-app.toml"
            path.write_text(content, encoding="utf-8")
            config = load_mcp_config_from_toml(path)
        self.assertTrue(config.enable)
        self.assertEqual(len(config.enabled_servers), 1)
        self.assertEqual(config.enabled_servers[0].timeout_seconds, 12.0)


if __name__ == "__main__":
    unittest.main()
