from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from tara_action import service


class DesktopActionServiceTests(unittest.TestCase):
    def test_invalid_port_is_rejected(self):
        status, _, _ = service._open_website("https://example.com:99999/path")
        self.assertEqual(status, "invalid_request")

    def test_oversized_url_is_rejected(self):
        status, _, _ = service._open_website("https://example.com/" + "a" * 2050)
        self.assertEqual(status, "invalid_request")

    def test_url_with_query_punctuation_is_preserved(self):
        with patch.object(service.webbrowser, "open", return_value=True) as open_browser:
            status, data, error = service._open_website("https://example.com/search?q=why?")
        self.assertEqual(status, "success")
        self.assertIsNone(error)
        self.assertEqual(data["url"], "https://example.com/search?q=why?")
        open_browser.assert_called_once_with("https://example.com/search?q=why?", new=2, autoraise=True)

    def test_orchestrator_metadata_is_ignored_but_unknown_fields_are_rejected(self):
        with patch.object(service, "_open_website", return_value=("success", {"url": "https://example.com"}, None)):
            status, _, _ = service.execute(
                "execute",
                {
                    "operation": "desktop.url.open",
                    "url": "https://example.com",
                    "question": "Open https://example.com",
                    "attachments": [],
                    "policy_tags": ["desktop_automation", "human_approval"],
                },
                approval_token="one-time-approval",
            )
        self.assertEqual(status, "success")

        status, _, _ = service.execute(
            "execute",
            {"operation": "desktop.url.open", "url": "https://example.com", "unexpected": True},
            approval_token="one-time-approval",
        )
        self.assertEqual(status, "invalid_request")

    def test_system_status_returns_metrics(self):
        status, data, err = service.execute(
            "execute",
            {"operation": "desktop.system.status"},
            approval_token="one-time-approval",
        )
        self.assertEqual(status, "success")
        self.assertIsNone(err)
        self.assertIn("memory", data)
        self.assertIn("cpu", data)
        self.assertIn("disk", data)

    def test_process_list_returns_processes(self):
        if not sys.platform.startswith("win"):
            self.skipTest("Windows-only process listing test")
        status, data, err = service.execute(
            "execute",
            {"operation": "desktop.process.list", "limit": 10},
            approval_token="one-time-approval",
        )
        self.assertEqual(status, "success")
        self.assertIsNone(err)
        self.assertIn("processes", data)
        self.assertLessEqual(len(data["processes"]), 10)

    def test_process_terminate_rejects_invalid_pid(self):
        status, _, err = service.execute(
            "execute",
            {"operation": "desktop.process.terminate", "pid": 0},
            approval_token="one-time-approval",
        )
        self.assertEqual(status, "invalid_request")

        status, _, err = service.execute(
            "execute",
            {"operation": "desktop.process.terminate", "pid": 4},
            approval_token="one-time-approval",
        )
        self.assertEqual(status, "invalid_request")

    def test_file_inspect_validates_and_blocks_system_dirs(self):
        status, data, err = service.execute(
            "execute",
            {"operation": "desktop.file.inspect", "path": "README.md"},
            approval_token="one-time-approval",
        )
        self.assertEqual(status, "success")
        self.assertIsNone(err)
        self.assertFalse(data["is_dir"])
        self.assertGreater(data["size_bytes"], 0)

        # Block C:\Windows\System32
        status, _, err = service.execute(
            "execute",
            {"operation": "desktop.file.inspect", "path": "C:\\Windows\\System32\\drivers"},
            approval_token="one-time-approval",
        )
        self.assertEqual(status, "permission_denied")

    def test_expanded_app_allowlist(self):
        for app in ["calculator", "notepad", "paint", "explorer", "taskmgr", "terminal"]:
            self.assertIn(app, service._APP_COMMANDS)


if __name__ == "__main__":
    unittest.main()
