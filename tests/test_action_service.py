from __future__ import annotations

import unittest
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


if __name__ == "__main__":
    unittest.main()
