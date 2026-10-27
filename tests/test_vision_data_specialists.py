from __future__ import annotations

import base64
import os
import unittest
from unittest.mock import patch

from tara_data.__main__ import handle_request as handle_data
from tara_vision.__main__ import _ollama_origin, handle_request as handle_vision


class VisionSpecialistTests(unittest.TestCase):
    def test_vision_rejects_non_local_ollama_endpoint(self):
        with patch.dict(os.environ, {"TARA_VISION_OLLAMA_URL": "https://example.com"}):
            with self.assertRaises(ValueError):
                _ollama_origin()

    def test_vision_health_does_not_send_an_image_or_call_a_model(self):
        result = handle_vision({
            "schema_version": "1.0", "request_id": "vision-health",
            "module": "vision", "action": "health", "inputs": {},
        })
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["data"]["provider"], "ollama")

    def test_vision_rejects_oversized_or_invalid_image_payloads(self):
        result = handle_vision({
            "schema_version": "1.0", "request_id": "vision-bad",
            "module": "vision", "action": "analyze", "inputs": {"images": ["%%%"]},
        })
        self.assertEqual(result["status"], "invalid_request")


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
