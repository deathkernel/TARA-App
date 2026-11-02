from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from tara_chat.omniroute_provider import OmniRouteProvider
from tara_chat.llm_provider_factory import provider_from_env


class OmniRouteProviderTests(unittest.TestCase):
    def test_sends_auto_route_alias_and_system_context(self):
        calls = []

        def transport(url, payload, api_key, timeout):
            calls.append((url, payload, api_key, timeout))
            return {"choices": [{"message": {"content": "Hello from TARA"}}]}

        provider = OmniRouteProvider(
            api_key="test-key",
            transport=transport,
        )
        result = provider.complete(
            "Hi",
            system="You are TARA",
            max_completion_tokens=128,
            temperature=0.2,
        )

        self.assertEqual(result, "Hello from TARA")
        url, payload, key, timeout = calls[0]
        self.assertEqual(url, "http://127.0.0.1:20128/v1/chat/completions")
        self.assertEqual(payload["model"], "auto")
        self.assertEqual(payload["stream"], False)
        self.assertEqual(payload["messages"][0], {"role": "system", "content": "You are TARA"})
        self.assertEqual(key, "test-key")
        self.assertEqual(timeout, 180.0)

    def test_supports_specialized_auto_route_alias(self):
        provider = OmniRouteProvider(api_key="test-key", model="auto/coding")
        self.assertEqual(provider.model, "auto/coding")

    def test_requires_api_key_and_v1_base_url(self):
        with self.assertRaises(ValueError):
            OmniRouteProvider(api_key="")
        with self.assertRaises(ValueError):
            OmniRouteProvider(api_key="test-key", base_url="http://127.0.0.1:20128")

    def test_rejects_non_loopback_gateway(self):
        with self.assertRaises(ValueError):
            OmniRouteProvider(api_key="test-key", base_url="https://gateway.example/v1")

    def test_rejects_redirect_like_invalid_model_input(self):
        with self.assertRaises(ValueError):
            OmniRouteProvider(api_key="test-key", model="auto route")

    def test_rejects_empty_or_malformed_completion(self):
        provider = OmniRouteProvider(api_key="test-key", transport=lambda *args: {"choices": []})
        with self.assertRaisesRegex(RuntimeError, "chat completion"):
            provider.complete("hello")

    def test_factory_selects_omniroute_only_when_explicitly_enabled(self):
        env = {
            "TARA_LLM_BACKEND": "omniroute",
            "TARA_OMNIROUTE_API_KEY": "test-key",
        }
        with patch.dict(os.environ, env, clear=True):
            provider = provider_from_env()
        self.assertIsInstance(provider, OmniRouteProvider)
        self.assertEqual(provider.model, "auto")

    def test_factory_defaults_to_omniroute(self):
        with patch.dict(os.environ, {"TARA_OMNIROUTE_API_KEY": "test-key"}, clear=True):
            provider = provider_from_env()
        self.assertIsInstance(provider, OmniRouteProvider)

    def test_stream_complete_yields_tokens(self):
        calls = []

        def fake_stream(url, payload, api_key, timeout):
            calls.append((url, payload, api_key, timeout))
            yield "Hello"
            yield " from"
            yield " TARA"

        provider = OmniRouteProvider(api_key="test-key")
        provider._stream_transport = fake_stream

        chunks = list(provider.stream_complete("Hi", system="You are TARA"))
        self.assertEqual(chunks, ["Hello", " from", " TARA"])
        url, payload, key, timeout = calls[0]
        self.assertEqual(url, "http://127.0.0.1:20128/v1/chat/completions")
        self.assertEqual(payload["stream"], True)
        self.assertEqual(payload["model"], "auto")

    def test_factory_rejects_ollama_backend(self):
        with patch.dict(os.environ, {"TARA_LLM_BACKEND": "ollama"}, clear=True):
            with self.assertRaisesRegex(ValueError, "OmniRoute only"):
                provider_from_env()


if __name__ == "__main__":
    unittest.main()
