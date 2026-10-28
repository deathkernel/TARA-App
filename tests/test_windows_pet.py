from __future__ import annotations

import errno
import unittest
import urllib.error
import urllib.request
from unittest.mock import patch

from tara_app.windows_pet import (
    _LoopbackOnlyRedirectHandler,
    _create_local_server,
    _pet_window_geometry,
    build_chat_payload,
    extract_answer,
    run_floating_pet,
    trim_transcript_text,
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

    def test_post_chat_rejects_redirects_without_following_them(self) -> None:
        from tara_app.windows_pet import _post_chat

        class RedirectingOpener:
            def open(self, request, timeout):
                raise urllib.error.HTTPError(
                    request.full_url,
                    302,
                    "Found",
                    {"Location": "https://example.com/collect"},
                    None,
                )

        with patch("tara_app.windows_pet.urllib.request.build_opener", return_value=RedirectingOpener()):
            with self.assertRaisesRegex(RuntimeError, "HTTP 302"):
                _post_chat("http://127.0.0.1:8765", {"question": "hello"})

    def test_post_chat_rejects_oversized_response(self) -> None:
        from tara_app.windows_pet import _post_chat

        class OversizedResponse:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self, limit):
                return b"x" * limit

        class OversizedOpener:
            def open(self, request, timeout):
                return OversizedResponse()

        with patch("tara_app.windows_pet.urllib.request.build_opener", return_value=OversizedOpener()):
            with self.assertRaisesRegex(RuntimeError, "1 MB limit"):
                _post_chat("http://127.0.0.1:8765", {"question": "hello"})

    def test_post_chat_rejects_invalid_json_response(self) -> None:
        from tara_app.windows_pet import _post_chat

        class InvalidJsonResponse:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self, limit):
                return b"{not json"

        class InvalidJsonOpener:
            def open(self, request, timeout):
                return InvalidJsonResponse()

        with patch("tara_app.windows_pet.urllib.request.build_opener", return_value=InvalidJsonOpener()):
            with self.assertRaisesRegex(RuntimeError, "invalid response"):
                _post_chat("http://127.0.0.1:8765", {"question": "hello"})

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

    def test_transcript_is_bounded_to_newest_content(self) -> None:
        self.assertEqual(trim_transcript_text("abcdefgh", 4), "efgh")
        self.assertEqual(trim_transcript_text("short", 10), "short")

    def test_transcript_bound_must_be_positive_integer(self) -> None:
        for value in (0, -1, True, 1.5):
            with self.subTest(value=value), self.assertRaises(ValueError):
                trim_transcript_text("hello", value)

    def test_local_server_uses_preferred_port_when_available(self) -> None:
        class FakeServer:
            server_port = 8765

        app = object()
        with patch("tara_app.webapp._Server", return_value=FakeServer()) as server_factory:
            server, port = _create_local_server(app, 8765)

        self.assertEqual(port, 8765)
        self.assertIsInstance(server, FakeServer)
        server_factory.assert_called_once_with(("127.0.0.1", 8765), app)

    def test_local_server_falls_back_to_ephemeral_port_when_preferred_port_is_busy(self) -> None:
        class FakeServer:
            server_port = 43210

        busy = OSError(errno.EADDRINUSE, "address already in use")
        with patch("tara_app.webapp._Server", side_effect=[busy, FakeServer()]) as server_factory:
            server, port = _create_local_server(object(), 8765)

        self.assertEqual(port, 43210)
        self.assertIsInstance(server, FakeServer)
        self.assertEqual(server_factory.call_args_list[0].args[0], ("127.0.0.1", 8765))
        self.assertEqual(server_factory.call_args_list[1].args[0], ("127.0.0.1", 0))

    def test_local_server_does_not_mask_unrelated_bind_errors(self) -> None:
        with patch("tara_app.webapp._Server", side_effect=OSError(errno.EACCES, "permission denied")) as server_factory:
            with self.assertRaises(OSError):
                _create_local_server(object(), 8765)

        server_factory.assert_called_once()

    def test_local_server_reports_fallback_bind_failure(self) -> None:
        with patch(
            "tara_app.webapp._Server",
            side_effect=[
                OSError(errno.EADDRINUSE, "address already in use"),
                OSError(errno.EACCES, "permission denied"),
            ],
        ):
            with self.assertRaisesRegex(RuntimeError, "could not bind its local chat server"):
                _create_local_server(object(), 8765)


    def test_chat_panel_expands_below_pet_without_moving_pet_center(self) -> None:
        self.assertEqual(
            _pet_window_geometry(expanded=True, pet_center_x=300, top_y=120),
            "390x620+105+120",
        )
        self.assertEqual(
            _pet_window_geometry(expanded=False, pet_center_x=300, top_y=120),
            "132x150+234+120",
        )

    def test_floating_pet_is_windows_only(self) -> None:
        with patch("tara_app.windows_pet.sys.platform", "linux"):
            with self.assertRaisesRegex(RuntimeError, "Windows only"):
                run_floating_pet(None)

    def test_rejects_non_object_response(self) -> None:
        with self.assertRaises(ValueError):
            extract_answer("unexpected")


if __name__ == "__main__":
    unittest.main()
