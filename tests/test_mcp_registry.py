"""Tests for the opt-in MCP allowlist registry."""
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
        self.assertEqual(config.servers, ())
        self.assertEqual(config.enabled_servers, ())

    def test_parse_disabled_with_servers_still_inactive(self) -> None:
        config = parse_mcp_config(
            {
                "enable": False,
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
        self.assertFalse(config.enable)
        self.assertEqual(len(config.servers), 1)
        self.assertEqual(config.enabled_servers, ())

    def test_parse_enabled_server(self) -> None:
        config = parse_mcp_config(
            {
                "enable": True,
                "servers": [
                    {
                        "name": "time",
                        "command": ["uvx", "mcp-server-time"],
                        "timeout_seconds": 15,
                        "read_only": True,
                    }
                ],
            }
        )
        self.assertTrue(config.enable)
        self.assertEqual(len(config.enabled_servers), 1)
        server = config.enabled_servers[0]
        self.assertEqual(server.name, "time")
        self.assertEqual(server.command, ("uvx", "mcp-server-time"))
        self.assertEqual(server.timeout_seconds, 15.0)
        self.assertTrue(server.read_only)

    def test_rejects_non_boolean_flags(self) -> None:
        invalid_values = (
            {"enable": "false", "servers": []},
            {"enable": True, "servers": [{"name": "time", "command": ["uvx"], "enabled": "false"}]},
            {"enable": True, "servers": [{"name": "time", "command": ["uvx"], "read_only": 0}]},
        )
        for raw in invalid_values:
            with self.subTest(raw=raw), self.assertRaises(McpConfigError):
                parse_mcp_config(raw)

    def test_rejects_shell_string_command(self) -> None:
        with self.assertRaises(McpConfigError):
            parse_mcp_config(
                {
                    "enable": True,
                    "servers": [{"name": "bad", "command": "uvx mcp-server-time"}],
                }
            )

    def test_rejects_empty_command(self) -> None:
        with self.assertRaises(McpConfigError):
            parse_mcp_config(
                {"enable": True, "servers": [{"name": "bad", "command": []}]}
            )

    def test_rejects_duplicate_names(self) -> None:
        with self.assertRaises(McpConfigError):
            parse_mcp_config(
                {
                    "enable": True,
                    "servers": [
                        {"name": "time", "command": ["uvx", "mcp-server-time"]},
                        {"name": "time", "command": ["uvx", "mcp-server-time"]},
                    ],
                }
            )

    def test_rejects_oversized_timeout(self) -> None:
        with self.assertRaises(McpConfigError):
            parse_mcp_config(
                {
                    "enable": True,
                    "servers": [
                        {
                            "name": "time",
                            "command": ["uvx", "mcp-server-time"],
                            "timeout_seconds": 9999,
                        }
                    ],
                }
            )

    def test_describe_registry_is_json_safe(self) -> None:
        config = parse_mcp_config(
            {
                "enable": True,
                "servers": [
                    {
                        "name": "time",
                        "command": ["uvx", "mcp-server-time"],
                        "enabled": True,
                    }
                ],
            }
        )
        summary = describe_registry(config)
        self.assertTrue(summary["enable"])
        self.assertEqual(summary["enabled_server_count"], 1)
        self.assertEqual(summary["servers"][0]["name"], "time")
        self.assertEqual(summary["servers"][0]["command0"], "uvx")
        self.assertTrue(summary["servers"][0]["known_reference"])

    def test_require_mcp_ready_noop_when_disabled(self) -> None:
        require_mcp_ready(default_mcp_config())

    def test_require_mcp_ready_errors_when_enabled_without_package(self) -> None:
        config = parse_mcp_config(
            {
                "enable": True,
                "servers": [
                    {
                        "name": "time",
                        "command": ["uvx", "mcp-server-time"],
                        "enabled": True,
                    }
                ],
            }
        )
        # If the optional package is installed in the environment, skip the negative case.
        from tara_app.mcp_registry import mcp_package_available

        if mcp_package_available():
            require_mcp_ready(config)
            return
        with self.assertRaises(McpConfigError):
            require_mcp_ready(config)


if __name__ == "__main__":
    unittest.main()
