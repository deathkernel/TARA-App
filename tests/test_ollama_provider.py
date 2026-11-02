"""Offline contract tests for the loopback-only Ollama adapter."""
import json
import socket
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

    def test_pre_cancelled_chat_is_rejected_before_network_call(self):
        """Reject an already-cancelled request without opening a connection."""
        from threading import Event

        cancelled = Event()
        cancelled.set()
        with patch("tara_app.providers.ollama.http.client.HTTPConnection") as factory:
            with self.assertRaisesRegex(ProviderError, "cancelled"):
                OllamaProvider().chat_cancellable(
                    "tinyllama", [{"role": "user", "content": "hi"}],
                    cancel_event=cancelled,
                )
            factory.assert_not_called()

    def test_cancellation_closes_a_blocked_provider_request(self):
        """Close the active HTTP connection when its cancellation event is set."""
        import threading
        import time

        closed = threading.Event()
        connection = Mock()
        connection.sock = None

        def blocked_request(*args, **kwargs):
            closed.wait(2)
            raise OSError("connection closed")

        connection.request.side_effect = blocked_request
        connection.close.side_effect = lambda: closed.set()
        cancelled = threading.Event()
        provider = OllamaProvider(chat_timeout_seconds=5)

        def cancel_soon():
            time.sleep(0.1)
            cancelled.set()

        with patch("tara_app.providers.ollama.http.client.HTTPConnection", return_value=connection):
            canceller = threading.Thread(target=cancel_soon)
            canceller.start()
            with self.assertRaisesRegex(ProviderError, "cancelled"):
                provider.chat_cancellable(
                    "tinyllama", [{"role": "user", "content": "hi"}],
                    cancel_event=cancelled,
                )
            canceller.join(1)
        self.assertTrue(closed.is_set())

    def test_wall_clock_timeout_closes_a_blocked_provider_request(self):
        """Close a blocked request when its total wall-clock deadline expires."""
        import threading

        closed = threading.Event()
        connection = Mock()
        connection.sock = None

        def blocked_request(*args, **kwargs):
            closed.wait(2)
            raise OSError("connection closed")

        connection.request.side_effect = blocked_request
        connection.close.side_effect = lambda: closed.set()
        provider = OllamaProvider(chat_timeout_seconds=1)

        with patch("tara_app.providers.ollama.http.client.HTTPConnection", return_value=connection):
            with self.assertRaisesRegex(ProviderError, "timed out"):
                provider.chat("tinyllama", [{"role": "user", "content": "hi"}])

        self.assertTrue(closed.is_set())

    def test_cancellation_interrupts_a_pending_connection_attempt(self):
        """Cancellation is polled while the loopback TCP connect is still pending."""
        import threading

        connection = Mock()
        connection.sock = None
        cancelled = threading.Event()
        connect_started = threading.Event()

        def blocked_connect(address, timeout, source_address=None):
            connect_started.set()
            cancelled.wait(timeout=timeout)
            raise socket.timeout()

        connection.request.side_effect = lambda *args, **kwargs: connection.connect()
        provider = OllamaProvider(chat_timeout_seconds=5)

        def cancel_after_connect_starts():
            self.assertTrue(connect_started.wait(1))
            cancelled.set()

        with patch("tara_app.providers.ollama.http.client.HTTPConnection", return_value=connection), patch(
            "tara_app.providers.ollama.socket.create_connection", side_effect=blocked_connect
        ):
            canceller = threading.Thread(target=cancel_after_connect_starts)
            canceller.start()
            with self.assertRaisesRegex(ProviderError, "cancelled"):
                provider.chat_cancellable(
                    "tinyllama", [{"role": "user", "content": "hi"}],
                    cancel_event=cancelled,
                )
            canceller.join(1)

    def test_cancellation_interrupts_detached_response_socket(self):
        """The watchdog also closes the response socket after HTTPConnection detaches it."""
        import threading

        cancelled = threading.Event()
        read_released = threading.Event()
        response_socket = Mock()
        response_socket.shutdown.side_effect = lambda *_: read_released.set()
        response = Mock()
        response.status = 200
        response.fp.raw._sock = response_socket

        def blocked_read(_limit):
            self.assertTrue(read_released.wait(2))
            raise OSError("response socket interrupted")

        response.read.side_effect = blocked_read
        connection = Mock()
        connection.sock = None
        connection.getresponse.return_value = response
        provider = OllamaProvider(chat_timeout_seconds=5)

        def cancel_soon():
            cancelled.set()

        with patch("tara_app.providers.ollama.http.client.HTTPConnection", return_value=connection):
            canceller = threading.Thread(target=cancel_soon)
            canceller.start()
            with self.assertRaisesRegex(ProviderError, "cancelled"):
                provider.chat_cancellable(
                    "tinyllama", [{"role": "user", "content": "hi"}],
                    cancel_event=cancelled,
                )
            canceller.join(1)

        response_socket.shutdown.assert_called_once()
        response_socket.close.assert_called_once()

    def test_http_errors_are_normalized(self):
        connection = fake_connection({"error": "not found"}, status=500)
        with patch("tara_app.providers.ollama.http.client.HTTPConnection", return_value=connection):
            with self.assertRaisesRegex(ProviderError, "HTTP 500"):
                OllamaProvider().list_models()


if __name__ == "__main__":
    unittest.main()
