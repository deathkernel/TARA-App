"""Tests for operation-bound, one-shot MCP approvals."""
from __future__ import annotations
import unittest
from tara_app.mcp_app import McpOrchestratorMixin
from tara_app.mcp_registry import parse_mcp_config

class _Gateway:
    def __init__(self):
        self.config = parse_mcp_config({"enable": True, "servers": [{"name": "time", "command": ["uvx", "mcp-server-time"], "read_only_tools": ["get_time"]}]})
        self.calls = []
    def call_tool(self, server, tool, arguments, *, approval_grant):
        self.calls.append((server, tool, dict(arguments or {}), approval_grant))
        return "ok"

class _App(McpOrchestratorMixin):
    def __init__(self):
        self.gateway = _Gateway()
        self._init_mcp_state(self.gateway)

class McpApprovalTests(unittest.TestCase):
    def test_approval_is_bound_to_exact_call_and_session(self):
        app = _App()
        arguments = {"timezone": "Asia/Kolkata"}
        token = app.issue_mcp_approval_token("time", "get_time", arguments, session_id="session-1")
        with self.assertRaises(ValueError):
            app.call_mcp_tool("time", "get_time", {"timezone": "UTC"}, approval_token=token, session_id="session-1")
        with self.assertRaises(ValueError):
            app.call_mcp_tool("time", "get_time", arguments, approval_token=token, session_id="session-2")
        self.assertEqual(app.call_mcp_tool("time", "get_time", arguments, approval_token=token, session_id="session-1"), "ok")
        self.assertEqual(len(app.gateway.calls), 1)
        with self.assertRaises(ValueError):
            app.call_mcp_tool("time", "get_time", arguments, approval_token=token, session_id="session-1")

    def test_audit_log_records_approval_and_tool_call_without_secrets(self):
        app = _App()
        arguments = {"timezone": "Asia/Kolkata", "private_value": "do-not-log"}
        token = app.issue_mcp_approval_token("time", "get_time", arguments, session_id="session-secret")
        self.assertEqual(app.call_mcp_tool(
            "time", "get_time", arguments, approval_token=token, session_id="session-secret"
        ), "ok")
        audit = app.mcp_audit_log()
        self.assertEqual([event["event"] for event in audit["events"]], ["tool_call", "approval_issued"])
        self.assertEqual(audit["events"][0]["outcome"], "succeeded")
        serialized = str(audit)
        self.assertNotIn("do-not-log", serialized)
        self.assertNotIn("session-secret", serialized)
        self.assertNotIn(token, serialized)
        self.assertEqual(audit["retention"], "current_process")

    def test_audit_log_rejects_invalid_limits(self):
        app = _App()
        for limit in (0, 101, True, "10"):
            with self.subTest(limit=limit), self.assertRaises(ValueError):
                app.mcp_audit_log(limit)

    def test_approval_rejects_unlisted_read_only_tool(self):
        app = _App()
        with self.assertRaisesRegex(ValueError, "read-only allowlist"):
            app.issue_mcp_approval_token("time", "delete_file", {}, session_id="session-1")

    def test_approval_rejects_disabled_server(self):
        app = _App()
        with self.assertRaises(ValueError):
            app.issue_mcp_approval_token("filesystem", "read_file", {"path": "x"}, session_id="session-1")

    def test_approval_rejects_writable_server_until_security_gate_exists(self):
        app = _App()
        app.gateway.config = parse_mcp_config({
            "enable": True,
            "servers": [{
                "name": "filesystem",
                "command": ["uvx", "mcp-server-filesystem"],
                "read_only": False,
            }],
        })
        with self.assertRaisesRegex(ValueError, "explicitly allowlisted read-only tools"):
            app.issue_mcp_approval_token(
                "filesystem", "write_file", {"path": "notes.txt", "content": "hello"},
                session_id="session-1",
            )
        self.assertEqual(app.gateway.calls, [])

if __name__ == "__main__":
    unittest.main()
