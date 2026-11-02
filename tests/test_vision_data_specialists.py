from __future__ import annotations

import base64
import os
import unittest
from unittest.mock import patch

from tara_data.__main__ import handle_request as handle_data
from tara_vision.__main__ import _omniroute_base_url, handle_request as handle_vision


class VisionSpecialistTests(unittest.TestCase):
    def test_vision_rejects_non_loopback_gateway_endpoint(self):
        with patch.dict(os.environ, {"TARA_VISION_API_BASE_URL": "https://example.com"}):
            with self.assertRaises(ValueError):
                _omniroute_base_url()

    def test_vision_health_reports_omniroute_configuration(self):
        env = {
            "TARA_VISION_API_BASE_URL": "http://127.0.0.1:20128/v1",
            "TARA_VISION_API_KEY": "test-key",
        }
        with patch.dict(os.environ, env):
            result = handle_vision({
                "schema_version": "1.0", "request_id": "vision-health",
                "module": "vision", "action": "health", "inputs": {},
            })
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["data"]["provider"], "omniroute")

    def test_vision_rejects_invalid_image_payloads(self):
        result = handle_vision({
            "schema_version": "1.0", "request_id": "vision-bad",
            "module": "vision", "action": "analyze", "inputs": {"images": ["%%%"]},
        })
        self.assertEqual(result["status"], "invalid_request")

    def test_vision_sends_openai_compatible_image_content_to_omniroute(self):
        from tara_vision.__main__ import _post_chat_completion
        png = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"fake-png").decode("ascii")
        env = {
            "TARA_VISION_API_BASE_URL": "http://127.0.0.1:20128/v1",
            "TARA_VISION_API_KEY": "test-key",
            "TARA_VISION_MODEL": "auto",
        }
        response = {"text": "A test image", "model": "vision-model"}
        with patch.dict(os.environ, env), patch("tara_vision.__main__._post_chat_completion", return_value=response) as call:
            result = handle_vision({
                "schema_version": "1.0", "request_id": "vision-image",
                "module": "vision", "action": "analyze",
                "inputs": {"question": "Describe this", "images": [png]},
            })
        self.assertEqual(result["status"], "success")
        self.assertTrue(result["data"]["images_sent_to_remote"])
        payload = call.call_args.args[1]
        user_content = payload["messages"][1]["content"]
        self.assertEqual(user_content[0]["type"], "text")
        self.assertTrue(user_content[1]["image_url"]["url"].startswith("data:image/png;base64,"))


class DataSpecialistTests(unittest.TestCase):
    def test_data_returns_bounded_numeric_and_missing_value_summaries(self):
        result = handle_data({
            "schema_version": "1.0", "request_id": "data-1",
            "module": "data", "action": "analyze",
            "inputs": {"csv_text": "name,score\nAri,2\nBea,4\nCam,\n"},
        })
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["data"]["rows"], 3)
        self.assertEqual(result["data"]["missing_values"]["score"], 1)
        self.assertEqual(result["data"]["numeric_summary"]["score"]["mean"], 3.0)
        self.assertTrue(result["data"]["read_only"])

    def test_data_rejects_inconsistent_csv_rows(self):
        result = handle_data({
            "schema_version": "1.0", "request_id": "data-2",
            "module": "data", "action": "analyze",
            "inputs": {"csv_text": "name,score\nAri,2,extra\n"},
        })
        self.assertEqual(result["status"], "invalid_request")


if __name__ == "__main__":
    unittest.main()
