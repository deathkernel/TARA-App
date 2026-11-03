"""Offline contract tests for the loopback-only Ollama adapter."""
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from tara_app.providers.ollama import OllamaProvider, ProviderError  # noqa: E402


def fake_connection(payload, status=200):
    connection = Mock()
    response = Mock()
    response.status = status
    response.read.return_value = json.dumps(payload).encode("utf-8")
    connection.getresponse.return_value = response
    return connection


class OllamaProviderTests(unittest.TestCase):
    def test_only_uses_loopback_address(self):
        with patch("tara_app.providers.ollama.http.client.HTTPConnection") as factory:
            factory.return_value = fake_connection({"models": []})
            self.assertEqual(OllamaProvider().list_models(), [])
            self.assertEqual(factory.call_args.args[:2], ("127.0.0.1", 11434))

    def test_rejects_invalid_port_and_timeout(self):
        for port in (70000, True, "11434"):
            with self.subTest(port=port), self.assertRaises(ValueError):
                OllamaProvider(port=port)
        for timeout in (0, True, "10"):
            with self.subTest(timeout=timeout), self.assertRaises(ValueError):
                OllamaProvider(timeout_seconds=timeout)

    def test_lists_models_without_downloading(self):
        connection = fake_connection({"models": [
            {
                "name": "tinyllama:latest",
                "size": 123,
                "digest": "sha256:abc",
                "modified_at": "2026-10-25T10:00:00Z",
                "details": {
                    "family": "llama",
                    "parameter_size": "1B",
                    "quantization_level": "Q4_0",
                    "format": "gguf",
                },
            },
            {"bad": True},
        ]})
        with patch("tara_app.providers.ollama.http.client.HTTPConnection", return_value=connection):
            models = OllamaProvider().list_models()
        self.assertEqual(len(models), 1)
        model = models[0]
        self.assertEqual(model.name, "tinyllama:latest")
        self.assertEqual(model.size, 123)
        self.assertEqual(model.digest, "sha256:abc")
        self.assertEqual(model.modified_at, "2026-10-25T10:00:00Z")
        self.assertEqual(model.family, "llama")
        self.assertEqual(model.parameter_size, "1B")
        self.assertEqual(model.quantization_level, "Q4_0")
        self.assertEqual(model.model_format, "gguf")
        connection.request.assert_called_once_with("GET", "/api/tags", body=None, headers={"Accept": "application/json"})

    def test_chat_uses_non_streaming_local_endpoint(self):
        connection = fake_connection({"message": {"content": "hello"}})
        with patch("tara_app.providers.ollama.http.client.HTTPConnection", return_value=connection):
            result = OllamaProvider().chat("tinyllama", [{"role": "user", "content": "hi"}])
        self.assertEqual(result, "hello")
        args = connection.request.call_args
        self.assertEqual(args.args[:2], ("POST", "/api/chat"))
        self.assertEqual(json.loads(args.kwargs["body"])["stream"], False)

    def test_chat_rejects_malformed_inputs_before_network_call(self):
        provider = OllamaProvider()
        for model, messages in (
            ("", [{"role": "user", "content": "hi"}]),
            (None, [{"role": "user", "content": "hi"}]),
            ("tinyllama", []),
            ("tinyllama", "not a message list"),
            ("tinyllama", ["not an object"]),
            ("tinyllama", [{"role": "user", "content": None}]),
        ):
            with self.subTest(model=model, messages=messages), self.assertRaises(ValueError):
                provider.chat(model, messages)

    def test_http_errors_are_normalized(self):
        connection = fake_connection({"error": "not found"}, status=500)
        with patch("tara_app.providers.ollama.http.client.HTTPConnection", return_value=connection):
            with self.assertRaisesRegex(ProviderError, "HTTP 500"):
                OllamaProvider().list_models()


if __name__ == "__main__":
    unittest.main()
