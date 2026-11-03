from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

from tara_app.contracts import Capability, ModuleRequest
from tara_app.module_client import ModuleProcessError, StdioModuleAdapter


class StdioModuleAdapterTests(unittest.TestCase):
    def adapter(self, capability: Capability | None = None) -> StdioModuleAdapter:
        cap = capability or Capability("research", "answer", "Answer with sourced research", True)
        return StdioModuleAdapter(
            "research",
            (cap,),
            ("python", "-m", "tara_research"),
            working_directory=Path(__file__).resolve().parent,
        )

    @staticmethod
    def completed(response: dict[str, object]) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args=[], returncode=0, stdout=json.dumps(response), stderr="")

    def test_executes_registered_action_and_checks_request_id(self) -> None:
        adapter = self.adapter()
        response = {
            "schema_version": "1.0",
            "request_id": "req-1",
            "status": "success",
            "data": {"summary": "Evidence-backed answer"},
            "error": None,
            "duration_ms": 3,
        }
        request = ModuleRequest("req-1", "session-1", "research", "answer", {"question": "Why?"})
        with patch("tara_app.module_client.subprocess.run", return_value=self.completed(response)) as run:
            result = adapter.execute(request)
        self.assertEqual(result.status, "success")
        self.assertEqual(result.data["summary"], "Evidence-backed answer")
        self.assertFalse(run.call_args.kwargs["shell"])

    def test_side_effect_action_requires_token_before_starting_process(self) -> None:
        cap = Capability("research", "answer", "Side effect", False, True)
        adapter = self.adapter(cap)
        request = ModuleRequest("req-2", "session-1", "research", "answer", {})
        with patch("tara_app.module_client.subprocess.run") as run:
            result = adapter.execute(request)
        self.assertEqual(result.status, "approval_required")
        run.assert_not_called()

    def test_health_requires_matching_request_id_and_healthy_response(self) -> None:
        adapter = self.adapter()
        response = {
            "schema_version": "1.0",
            "request_id": "tara-health-check",
            "status": "success",
            "data": {"healthy": True},
            "error": None,
            "duration_ms": 0,
        }
        with patch("tara_app.module_client.subprocess.run", return_value=self.completed(response)):
            self.assertEqual(adapter.health().status, "healthy")

    def test_mismatched_request_id_is_rejected(self) -> None:
        adapter = self.adapter()
        response = {"schema_version": "1.0", "request_id": "wrong", "status": "success", "data": {}}
        request = ModuleRequest("req-3", "session-1", "research", "answer", {})
        with patch("tara_app.module_client.subprocess.run", return_value=self.completed(response)):
            with self.assertRaises(ModuleProcessError):
                adapter.execute(request)


if __name__ == "__main__":
    unittest.main()

