from __future__ import annotations

import io
import json
import unittest
from unittest.mock import patch

from tara_app.omniroute_health import check_gateway
from tara_chat.app_adapter import handle_request as handle_chat
from tara_models.__main__ import handle_request as handle_models
from tara_vision.__main__ import handle_request as handle_vision


def module_request(module: str) -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "request_id": f"{module}-health-test",
        "module": module,
        "action": "health",
        "inputs": {},
    }


class _Response:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def read(self, size: int = -1) -> bytes:
        return self.payload if size < 0 else self.payload[:size]


class _Opener:
    def __init__(self, response: _Response) -> None:
        self.response = response
        self.request = None
        self.timeout = None

    def open(self, request, timeout: float):
        self.request = request
        self.timeout = timeout
        return self.response


class OmniRouteLiveHealthTests(unittest.TestCase):
    def test_gateway_probe_uses_authenticated_models_endpoint(self) -> None:
        opener = _Opener(_Response(b'{"data":[{"id":"auto"}]}'))
        with patch("tara_app.omniroute_health.build_opener", return_value=opener):
            self.assertTrue(check_gateway("http://127.0.0.1:20128/v1", "test-key"))
        self.assertEqual(opener.request.full_url, "http://127.0.0.1:20128/v1/models")
        self.assertEqual(opener.request.get_method(), "GET")
        self.assertEqual(opener.request.get_header("Authorization"), "Bearer test-key")
        self.assertEqual(opener.timeout, 5.0)

    def test_gateway_probe_rejects_malformed_or_wrong_shape_catalogue(self) -> None:
        for payload in (b"not-json", b'{"models":[]}', b'{"data":{}}'):
            opener = _Opener(_Response(payload))
            with patch("tara_app.omniroute_health.build_opener", return_value=opener):
                self.assertFalse(check_gateway("http://127.0.0.1:20128/v1", "test-key"))

    def test_chat_health_fails_when_gateway_is_unreachable(self) -> None:
        with patch.dict("os.environ", {
            "TARA_OMNIROUTE_API_KEY": "test-key",
            "TARA_LLM_BACKEND": "omniroute",
        }, clear=True), patch("tara_chat.omniroute_provider.check_gateway", return_value=False):
            result = handle_chat(module_request("chat"))
        self.assertEqual(result["status"], "unavailable")
        self.assertNotIn("test-key", json.dumps(result))

    def test_vision_health_fails_when_gateway_is_unreachable(self) -> None:
        with patch.dict("os.environ", {
            "TARA_VISION_API_BASE_URL": "http://127.0.0.1:20128/v1",
            "TARA_VISION_API_KEY": "test-key",
        }, clear=True), patch("tara_vision.__main__.check_gateway", return_value=False):
            result = handle_vision(module_request("vision"))
        self.assertEqual(result["status"], "unavailable")
        self.assertNotIn("test-key", json.dumps(result))

    def test_model_hub_health_fails_when_gateway_is_unreachable(self) -> None:
        with patch.dict("os.environ", {
            "TARA_MODELS_API_BASE_URL": "http://127.0.0.1:20128/v1",
            "TARA_MODELS_API_KEY": "test-key",
        }, clear=True), patch("tara_models.__main__.check_gateway", return_value=False):
            result = handle_models(module_request("models"))
        self.assertEqual(result["status"], "unavailable")
        self.assertNotIn("test-key", json.dumps(result))

    def test_creative_health_fails_when_gateway_is_unreachable(self) -> None:
        from tara_creative import __main__ as creative

        request = module_request("creative")
        source = io.BytesIO(json.dumps(request).encode("utf-8"))

        class _Input:
            buffer = source

        output = io.StringIO()
        with patch("sys.stdin", _Input()), patch("sys.stdout", output), patch(
            "tara_creative.__main__._omniroute_config",
            return_value=("http://127.0.0.1:20128/v1", "test-key", "auto/cheap"),
        ), patch("tara_creative.__main__.check_gateway", return_value=False):
            self.assertEqual(creative.main(), 0)
        result = json.loads(output.getvalue())
        self.assertEqual(result["status"], "unavailable")
        self.assertNotIn("test-key", output.getvalue())


if __name__ == "__main__":
    unittest.main()
