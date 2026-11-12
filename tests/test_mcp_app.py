"""Tests for operation-bound, one-shot MCP approvals."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tara_app.audit import AuditLogError, JsonlAuditLog
from tara_app.mcp_app import McpOrchestratorMixin
from tara_app.mcp_registry import parse_mcp_config


class _Gateway:
    def __init__(self):
        self.config = parse_mcp_config({
            "enable": True,
            "servers": [{
                "name": "time",
                "command": ["uvx", "mcp-server-time"],
                "read_only_tools": ["get_time"],
            }],
        })
        self.calls = []

    def call_tool(self, server, tool, arguments, *, approval_grant):
        self.calls.append((server, tool, dict(arguments or {}), approval_grant))
        if getattr(self, "fail_call", False):
            raise RuntimeError("gateway failed")
        return "ok"


class _MemoryAuditLog:
    def __init__(self, fail_on=None):
        self.events = []
        self.fail_on = fail_on

    def record(self, event_type, fields=None):
        if event_type == self.fail_on:
            raise AuditLogError("audit unavailable")
        self.events.append({"event_type": event_type, "fields": dict(fields or {})})


class _App(McpOrchestratorMixin):
    def __init__(self, audit_log=None):
        self.gateway = _Gateway()
        self.audit_log = audit_log or _MemoryAuditLog()
        self._init_mcp_state(self.gateway, audit_log=self.audit_log)


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

    def test_approval_expires_and_cannot_be_replayed(self):
        app = _App()
        with patch("tara_app.mcp_app.time.time", return_value=1_000):
            token = app.issue_mcp_approval_token(
                "time", "get_time", {"timezone": "UTC"}, session_id="session-1", ttl_seconds=30,
            )
        with patch("tara_app.mcp_app.time.time", return_value=1_031):
            with self.assertRaisesRegex(ValueError, "invalid or expired"):
                app.call_mcp_tool(
                    "time", "get_time", {"timezone": "UTC"},
                    approval_token=token, session_id="session-1",
                )
        self.assertEqual(app.gateway.calls, [])


    def test_durable_audit_records_only_digests_and_lifecycle_events(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "mcp.jsonl"
            app = _App(JsonlAuditLog(path, max_bytes=4096))
            arguments = {"timezone": "Asia/Kolkata", "private_value": "do-not-log"}
            token = app.issue_mcp_approval_token(
                "time", "get_time", arguments, session_id="session-secret",
            )
            self.assertEqual(app.call_mcp_tool(
                "time", "get_time", arguments,
                approval_token=token, session_id="session-secret",
            ), "ok")
            records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(
                [item["event_type"] for item in records],
                ["approval_issued", "tool_call_started", "tool_call_succeeded"],
            )
            serialized = path.read_text(encoding="utf-8")
            self.assertNotIn("do-not-log", serialized)
            self.assertNotIn("session-secret", serialized)
            self.assertNotIn(token, serialized)
            self.assertNotIn("Asia/Kolkata", serialized)
            self.assertEqual(len(records[0]["fields"]["session_digest"]), 64)
            self.assertEqual(len(records[0]["fields"]["arguments_digest"]), 64)
            self.assertIsInstance(records[0]["fields"]["expires_at"], float)

    def test_replayed_approval_is_rejected_and_audited(self):
        app = _App()
        arguments = {"timezone": "UTC"}
        token = app.issue_mcp_approval_token("time", "get_time", arguments, session_id="session-1")
        app.call_mcp_tool("time", "get_time", arguments, approval_token=token, session_id="session-1")
        with self.assertRaisesRegex(ValueError, "invalid or expired"):
            app.call_mcp_tool("time", "get_time", arguments, approval_token=token, session_id="session-1")
        self.assertEqual(
            [item["event_type"] for item in app.audit_log.events],
            ["approval_issued", "tool_call_started", "tool_call_succeeded", "approval_rejected"],
        )

    def test_audit_failure_revokes_approval_and_blocks_tool_dispatch(self):
        issue_app = _App(_MemoryAuditLog(fail_on="approval_issued"))
        with self.assertRaises(AuditLogError):
            issue_app.issue_mcp_approval_token("time", "get_time", {}, session_id="session-1")
        self.assertEqual(issue_app._mcp_approval_tokens, {})

        dispatch_app = _App(_MemoryAuditLog(fail_on="tool_call_started"))
        token = dispatch_app.issue_mcp_approval_token("time", "get_time", {}, session_id="session-1")
        with self.assertRaises(AuditLogError):
            dispatch_app.call_mcp_tool(
                "time", "get_time", {}, approval_token=token, session_id="session-1",
            )
        self.assertEqual(dispatch_app.gateway.calls, [])
        self.assertEqual(dispatch_app._mcp_approval_tokens, {})

    def test_post_dispatch_audit_failure_marks_health_degraded_without_retrying(self):
        audit = _MemoryAuditLog(fail_on="tool_call_succeeded")
        app = _App(audit)
        token = app.issue_mcp_approval_token("time", "get_time", {}, session_id="session-1")
        self.assertEqual(
            app.call_mcp_tool("time", "get_time", {}, approval_token=token, session_id="session-1"),
            "ok",
        )
        self.assertEqual(len(app.gateway.calls), 1)
        self.assertEqual(app.mcp_status()["audit_status"], "degraded")

    def test_gateway_failure_is_recorded_without_masking_the_error(self):
        app = _App()
        token = app.issue_mcp_approval_token("time", "get_time", {}, session_id="session-1")
        app.gateway.fail_call = True
        with self.assertRaisesRegex(RuntimeError, "gateway failed"):
            app.call_mcp_tool("time", "get_time", {}, approval_token=token, session_id="session-1")
        self.assertEqual(
            [item["event_type"] for item in app.audit_log.events],
            ["approval_issued", "tool_call_started", "tool_call_failed"],
        )

    def test_approval_arguments_are_size_bounded(self):
        app = _App()
        with self.assertRaisesRegex(ValueError, "64 KiB"):
            app.issue_mcp_approval_token(
                "time", "get_time", {"value": "x" * 65_536}, session_id="session-1",
            )

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
