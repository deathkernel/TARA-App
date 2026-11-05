"""Tests for built-in MCP reference server logic (no live MCP stdio required)."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from tara_app.application.facade import ApplicationFacade
from tara_app.mcp_servers.fetch_logic import FetchError, validate_public_https_url
from tara_app.mcp_servers.scoped_fs_logic import (
    ScopedFsError,
    list_directory,
    read_text_file,
    resolve_under_roots,
)
from tara_app.mcp_servers.time_logic import current_time_payload


class TimeLogicTests(unittest.TestCase):
    def test_utc_payload(self) -> None:
        payload = current_time_payload()
        self.assertIn("utc_iso", payload)
        self.assertIn("unix_seconds", payload)

    def test_unknown_timezone_rejected(self) -> None:
        with self.assertRaises(ValueError):
            current_time_payload("Not/A_Real_Zone")


class ScopedFsLogicTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "notes.txt").write_text("hello tara\n", encoding="utf-8")
        (self.root / "sub").mkdir()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_path_outside_root_denied(self) -> None:
        with self.assertRaises(ScopedFsError):
            resolve_under_roots("/etc/passwd", [str(self.root)])

    def test_list_and_read(self) -> None:
        entries = list_directory(str(self.root), [str(self.root)])
        names = {item["name"] for item in entries}
        self.assertIn("notes.txt", names)
        text = read_text_file(str(self.root / "notes.txt"), [str(self.root)])
        self.assertEqual(text, "hello tara\n")


class FetchLogicTests(unittest.TestCase):
    def test_rejects_file_scheme(self) -> None:
        with self.assertRaises(FetchError):
            validate_public_https_url("file:///etc/passwd")

    def test_rejects_localhost(self) -> None:
        with self.assertRaises(FetchError):
            validate_public_https_url("http://localhost/secret")

    def test_rejects_private_ip(self) -> None:
        with self.assertRaises(FetchError):
            validate_public_https_url("http://127.0.0.1/x")
        with self.assertRaises(FetchError):
            validate_public_https_url("http://10.0.0.1/x")

    def test_rejects_credentials(self) -> None:
        with self.assertRaises(FetchError):
            validate_public_https_url("https://user:pass@example.com/")


class HealthMcpSummaryTests(unittest.TestCase):
    def test_health_includes_mcp_summary(self) -> None:
        coordinator = MagicMock()
        coordinator.registry.capability_ids.return_value = ("chat.reply",)
        coordinator.registry.adapter.return_value = None
        coordinator.registry.disabled_modules.return_value = {}
        coordinator.mcp_status.return_value = {
            "enable": False,
            "status": "disabled",
            "package_available": False,
            "enabled_server_count": 0,
        }
        facade = ApplicationFacade(coordinator)
        payload = facade.health_status()
        self.assertIn("mcp", payload)
        self.assertEqual(payload["mcp"]["status"], "disabled")
        self.assertFalse(payload["mcp"]["enable"])


if __name__ == "__main__":
    unittest.main()
