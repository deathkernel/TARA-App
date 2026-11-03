"""Tests for the MCP allowlist registry."""
from __future__ import annotations

import unittest

from tara_app.mcp_registry import (
    McpConfigError,
    default_mcp_config,
    describe_registry,
    parse_mcp_config,
    require_mcp_ready,
)


class McpRegistryTests(unittest.TestCase):
    def test_default_is_disabled(self) -> None:
        config = default_mcp_config()
        self.assertFalse(config.enable)
        self.assertEqual(config.enabled_servers, ())

    def test_parse_enabled_server(self) -> None:
        config = parse_mcp_config(
            {
                "enable": True,
                "servers": [
                    {
                        "name": "time",
                        "command": ["uvx", "mcp-server-time"],
                        "enabled": True,
                        "read_only": True,
                        "timeout_seconds": 30,
                    }
                ],
            }
        )
        self.assertTrue(config.enable)
        self.assertEqual(len(config.enabled_servers), 1)
        self.assertEqual(config.enabled_servers[0].name, "time")

    def test_rejects_shell_string_command(self) -> None:
        with self.assertRaises(McpConfigError):
            parse_mcp_config(
                {
                    "enable": True,
                    "servers": [{"name": "x", "command": "echo hi"}],
                }
            )

    def test_rejects_duplicate_names(self) -> None:
        with self.assertRaises(McpConfigError):
            parse_mcp_config(
                {
                    "enable": True,
                    "servers": [
                        {"name": "time", "command": ["a"]},
                        {"name": "time", "command": ["b"]},
                    ],
                }
            )

    def test_describe_registry_is_json_safe(self) -> None:
        config = parse_mcp_config(
            {
                "enable": False,
                "servers": [{"name": "time", "command": ["uvx", "mcp-server-time"]}],
            }
        )
        summary = describe_registry(config)
        self.assertIn("enable", summary)
        self.assertIn("servers", summary)

    def test_require_mcp_ready_noop_when_disabled(self) -> None:
        require_mcp_ready(default_mcp_config())


if __name__ == "__main__":
    unittest.main()
