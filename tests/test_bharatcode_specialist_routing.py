from __future__ import annotations

import base64
import os
import unittest
from unittest.mock import patch

from tara_app.providers.bharatcode import BharatCodeProvider


class BharatCodeSpecialistRoutingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.env = patch.dict(os.environ, {
            "BHARATCODE_API_KEY": "test-key",
            "TARA_CODE_PROVIDER": "bharatcode",
            "TARA_CREATIVE_PROVIDER": "bharatcode",
            "TARA_VISION_PROVIDER": "bharatcode",
            "TARA_LLM_BACKEND": "bharatcode",
        }, clear=False)
        self.env.start()
        self.addCleanup(self.env.stop)

    @patch.object(BharatCodeProvider, "chat", return_value="review plan")
    def test_code_specialist_uses_bharatcode_without_enabling_execution(self, chat) -> None:
        from tara_code.__main__ import handle_request

        result = handle_request({
            "schema_version": "1.0",
            "request_id": "code-1",
            "module": "code",
            "action": "plan",
            "inputs": {"question": "Review this function"},
        })
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["data"]["provider"], "bharatcode")
        self.assertFalse(result["data"]["execution_performed"])
        chat.assert_called_once()

    @patch.object(BharatCodeProvider, "chat", return_value="A small image.")
    def test_vision_specialist_uses_bharatcode_only_when_selected(self, chat) -> None:
        from tara_vision.__main__ import handle_request

        png = base64.b64encode(b"\x89PNG\r\n\x1a\nimage-data").decode("ascii")
        result = handle_request({
            "schema_version": "1.0",
            "request_id": "vision-1",
            "module": "vision",
            "action": "analyze",
            "inputs": {"question": "Describe this", "images": [png]},
        })
        self.assertEqual(result["status"], "success")
        self.assertTrue(result["data"]["images_sent_to_remote"])
        messages = chat.call_args.args[0]
        self.assertIn("data:image/png;base64,", messages[1]["content"][1]["image_url"]["url"])

    @patch.object(BharatCodeProvider, "complete", return_value="A short story.")
    def test_creative_specialist_uses_bharatcode_only_when_selected(self, complete) -> None:
        from tara_creative.service import execute

        status, data, error = execute("write", {"brief": "A short story", "tone": "warm"})
        self.assertEqual(status, "success")
        self.assertEqual(data["provider"], "bharatcode")
        self.assertIsNone(error)
        complete.assert_called_once()

    @patch.object(BharatCodeProvider, "complete", return_value="Model Hub answer")
    def test_model_hub_can_select_bharatcode_qwen(self, complete) -> None:
        from tara_models.__main__ import handle_request

        result = handle_request({
            "schema_version": "1.0",
            "request_id": "models-1",
            "module": "models",
            "action": "generate",
            "inputs": {"question": "Explain binary search", "model": "qwen-3.8-27b"},
        })
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["data"]["provider"], "BharatCode")
        complete.assert_called_once()

    def test_chat_factory_selects_bharatcode_provider(self) -> None:
        from tara_chat.llm_provider_factory import provider_from_env

        provider = provider_from_env()
        self.assertIsInstance(provider, BharatCodeProvider)
        self.assertEqual(provider.model, "qwen-3.8-27b")

    def test_unknown_provider_fails_closed(self) -> None:
        from tara_chat.llm_provider_factory import provider_from_env

        with patch.dict(os.environ, {"TARA_LLM_BACKEND": "unknown"}):
            with self.assertRaisesRegex(ValueError, "Unsupported"):
                provider_from_env()


if __name__ == "__main__":
    unittest.main()
