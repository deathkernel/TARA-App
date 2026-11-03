from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from tara_models.__main__ import handle_request


class ModelHubTests(unittest.TestCase):
    def setUp(self):
        self.env = {
            "TARA_MODELS_API_BASE_URL": "http://127.0.0.1:20128/v1",
            "TARA_MODELS_API_KEY": "test-key",
            "TARA_MODELS_MODEL": "auto",
        }

    def test_health_reports_omniroute_as_the_only_provider(self):
        with patch.dict(os.environ, self.env), patch("tara_models.__main__.check_gateway", return_value=True):
            result = handle_request({
                "schema_version": "1.0", "request_id": "h",
                "module": "models", "action": "health", "inputs": {},
            })
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["data"]["provider"], "omniroute")

    def test_catalog_lists_only_models_returned_by_omniroute(self):
        payload = {"data": [{"id": "provider/model-a", "owned_by": "provider"}]}
        with patch.dict(os.environ, self.env), patch("tara_models.__main__._http_json", return_value=payload):
            result = handle_request({
                "schema_version": "1.0", "request_id": "catalog",
                "module": "models", "action": "catalog", "inputs": {},
            })
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["data"]["provider"], "omniroute")
        self.assertEqual([item["id"] for item in result["data"]["models"]], ["auto", "provider/model-a"])
        self.assertNotIn("gemini", result["data"]["text"].lower())
        self.assertNotIn("ollama", result["data"]["text"].lower())

    def test_generate_uses_the_selected_omniroute_model(self):
        payload = {"choices": [{"message": {"content": "Hello from OmniRoute"}}], "model": "provider/model-a"}
        with patch.dict(os.environ, self.env), patch("tara_models.__main__._http_json", return_value=payload) as call:
            result = handle_request({
                "schema_version": "1.0", "request_id": "generate",
                "module": "models", "action": "generate",
                "inputs": {"question": "Say hello", "model": "provider/model-a"},
            })
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["data"]["provider"], "omniroute")
        self.assertEqual(result["data"]["model"], "provider/model-a")
        self.assertTrue(result["data"]["remote_data_transfer"])
        self.assertTrue(call.call_args.args[0].endswith("/chat/completions"))

    def test_generate_parses_explicit_model_route_from_question(self):
        payload = {"choices": [{"message": {"content": "Hello"}}], "model": "provider/model-a"}
        with patch.dict(os.environ, self.env), patch("tara_models.__main__._http_json", return_value=payload) as call:
            result = handle_request({
                "schema_version": "1.0", "request_id": "selected",
                "module": "models", "action": "generate",
                "inputs": {"question": "Use model provider/model-a: say hello"},
            })
        self.assertEqual(result["status"], "success")
        body = call.call_args.kwargs["body"]
        self.assertEqual(body["model"], "provider/model-a")
        self.assertEqual(body["messages"][1]["content"], "say hello")

    def test_invalid_request_rejected(self):
        result = handle_request({
            "schema_version": "1.0", "request_id": "x",
            "module": "models", "action": "generate", "inputs": {"question": " "},
        })
        self.assertEqual(result["status"], "invalid_request")

    def test_invalid_request_is_rejected_before_gateway_configuration(self):
        with patch.dict(os.environ, {}, clear=True):
            result = handle_request({
                "schema_version": "1.0", "request_id": "invalid-no-gateway",
                "module": "models", "action": "generate", "inputs": {"question": " "},
            })
        self.assertEqual(result["status"], "invalid_request")

    def test_missing_gateway_key_does_not_fall_back_to_another_provider(self):
        with patch.dict(os.environ, {"TARA_MODELS_API_BASE_URL": self.env["TARA_MODELS_API_BASE_URL"]}, clear=True):
            result = handle_request({
                "schema_version": "1.0", "request_id": "missing-key",
                "module": "models", "action": "catalog", "inputs": {},
            })
        self.assertEqual(result["status"], "unavailable")
        self.assertIn("OmniRoute", result["error"])


if __name__ == "__main__":
    unittest.main()
