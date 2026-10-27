from __future__ import annotations

import unittest

from tara_app.orchestrator import Orchestrator


class ApprovalInputValidationTests(unittest.TestCase):
    def add_website(self, question: str):
        inputs = {}
        Orchestrator._add_approval_inputs(inputs, "action", "execute", question, "request-1")
        return inputs

    def test_explicit_url_query_punctuation_is_preserved(self):
        inputs = self.add_website("Open https://example.com/search?q=why?")
        self.assertEqual(inputs["url"], "https://example.com/search?q=why?")

    def test_invalid_port_is_rejected_before_pending_approval(self):
        with self.assertRaises(ValueError):
            self.add_website("Open https://example.com:99999/path")

    def test_oversized_url_is_rejected_before_pending_approval(self):
        with self.assertRaises(ValueError):
            self.add_website("Open https://example.com/" + "a" * 2050)


if __name__ == "__main__":
    unittest.main()
