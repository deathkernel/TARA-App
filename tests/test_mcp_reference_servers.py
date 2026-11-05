"""Tests for built-in MCP reference server logic (no live MCP stdio required)."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

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
        self.assertTrue(payload["utc_iso"].endswith("Z") or "+" in payload["utc_iso"])

    def test_named_timezone(self) -> None:
        payload = current_time_payload("UTC")
        self.assertEqual(payload["timezone"], "UTC")
        self.assertIn("local_iso", payload)

    def test_unknown_timezone_rejected(self) -> None:
        with self.assertRaises(ValueError):
            current_time_payload("Not/A_Real_Zone")


class ScopedFsLogicTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "notes.txt").write_text("hello tara\n", encoding="utf-8")
        (self.root / "sub").mkdir()
        (self.root / "sub" / "a.txt").write_text("nested\n", encoding="utf-8")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_resolve_under_root(self) -> None:
        target = resolve_under_roots(str(self.root / "notes.txt"), [str(self.root)])
        self.assertEqual(target, (self.root / "notes.txt").resolve())

    def test_path_outside_root_denied(self) -> None:
        with self.assertRaises(ScopedFsError):
            resolve_under_roots("/etc/passwd", [str(self.root)])

    def test_traversal_denied(self) -> None:
        with self.assertRaises(ScopedFsError):
            resolve_under_roots(str(self.root / ".." / ".." / "etc" / "passwd"), [str(self.root)])

    def test_list_and_read(self) -> None:
        entries = list_directory(str(self.root), [str(self.root)])
        names = {item["name"] for item in entries}
        self.assertIn("notes.txt", names)
        self.assertIn("sub", names)
        text = read_text_file(str(self.root / "notes.txt"), [str(self.root)])
        self.assertEqual(text, "hello tara\n")


if __name__ == "__main__":
    unittest.main()
