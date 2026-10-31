from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from tara_app.providers.bharatcode import BharatCodeError, BharatCodeProvider, DEFAULT_MODEL


class BharatCodeProviderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.key = patch.dict(os.environ, {"BHARATCODE_API_KEY": "test-key"}, clear=False)
        self.key.start()
        self.addCleanup(self.key.stop)

    @patch("tara_app.providers.bharatcode._request")
    def test_chat_uses_configured_model_and_stateless_messages(self, request) -> None:
        request.return_value = {"choices": [{"finish_reason": "stop", "message": {"content": "hello"}}]}
        provider = BharatCodeProvider()
        result = provider.chat([{"role": "user", "content": "hi"}])
        self.assertEqual(result, "hello")
        self.assertEqual(provider.model, DEFAULT_MODEL)
        self.assertEqual(request.call_args.args[0], "/chat/completions")
        payload = request.call_args.kwargs["payload"]
        self.assertEqual(payload["model"], DEFAULT_MODEL)
        self.assertEqual(payload["messages"], [{"role": "user", "content": "hi"}])
        self.assertFalse(payload["stream"])

    @patch("tara_app.providers.bharatcode._request")
    def test_length_finish_reason_is_not_accepted_as_complete(self, request) -> None:
        request.return_value = {"choices": [{"finish_reason": "length", "message": {"content": "partial"}}]}
        with self.assertRaisesRegex(BharatCodeError, "truncated"):
            BharatCodeProvider().chat([{"role": "user", "content": "hi"}])

    @patch("tara_app.providers.bharatcode._request")
    def test_model_discovery_uses_live_catalog(self, request) -> None:
        request.return_value = {"data": [{"id": DEFAULT_MODEL}, {"id": "deepseek-v4.1-flash"}]}
        self.assertEqual([item["id"] for item in BharatCodeProvider().list_models()], [DEFAULT_MODEL, "deepseek-v4.1-flash"])
        self.assertEqual(request.call_args.args[0], "/models")

    def test_missing_key_fails_before_network(self) -> None:
        with patch.dict(os.environ, {"BHARATCODE_API_KEY": ""}):
            with patch("tara_app.providers.bharatcode.urlopen") as urlopen:
                with self.assertRaisesRegex(BharatCodeError, "not configured"):
                    BharatCodeProvider().chat([{"role": "user", "content": "hi"}])
                urlopen.assert_not_called()

    def test_rejects_invalid_message_and_limits(self) -> None:
        provider = BharatCodeProvider()
        for messages in ([], "not messages", [{"role": "system", "content": None}], [{"role": "bad", "content": "x"}]):
            with self.subTest(messages=messages), self.assertRaises(ValueError):
                provider.chat(messages)
        with self.assertRaises(ValueError):
            provider.chat([{"role": "user", "content": "x"}], max_tokens=32_001)

    def test_complete_implements_chat_provider_contract(self) -> None:
        with patch.object(BharatCodeProvider, "chat", return_value="answer") as chat:
            result = BharatCodeProvider().complete("question", system="system", max_completion_tokens=300)
        self.assertEqual(result, "answer")
        self.assertEqual(chat.call_args.kwargs["max_tokens"], 300)


if __name__ == "__main__":
    unittest.main()
