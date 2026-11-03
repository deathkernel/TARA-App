from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from tara_creative.service import _omniroute_config, execute


class OmniRouteCreativeTests(unittest.TestCase):
    def setUp(self):
        self.env = {
            "TARA_CREATIVE_API_BASE_URL": "http://127.0.0.1:20128/v1",
            "TARA_CREATIVE_API_KEY": "test-key",
            "TARA_CREATIVE_MODEL": "auto/cheap",
        }

    def test_creative_generation_uses_omniroute_and_marks_remote_transfer(self):
        with patch.dict(os.environ, self.env), patch(
            "tara_creative.service._generate", return_value=("A polished draft", "provider/model")
        ):
            status, data, error = execute("write", {"brief": "Write a short introduction"})
        self.assertEqual(status, "success")
        self.assertIsNone(error)
        self.assertEqual(data["text"], "A polished draft")
        self.assertEqual(data["provider"], "omniroute")
        self.assertEqual(data["model"], "provider/model")
        self.assertTrue(data["remote_data_transfer"])

    def test_creative_rejects_non_loopback_gateway(self):
        with patch.dict(os.environ, {**self.env, "TARA_CREATIVE_API_BASE_URL": "https://example.com/v1"}):
            with self.assertRaises(ValueError):
                _omniroute_config()

    def test_missing_gateway_key_fails_without_local_fallback(self):
        with patch.dict(os.environ, {"TARA_CREATIVE_API_BASE_URL": self.env["TARA_CREATIVE_API_BASE_URL"]}, clear=True):
            status, data, error = execute("write", {"brief": "Write a short introduction"})
        self.assertEqual(status, "unavailable")
        self.assertEqual(data, {})
        self.assertIn("OmniRoute API key", error)


if __name__ == "__main__":
    unittest.main()
