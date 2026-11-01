from __future__ import annotations

import json
import os
import unittest
from io import BytesIO
from unittest.mock import patch
from urllib.error import HTTPError

from tara_code import __main__ as code_module
from tara_app.runtime import RuntimeConfigurationError, _ollama_settings, _omniroute_settings


class FakeResponse:
    def __init__(self, body: dict[str, object], headers: dict[str, str] | None = None) -> None:
        self.raw = json.dumps(body).encode("utf-8")
        self.headers = headers or {}

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self, size: int = -1) -> bytes:
        return self.raw if size < 0 else self.raw[:size]


class FakeOpener:
    def __init__(self, response: FakeResponse | None = None, error: Exception | None = None) -> None:
        self.response = response
        self.error = error
        self.request = None
        self.timeout = None

    def open(self, request, timeout: int):
        self.request = request
        self.timeout = timeout
        if self.error:
            raise self.error
        return self.response


class TaraCodeOmniRouteTests(unittest.TestCase):
    def request(self) -> dict[str, object]:
        return {
            "schema_version": "1.0",
            "request_id": "code-test-1",
            "module": "code",
            "action": "plan",
            "inputs": {"question": "Review this function"},
        }

    def test_uses_openai_compatible_endpoint_and_bearer_auth(self) -> None:
        opener = FakeOpener(FakeResponse({
            "model": "provider/model-id",
            "choices": [{"message": {"content": "Review plan"}}],
        }))
        with patch.dict(os.environ, {
            "TARA_CODE_API_BASE_URL": "http://127.0.0.1:20128/v1",
            "TARA_CODE_API_KEY": "local-test-key",
            "TARA_CODE_MODEL": "auto/coding",
        }), patch.object(code_module, "_omniroute_opener", return_value=opener):
            result = code_module.handle_request(self.request())

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["data"]["text"], "Review plan")
        self.assertEqual(result["data"]["provider"], "omniroute")
        self.assertEqual(result["data"]["model"], "provider/model-id")
        self.assertFalse(result["data"]["execution_performed"])
        self.assertEqual(opener.request.full_url, "http://127.0.0.1:20128/v1/chat/completions")
        self.assertEqual(opener.request.get_header("Authorization"), "Bearer local-test-key")
        self.assertEqual(json.loads(opener.request.data)["model"], "auto/coding")
        self.assertEqual(opener.timeout, 150)

    def test_missing_api_key_fails_closed(self) -> None:
        with patch.dict(os.environ, {
            "TARA_CODE_API_BASE_URL": "http://127.0.0.1:20128/v1",
            "TARA_CODE_API_KEY": "",
        }), patch.object(code_module, "_omniroute_opener") as opener:
            result = code_module.handle_request(self.request())
        self.assertEqual(result["status"], "unavailable")
        opener.assert_not_called()

    def test_rejects_non_loopback_gateway(self) -> None:
        with patch.dict(os.environ, {
            "TARA_CODE_API_BASE_URL": "http://example.com/v1",
            "TARA_CODE_API_KEY": "local-test-key",
        }):
            result = code_module.handle_request(self.request())
        self.assertEqual(result["status"], "invalid_request")

    def test_health_checks_local_models_endpoint(self) -> None:
        opener = FakeOpener(FakeResponse({"data": []}))
        request = self.request()
        request["action"] = "health"
        with patch.dict(os.environ, {
            "TARA_CODE_API_BASE_URL": "http://127.0.0.1:20128/v1",
            "TARA_CODE_API_KEY": "local-test-key",
        }), patch.object(code_module, "_omniroute_opener", return_value=opener):
            result = code_module.handle_request(request)
        self.assertEqual(result["status"], "success")
        self.assertEqual(opener.request.full_url, "http://127.0.0.1:20128/v1/models")
        self.assertEqual(opener.request.get_method(), "GET")
        self.assertEqual(opener.timeout, 8)

    def test_gateway_auth_error_does_not_leak_response_body(self) -> None:
        error = HTTPError(
            "http://127.0.0.1:20128/v1/chat/completions",
            401,
            "Unauthorized",
            {},
            BytesIO(b"secret diagnostic"),
        )
        opener = FakeOpener(error=error)
        with patch.dict(os.environ, {
            "TARA_CODE_API_BASE_URL": "http://127.0.0.1:20128/v1",
            "TARA_CODE_API_KEY": "local-test-key",
        }), patch.object(code_module, "_omniroute_opener", return_value=opener):
            result = code_module.handle_request(self.request())
        self.assertEqual(result["status"], "unavailable")
        self.assertNotIn("secret diagnostic", result["error"])

    def test_omniroute_config_is_loopback_only_and_keeps_secrets_out(self) -> None:
        settings = _omniroute_settings({
            "base_url": "http://127.0.0.1:20128/v1",
            "model": "auto/coding",
        })
        self.assertEqual(settings, {
            "TARA_CODE_API_BASE_URL": "http://127.0.0.1:20128/v1",
            "TARA_CODE_MODEL": "auto/coding",
        })
        with self.assertRaises(RuntimeConfigurationError):
            _omniroute_settings({"base_url": "https://api.example.com/v1"})

    def test_old_ollama_code_setting_is_ignored_and_new_defaults_apply(self) -> None:
        legacy = _ollama_settings({"models": {"code": "legacy-coder-model"}})
        self.assertNotIn("code", legacy)
        defaults = _omniroute_settings(None)
        self.assertEqual(defaults["TARA_CODE_API_BASE_URL"], "http://127.0.0.1:20128/v1")
        self.assertEqual(defaults["TARA_CODE_MODEL"], "auto/coding:cheap")


if __name__ == "__main__":
    unittest.main()
