from __future__ import annotations

import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from tara_app.contracts import ModuleRequest
from tara_app.handler_adapter import HandlerProcessAdapter


class HandlerProcessAdapterTests(unittest.TestCase):
    def test_cancel_request_stops_active_handler_process(self) -> None:
        finished = threading.Event()

        class FakeProcess:
            pid = 12345

            def __init__(self):
                self.returncode = None

            def poll(self):
                return self.returncode

            def communicate(self, timeout=None):
                if not finished.wait(timeout):
                    raise TimeoutError("test process did not stop")
                return "diagnostic output", ""

            def terminate(self):
                self.returncode = -15
                finished.set()

        process = FakeProcess()
        adapter = HandlerProcessAdapter(
            ("python", "doctor"),
            working_directory=Path(__file__).resolve().parent,
        )
        request = ModuleRequest("handler-cancel", "session-1", "handler", "diagnose", {})
        results = []
        worker = threading.Thread(target=lambda: results.append(adapter.execute(request)))
        with patch("tara_app.handler_adapter.subprocess.Popen", return_value=process), patch(
            "tara_app.handler_adapter._terminate_process_tree",
            side_effect=lambda child: child.terminate(),
        ):
            worker.start()
            deadline = threading.Event()
            for _ in range(200):
                with adapter._process_lock:
                    active = "handler-cancel" in adapter._active_processes
                if active:
                    break
                deadline.wait(0.01)
            self.assertTrue(active, "Handler process did not start")
            self.assertTrue(adapter.cancel_request("handler-cancel"))
            worker.join(timeout=2)
        self.assertFalse(worker.is_alive())
        self.assertEqual(results[0].status, "cancelled")


if __name__ == "__main__":
    unittest.main()
