"""Regression tests for security boundaries in built-in MCP helpers."""
from __future__ import annotations

import os
import socket
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from tara_app.mcp_servers.fetch_logic import FetchError, _PinnedHTTPConnection, fetch_text
from tara_app.mcp_servers.git_read_logic import _run_git
from tara_app.tool_loop import ToolPlan, ToolStep, ToolStepStatus
from tara_app.tool_loop_bridge import run_validated_tool_plan
from tara_app.runtime import _remote_permission_message


class FetchSecurityTests(unittest.TestCase):
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
    def test_git_read_disables_repository_fsmonitor_and_external_config(self):
        completed = SimpleNamespace(returncode=0, stdout=b"## main\n", stderr=b"")
        with patch("tara_app.mcp_servers.git_read_logic.subprocess.run", return_value=completed) as run:
            self.assertEqual(_run_git(Path("/repo"), ["status", "--porcelain"]), "## main\n")

        args, kwargs = run.call_args
        self.assertIn("core.fsmonitor=false", args[0])
        self.assertEqual(kwargs["env"]["GIT_CONFIG_NOSYSTEM"], "1")
        self.assertEqual(kwargs["env"]["GIT_CONFIG_GLOBAL"], os.devnull)
        self.assertFalse(kwargs["shell"])


class ToolLoopApprovalTests(unittest.TestCase):
    def test_bridge_never_mints_approval_tokens(self):
        class Gateway:
            _config = SimpleNamespace(enabled_servers=[SimpleNamespace(name="write-server")])

        class Coordinator:
            mcp_gateway = Gateway()

            def __init__(self):
                self.issued = 0
                self.calls = []

            def issue_mcp_approval_token(self, *args, **kwargs):
                self.issued += 1
                return "forged-by-bridge"

            def call_mcp_tool(self, *args, **kwargs):
                self.calls.append((args, kwargs))
                return "mutated"

        coordinator = Coordinator()
        plan = ToolPlan(
            "approval-check",
            (ToolStep("write", "write-server.update", {"value": 1}, read_only=False),),
        )
        result = run_validated_tool_plan(coordinator, plan, session_id="session-1")

        self.assertEqual(result.steps[0].status, ToolStepStatus.WAITING_APPROVAL)
        self.assertEqual(coordinator.issued, 0)
        self.assertEqual(coordinator.calls, [])

    def test_bridge_mints_app_token_only_for_configured_read_only_tool(self):
        class Gateway:
            _config = SimpleNamespace(
                enabled_servers=[
                    SimpleNamespace(
                        name="read-server",
                        read_only=True,
                        read_only_tools=("list_items",),
                    )
                ]
            )

        class Coordinator:
            mcp_gateway = Gateway()

            def __init__(self):
                self.issued = 0
                self.calls = []

            def issue_mcp_approval_token(self, *args, **kwargs):
                self.issued += 1
                return "app-read-only-token"

            def call_mcp_tool(self, *args, **kwargs):
                self.calls.append((args, kwargs))
                return "listed"

        coordinator = Coordinator()
        plan = ToolPlan(
            "read-only-check",
            (ToolStep("read", "read-server.list_items", {}, read_only=True),),
        )
        result = run_validated_tool_plan(coordinator, plan, session_id="session-1")

        self.assertEqual(result.steps[0].status, ToolStepStatus.SUCCEEDED)
        self.assertEqual(coordinator.issued, 1)
        self.assertEqual(coordinator.calls[0][1]["approval_token"], "app-read-only-token")

    def test_bridge_uses_only_a_supplied_approval_token(self):
        class Gateway:
            _config = SimpleNamespace(enabled_servers=[SimpleNamespace(name="write-server")])

        class Coordinator:
            mcp_gateway = Gateway()

            def __init__(self):
                self.calls = []

            def issue_mcp_approval_token(self, *args, **kwargs):
                raise AssertionError("bridge must not issue approval tokens")

            def call_mcp_tool(self, *args, **kwargs):
                self.calls.append((args, kwargs))
                return "approved"

        coordinator = Coordinator()
        plan = ToolPlan(
            "approval-check-supplied",
            (ToolStep("write", "write-server.update", {"value": 1}, read_only=False),),
        )
        result = run_validated_tool_plan(
            coordinator,
            plan,
            session_id="session-1",
            approval_tokens={"write": "human-approved-token"},
        )

        self.assertEqual(result.steps[0].status, ToolStepStatus.SUCCEEDED)
        self.assertEqual(len(coordinator.calls), 1)
        self.assertEqual(coordinator.calls[0][1]["approval_token"], "human-approved-token")


class RemotePermissionMessageTests(unittest.TestCase):
    def test_voice_message_describes_local_audio_and_weight_download(self):
        message = _remote_permission_message("voice")
        self.assertIn("audio transcription", message)
        self.assertIn("on-device", message)
        self.assertNotIn("OmniRoute", message)

    def test_public_api_modules_do_not_claim_omniroute_processing(self):
        self.assertIn("public research sources", _remote_permission_message("research"))
        self.assertIn("Open-Meteo", _remote_permission_message("weather"))


if __name__ == "__main__":
    unittest.main()
