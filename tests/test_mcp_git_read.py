"""Tests for read-only git MCP server logic."""
from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from tara_app.mcp_servers.git_read_logic import (
    GitReadError,
    git_log,
    git_show_file,
    git_status,
    resolve_repo,
)


class GitReadLogicTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.repo = self.root / "project"
        self.repo.mkdir()
        subprocess.run(["git", "init"], cwd=self.repo, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=self.repo, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=self.repo, check=True, capture_output=True)
        (self.repo / "README.md").write_text("hello\n", encoding="utf-8")
        subprocess.run(["git", "add", "README.md"], cwd=self.repo, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=self.repo, check=True, capture_output=True)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_outside_root_denied(self) -> None:
        with self.assertRaises(GitReadError):
            resolve_repo("/tmp", [str(self.root)])

    def test_status_and_log(self) -> None:
        status = git_status(str(self.repo), [str(self.root)])
        self.assertIn("status", status)
        log = git_log(str(self.repo), [str(self.root)], max_count=5)
        self.assertEqual(len(log["entries"]), 1)
        self.assertIn("init", log["entries"][0]["subject"])

    def test_show_file(self) -> None:
        shown = git_show_file(str(self.repo), [str(self.root)], path="README.md")
        self.assertEqual(shown["content"], "hello\n")

    def test_path_traversal_denied(self) -> None:
        with self.assertRaises(GitReadError):
            git_show_file(str(self.repo), [str(self.root)], path="../README.md")

    def test_option_like_revision_denied(self) -> None:
        with self.assertRaises(GitReadError):
            git_show_file(str(self.repo), [str(self.root)], path="README.md", revision="--output=/tmp/x")


if __name__ == "__main__":
    unittest.main()
