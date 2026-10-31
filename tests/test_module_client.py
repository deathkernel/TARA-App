from __future__ import annotations

import json
import sys
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from tara_app.contracts import Capability, ModuleRequest
from tara_app.module_client import ModuleProcessError, StdioModuleAdapter


class StdioModuleAdapterTests(unittest.TestCase):
    class FakeProcess:
        def __init__(self, response: dict[str, object]):
            self.returncode = 0
            self.stdout = json.dumps(response)

        def communicate(self, input=None, timeout=None):
            return self.stdout, ""

        def poll(self):
            return self.returncode

    def adapter(self, capability: Capability | None = None) -> StdioModuleAdapter:
        cap = capability or Capability("research", "answer", "Answer with sourced research", True)
        return StdioModuleAdapter(
            "research",
            (cap,),
            ("python", "-m", "tara_research"),
            working_directory=Path(__file__).resolve().parent,
        )

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
        with patch("tara_app.module_client.subprocess.Popen", return_value=self.FakeProcess(response)) as popen:
            result = adapter.execute(request)
        self.assertEqual(result.status, "success")
        self.assertEqual(result.data["summary"], "Evidence-backed answer")
        self.assertFalse(popen.call_args.kwargs["shell"])

    def test_side_effect_action_requires_token_before_starting_process(self) -> None:
        cap = Capability("research", "answer", "Side effect", False, True)
        adapter = self.adapter(cap)
        request = ModuleRequest("req-2", "session-1", "research", "answer", {})
        with patch("tara_app.module_client.subprocess.Popen") as popen:
            result = adapter.execute(request)
        self.assertEqual(result.status, "approval_required")
        popen.assert_not_called()

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
        with patch("tara_app.module_client.subprocess.Popen", return_value=self.FakeProcess(response)):
            self.assertEqual(adapter.health().status, "healthy")

    def test_cancel_request_terminates_active_child_process(self) -> None:
        adapter = StdioModuleAdapter(
            "research",
            (Capability("research", "answer", "Answer with sourced research", True),),
            (sys.executable, "-c", "import time; time.sleep(30)"),
            working_directory=Path(__file__).resolve().parent,
            timeout_seconds=60,
        )
        request = ModuleRequest("req-cancel", "session-1", "research", "answer", {})
        results = []
        worker = threading.Thread(target=lambda: results.append(adapter.execute(request)))
        worker.start()
        deadline = time.monotonic() + 3
        active = False
        while time.monotonic() < deadline:
            with adapter._process_lock:
                active = "req-cancel" in adapter._active_processes
            if active:
                break
            time.sleep(0.01)
        self.assertTrue(active, "child process did not start")
        self.assertTrue(adapter.cancel_request("req-cancel"))
        worker.join(timeout=3)
        self.assertFalse(worker.is_alive(), "cancelled child process did not exit")
        self.assertEqual(results[0].status, "cancelled")

    def test_mismatched_request_id_is_rejected(self) -> None:
        adapter = self.adapter()
        response = {"schema_version": "1.0", "request_id": "wrong", "status": "success", "data": {}}
        request = ModuleRequest("req-3", "session-1", "research", "answer", {})
        with patch("tara_app.module_client.subprocess.Popen", return_value=self.FakeProcess(response)):
            with self.assertRaises(ModuleProcessError):
                adapter.execute(request)


if __name__ == "__main__":
    unittest.main()
