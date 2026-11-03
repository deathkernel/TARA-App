"""Tests for the MCP tool gateway (no live MCP process)."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from typing import Any, Mapping

from tara_app.mcp_client import McpClientError, McpToolGateway, McpToolInfo
from tara_app.mcp_registry import McpServerSpec, parse_mcp_config
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
                }
            ],
        }
    )


class McpClientTests(unittest.TestCase):
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

    def test_list_tools_disabled(self) -> None:
        config = parse_mcp_config({"enable": False, "servers": []})
        gateway = McpToolGateway(config, session_factory=lambda spec: _FakeSession(spec))
        with self.assertRaises(McpClientError):
            gateway.list_tools()

    def test_call_tool_requires_approval(self) -> None:
        gateway = McpToolGateway(_enabled_config(), session_factory=lambda spec: _FakeSession(spec))
        with self.assertRaises(McpClientError):
            gateway.call_tool("time", "ping", {}, approval_token="")

    def test_call_tool_with_approval(self) -> None:
        session_box: list[_FakeSession] = []

        def factory(spec: McpServerSpec) -> _FakeSession:
            session = _FakeSession(spec)
            session_box.append(session)
            return session

        gateway = McpToolGateway(_enabled_config(), session_factory=factory)
        result = gateway.call_tool("time", "ping", {"x": 1}, approval_token="approve-1")
        self.assertEqual(result, "ok:ping")
        self.assertEqual(session_box[0].calls[0][0], "ping")

    def test_unknown_server_rejected(self) -> None:
        gateway = McpToolGateway(_enabled_config(), session_factory=lambda spec: _FakeSession(spec))
        with self.assertRaises(McpClientError):
            gateway.call_tool("nope", "ping", {}, approval_token="approve-1")

    def test_load_toml_missing_file_defaults_off(self) -> None:
        config = load_mcp_config_from_toml(Path("/nonexistent/tara-app.toml"))
        self.assertFalse(config.enable)

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
