"""Tests for operation-bound MCP approvals and redacted audit events."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tara_app.mcp_app import McpOrchestratorMixin
from tara_app.mcp_audit import McpAuditLog
from tara_app.mcp_registry import parse_mcp_config


class _Gateway:
    def __init__(self):
        self.config = parse_mcp_config({"enable": True, "servers": [{"name": "time", "command": ["uvx", "mcp-server-time"], "read_only_tools": ["get_time"]}]})
        self.calls = []

    def call_tool(self, server, tool, arguments, *, approval_grant):
        self.calls.append((server, tool, dict(arguments or {}), approval_grant))
        return "ok"


class _App(McpOrchestratorMixin):
    def __init__(self, audit_log=None):
        self.gateway = _Gateway()
        self._init_mcp_state(self.gateway, audit_log=audit_log)


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

    def test_audit_records_lifecycle_without_tokens_or_argument_values(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "mcp.jsonl"
            app = _App(McpAuditLog(path))
            arguments = {"timezone": "Asia/Kolkata", "api_key": "must-not-be-logged"}
            token = app.issue_mcp_approval_token("time", "get_time", arguments, session_id="session-1")
            app.call_mcp_tool("time", "get_time", arguments, approval_token=token, session_id="session-1")

            rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
            self.assertEqual([row["event"] for row in rows], ["approval_issued", "tool_call_succeeded"])
            raw_log = path.read_text(encoding="utf-8")
            self.assertNotIn(token, raw_log)
            self.assertNotIn("Asia/Kolkata", raw_log)
            self.assertNotIn("must-not-be-logged", raw_log)
            self.assertTrue(rows[0]["arguments_digest"])
            self.assertTrue(rows[0]["session_digest"])

    def test_audit_log_rotates_at_configured_size(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "mcp.jsonl"
            audit = McpAuditLog(path, max_bytes=4096)
            for _ in range(80):
                audit.record("approval_issued", server="time", tool="get_time")
            self.assertLessEqual(path.stat().st_size, 4096)
            self.assertTrue(path.with_suffix(".jsonl.1").exists())


if __name__ == "__main__":
    unittest.main()
