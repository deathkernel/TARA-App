from __future__ import annotations

import unittest
import urllib.request
from unittest.mock import patch

from tara_app.windows_pet import (
    _LoopbackOnlyRedirectHandler,
    build_chat_payload,
    extract_answer,
    run_floating_pet,
    validate_server_url,
)


class WindowsPetContractTests(unittest.TestCase):
    def test_accepts_only_loopback_http_origins(self) -> None:
        self.assertEqual(validate_server_url("http://127.0.0.1:8765"), "http://127.0.0.1:8765")
        self.assertEqual(validate_server_url("http://localhost:9000/"), "http://localhost:9000")

    def test_rejects_non_loopback_or_ambiguous_urls(self) -> None:
        for value in (
            "https://127.0.0.1:8765",
            "http://example.com:8765",
            "http://127.0.0.1:8765/api",
            "http://user@127.0.0.1:8765",
            "http://127.0.0.1:80",
            "http://127.0.0.1:8765/?token=secret",
        ):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_server_url(value)

    def test_chat_payload_bounds_history_and_omits_attachments(self) -> None:
        history = [{"role": "user", "content": f"message {i}"} for i in range(25)]
        payload = build_chat_payload("  hello  ", "session-1", history)
        self.assertEqual(payload["question"], "hello")
        self.assertEqual(payload["session_id"], "session-1")
        self.assertEqual(len(payload["history"]), 20)
        self.assertEqual(payload["history"][0]["content"], "message 5")
        self.assertEqual(payload["attachments"], [])

    def test_chat_payload_rejects_empty_or_oversized_prompt(self) -> None:
        with self.assertRaises(ValueError):
            build_chat_payload("  ", "session-1", [])
        with self.assertRaises(ValueError):
            build_chat_payload("x" * 20_001, "session-1", [])

    def test_extracts_existing_response_shapes(self) -> None:
        self.assertEqual(extract_answer({"result": {"data": {"text": "Hello"}}}), "Hello")
        self.assertEqual(extract_answer({"result": {"data": {"reply": "Hi"}}}), "Hi")
        self.assertEqual(extract_answer({"error": "unavailable"}), "unavailable")

    def test_redirect_handler_blocks_redirects_away_from_loopback(self) -> None:
        handler = _LoopbackOnlyRedirectHandler()
        request = urllib.request.Request("http://127.0.0.1:8765/api/chat", method="POST")
        redirected = handler.redirect_request(
            request,
            None,
            302,
            "Found",
            {},
            "https://example.com/collect",
        )
        self.assertIsNone(redirected)

    def test_chat_payload_filters_invalid_history_entries(self) -> None:
        payload = build_chat_payload(
            "hello",
            "session-1",
            [
                {"role": "system", "content": "not allowed"},
                {"role": "user", "content": "valid"},
                {"role": "assistant", "content": 123},
                "malformed",
            ],
        )
        self.assertEqual(payload["history"], [{"role": "user", "content": "valid"}])

    def test_chat_payload_rejects_invalid_session_id(self) -> None:
        with self.assertRaises(ValueError):
            build_chat_payload("hello", "", [])
        with self.assertRaises(ValueError):
            build_chat_payload("hello", "x" * 129, [])

    def test_floating_pet_is_windows_only(self) -> None:
        with patch("tara_app.windows_pet.sys.platform", "linux"):
            with self.assertRaisesRegex(RuntimeError, "Windows only"):
                run_floating_pet(None)

    def test_rejects_non_object_response(self) -> None:
        with self.assertRaises(ValueError):
            extract_answer("unexpected")


if __name__ == "__main__":
    unittest.main()
