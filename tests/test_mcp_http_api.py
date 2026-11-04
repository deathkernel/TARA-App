"""Loopback HTTP tests for MCP status, discovery, approval and calls."""
from __future__ import annotations

import json
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from tara_app.mcp_app import McpOrchestratorMixin
from tara_app.mcp_client import McpToolInfo
from tara_app.mcp_registry import parse_mcp_config
from tara_app.webapp import _Server


class _Gateway:
    def __init__(self):
        self.config = parse_mcp_config({
            "enable": True,
            "servers": [{
                "name": "time",
                "command": ["uvx", "mcp-server-time"],
                "read_only": True,
                "read_only_tools": ["get_current_time"],
            }],
        })
        self.calls = []

    def list_tools(self, server_name=None):
        return [McpToolInfo(
            server="time",
            name="get_current_time",
            description="Get the current time",
            input_schema={"type": "object"},
        )]

    def call_tool(self, server, tool, arguments, *, approval_token):
        self.calls.append((server, tool, dict(arguments), approval_token))
        return "2026-11-04T12:00:00+05:30"


class _App(McpOrchestratorMixin):
    def __init__(self):
        self._init_mcp_state(_Gateway())


class McpHttpApiTests(unittest.TestCase):
    def setUp(self):
        self.server = _Server(("127.0.0.1", 0), _App())
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self._stop_server)
        self.base_url = f"http://127.0.0.1:{self.server.server_port}"

    def _stop_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def _post(self, path, payload, headers=None):
        request = Request(
            self.base_url + path,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", **(headers or {})},
            method="POST",
        )
        with urlopen(request, timeout=2) as response:
            return response.status, json.loads(response.read().decode("utf-8"))

    def test_status_and_tools_endpoints(self):
        with urlopen(self.base_url + "/api/mcp/status", timeout=2) as response:
            status = json.loads(response.read().decode("utf-8"))
        with urlopen(self.base_url + "/api/mcp/tools?server=time", timeout=2) as response:
            tools = json.loads(response.read().decode("utf-8"))
        self.assertEqual(status["status"], "enabled")
        self.assertEqual(status["enabled_server_count"], 1)
        self.assertEqual(tools["tools"][0]["name"], "get_current_time")

    def test_approval_and_call_are_one_shot(self):
        payload = {
            "server": "time",
            "tool": "get_current_time",
            "arguments": {"timezone": "Asia/Kolkata"},
            "session_id": "session-1",
        }
        _, approved = self._post("/api/mcp/approve", payload)
        self.assertEqual(approved["status"], "approved")
        call_payload = {**payload, "approval_token": approved["approval_token"]}
        _, called = self._post("/api/mcp/call", call_payload)
        self.assertEqual(called["status"], "success")
        self.assertEqual(len(self.server.app.mcp_gateway.calls), 1)
        with self.assertRaises(HTTPError) as caught:
            self._post("/api/mcp/call", call_payload)
        self.assertEqual(caught.exception.code, 400)

    def test_mcp_endpoints_reject_untrusted_origin(self):
        request = Request(
            self.base_url + "/api/mcp/status",
            headers={"Origin": "http://evil.example"},
        )
        with self.assertRaises(HTTPError) as caught:
            urlopen(request, timeout=2)
        self.assertEqual(caught.exception.code, 403)

    def test_tools_reject_duplicate_query_parameters(self):
        with self.assertRaises(HTTPError) as caught:
            urlopen(self.base_url + "/api/mcp/tools?server=time&server=git", timeout=2)
        self.assertEqual(caught.exception.code, 400)

    def test_approval_rejects_extra_fields(self):
        payload = {
            "server": "time",
            "tool": "get_current_time",
            "arguments": {},
            "session_id": "session-1",
            "unexpected": True,
        }
        with self.assertRaises(HTTPError) as caught:
            self._post("/api/mcp/approve", payload)
        self.assertEqual(caught.exception.code, 400)


if __name__ == "__main__":
    unittest.main()
