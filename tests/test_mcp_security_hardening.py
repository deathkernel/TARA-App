"""Regression tests for hardened built-in MCP reference servers."""
from __future__ import annotations

import os
import socket
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from tara_app.mcp_servers.fetch_logic import FetchError, _PinnedHTTPConnection, fetch_text
from tara_app.mcp_servers.git_read_logic import _run_git
from tara_app.mcp_servers.scoped_fs_logic import ScopedFsError, read_text_file


class FetchSecurityTests(unittest.TestCase):
    """Verify public-network pinning and redirect rejection."""

    def test_dns_resolution_rejects_any_non_public_answer(self):
        public = (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))
        private = (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))
        with patch("tara_app.mcp_servers.fetch_logic.socket.getaddrinfo", return_value=[public, private]):
            with self.assertRaisesRegex(FetchError, "non-public"):
                fetch_text("https://example.test")

    def test_redirects_are_not_followed(self):
        class Response:
            status = 302

            def getheader(self, name):
                return "https://127.0.0.1/admin" if name == "Location" else ""

        class Connection:
            requested = False
            closed = False

            def request(self, *args, **kwargs):
                self.requested = True

            def getresponse(self):
                return Response()

            def close(self):
                self.closed = True

        connection = Connection()
        with (
            patch("tara_app.mcp_servers.fetch_logic._public_address", return_value="93.184.216.34"),
            patch("tara_app.mcp_servers.fetch_logic._PinnedHTTPSConnection", return_value=connection),
        ):
            with self.assertRaisesRegex(FetchError, "redirects are not followed"):
                fetch_text("https://example.test/start")

        self.assertTrue(connection.requested)
        self.assertTrue(connection.closed)

    def test_http_connection_uses_the_validated_ip(self):
        class FakeSocket:
            def close(self):
                pass

        fake_socket = FakeSocket()
        with patch("tara_app.mcp_servers.fetch_logic.socket.create_connection", return_value=fake_socket) as connect:
            connection = _PinnedHTTPConnection("example.test", 8080, "93.184.216.34", 3.0)
            connection.connect()
        connect.assert_called_once_with(("93.184.216.34", 8080), 3.0)
        self.assertIs(connection.sock, fake_socket)
        connection.close()


class GitReadSecurityTests(unittest.TestCase):
    """Ensure repository configuration cannot run helpers during read operations."""

    def test_git_read_disables_repository_fsmonitor_and_external_config(self):
        completed = SimpleNamespace(returncode=0, stdout=b"## main\n", stderr=b"")
        with patch("tara_app.mcp_servers.git_read_logic.subprocess.run", return_value=completed) as run:
            self.assertEqual(_run_git(Path("/repo"), ["status", "--porcelain"]), "## main\n")

        args, kwargs = run.call_args
        self.assertIn("core.fsmonitor=false", args[0])
        self.assertEqual(kwargs["env"]["GIT_CONFIG_NOSYSTEM"], "1")
        self.assertEqual(kwargs["env"]["GIT_CONFIG_GLOBAL"], os.devnull)
        self.assertFalse(kwargs["shell"])


class ScopedFilesystemSecurityTests(unittest.TestCase):
    """Reject symlink escapes and non-text file reads."""

    def test_read_rejects_symlink_that_resolves_outside_root(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "root"
            outside = Path(temporary) / "outside.txt"
            root.mkdir()
            outside.write_text("secret", encoding="utf-8")
            link = root / "linked.txt"
            try:
                link.symlink_to(outside)
            except (OSError, NotImplementedError):
                self.skipTest("symlink creation is unavailable on this platform")

            with self.assertRaises(ScopedFsError):
                read_text_file(str(link), [str(root)])

    def test_read_accepts_regular_utf8_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target = root / "notes.txt"
            target.write_text("safe text", encoding="utf-8")
            self.assertEqual(read_text_file(str(target), [str(root)]), "safe text")


if __name__ == "__main__":
    unittest.main()
