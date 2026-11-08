from __future__ import annotations

import io
import json
import unittest
from unittest.mock import patch

from tara_app.stdio_runner import run_module


class StdioRunnerTests(unittest.TestCase):
    def _run(self, payload: dict[str, object], execute=None) -> dict[str, object]:
        stdin = io.TextIOWrapper(io.BytesIO(json.dumps(payload).encode("utf-8")))
        stdout = io.StringIO()
        with patch("sys.stdin", stdin), patch("sys.stdout", stdout):
            code = run_module("memory", execute or (lambda action, inputs, **kwargs: ("success", {"action": action}, None)))
        self.assertEqual(code, 0)
        return json.loads(stdout.getvalue())

    def test_dispatches_valid_request_to_module_executor(self) -> None:
        response = self._run({
            "schema_version": "1.0", "request_id": "r1", "module": "memory",
            "action": "search", "inputs": {"query": "hello"},
        })
        self.assertEqual(response["status"], "success")
        self.assertEqual(response["data"], {"action": "search"})

    def test_health_request_does_not_call_executor(self) -> None:
        def fail(*args, **kwargs):
            raise AssertionError("health must not invoke module execution")
        response = self._run({
            "schema_version": "1.0", "request_id": "r2", "module": "memory",
            "action": "health", "inputs": {},
        }, fail)
        self.assertEqual(response["data"], {"healthy": True})

    def test_rejects_request_for_another_module(self) -> None:
        response = self._run({
            "schema_version": "1.0", "request_id": "r3", "module": "security",
            "action": "assess", "inputs": {},
        })
        self.assertEqual(response["status"], "invalid_request")

    def test_rejects_unknown_request_fields(self) -> None:
        response = self._run({
            "schema_version": "1.0", "request_id": "r4", "module": "memory",
            "action": "search", "inputs": {}, "unexpected": True,
        })
        self.assertEqual(response["status"], "invalid_request")


if __name__ == "__main__":
    unittest.main()
