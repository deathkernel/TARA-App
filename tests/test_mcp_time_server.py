"""Tests for the built-in, read-only MCP time server."""
from __future__ import annotations

import contextlib
import io
import json
import sys
import unittest
from datetime import datetime, timedelta, timezone
from types import ModuleType
from unittest.mock import patch
from zoneinfo import ZoneInfoNotFoundError

from tara_app.mcp_servers.time_logic import current_time_payload
from tara_app.mcp_servers.time_server import main


class _FrozenDateTime(datetime):
    @classmethod
    def now(cls, tz=None):
        return cls(2026, 11, 6, 12, 30, tzinfo=timezone.utc)


class McpTimeLogicTests(unittest.TestCase):
    def test_payload_without_timezone_returns_utc_and_unix_time(self):
        with patch("tara_app.mcp_servers.time_logic.datetime", _FrozenDateTime):
            payload = current_time_payload()

        expected_timestamp = int(
            datetime(2026, 11, 6, 12, 30, tzinfo=timezone.utc).timestamp()
        )
        self.assertEqual(payload["utc_iso"], "2026-11-06T12:30:00Z")
        self.assertEqual(payload["unix_seconds"], str(expected_timestamp))
        self.assertNotIn("timezone", payload)
        self.assertNotIn("local_iso", payload)

    def test_payload_converts_to_requested_timezone(self):
        local_zone = timezone(timedelta(hours=5, minutes=30))
        with (
            patch("tara_app.mcp_servers.time_logic.datetime", _FrozenDateTime),
            patch("tara_app.mcp_servers.time_logic.ZoneInfo", return_value=local_zone) as zone_info,
        ):
            payload = current_time_payload(" Asia/Kolkata ")

        zone_info.assert_called_once_with("Asia/Kolkata")
        self.assertEqual(payload["timezone"], "Asia/Kolkata")
        self.assertEqual(payload["local_iso"], "2026-11-06T18:00:00+05:30")

    def test_unknown_timezone_raises_value_error(self):
        with patch(
            "tara_app.mcp_servers.time_logic.ZoneInfo",
            side_effect=ZoneInfoNotFoundError("Mars/Olympus"),
        ):
            with self.assertRaisesRegex(ValueError, "unknown timezone: Mars/Olympus"):
                current_time_payload("Mars/Olympus")

    def test_rejects_blank_timezone_name(self):
        with self.assertRaisesRegex(ValueError, "1–64 characters"):
            current_time_payload("   ")

    def test_rejects_timezone_name_longer_than_64_characters(self):
        with self.assertRaisesRegex(ValueError, "1–64 characters"):
            current_time_payload("A" * 65)


class McpTimeServerTests(unittest.TestCase):
    def _fake_mcp_modules(self):
        fastmcp_module = ModuleType("mcp.server.fastmcp")

        class FakeFastMCP:
            instances = []

            def __init__(self, name):
                self.name = name
                self.tools = {}
                self.transport = None
                self.__class__.instances.append(self)

            def tool(self):
                def register(function):
                    self.tools[function.__name__] = function
                    return function

                return register

            def run(self, *, transport):
                self.transport = transport

        fastmcp_module.FastMCP = FakeFastMCP
        server_module = ModuleType("mcp.server")
        server_module.__path__ = []
        server_module.fastmcp = fastmcp_module
        mcp_module = ModuleType("mcp")
        mcp_module.__path__ = []
        mcp_module.server = server_module
        return mcp_module, server_module, fastmcp_module, FakeFastMCP

    def test_main_registers_read_only_time_tool_and_uses_stdio(self):
        mcp_module, server_module, fastmcp_module, fake_server = self._fake_mcp_modules()
        expected = {"utc_iso": "2026-11-06T12:30:00Z", "unix_seconds": "1793968200"}

        with (
            patch.dict(
                sys.modules,
                {
                    "mcp": mcp_module,
                    "mcp.server": server_module,
                    "mcp.server.fastmcp": fastmcp_module,
                },
            ),
            patch(
                "tara_app.mcp_servers.time_server.current_time_payload",
                return_value=expected,
            ) as time_payload,
        ):
            self.assertEqual(main(), 0)

        server = fake_server.instances[-1]
        self.assertEqual(server.name, "tara-time")
        self.assertEqual(server.transport, "stdio")
        self.assertEqual(set(server.tools), {"get_current_time"})
        self.assertEqual(json.loads(server.tools["get_current_time"]("Asia/Kolkata")), expected)
        time_payload.assert_called_once_with("Asia/Kolkata")

    def test_time_tool_returns_validation_errors_as_json(self):
        mcp_module, server_module, fastmcp_module, fake_server = self._fake_mcp_modules()

        with (
            patch.dict(
                sys.modules,
                {
                    "mcp": mcp_module,
                    "mcp.server": server_module,
                    "mcp.server.fastmcp": fastmcp_module,
                },
            ),
            patch(
                "tara_app.mcp_servers.time_server.current_time_payload",
                side_effect=ValueError("unknown timezone: Mars/Olympus"),
            ),
        ):
            self.assertEqual(main(), 0)

        result = fake_server.instances[-1].tools["get_current_time"]("Mars/Olympus")
        self.assertEqual(
            json.loads(result),
            {"error": "unknown timezone: Mars/Olympus"},
        )

    def test_main_reports_missing_optional_mcp_package(self):
        stderr = io.StringIO()
        with patch.dict(sys.modules, {"mcp": None}), contextlib.redirect_stderr(stderr):
            self.assertEqual(main(), 2)

        self.assertIn("optional mcp package is not installed", stderr.getvalue())
        self.assertIn("pip install -e '.[mcp]'", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
