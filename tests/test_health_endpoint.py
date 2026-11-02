"""Loopback health endpoint tests for the local TARA web server."""
from __future__ import annotations

import json
import sys
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from tara_app.webapp import _Server
from tara_app.ollama_models import OllamaModelCatalog


class _Registry:
    def capability_ids(self):
        return ("chat.respond", "models.catalog")


class _App:
    registry = _Registry()
    model_catalog = None


class HealthEndpointTests(unittest.TestCase):
    def setUp(self):
        self.server = _Server(("127.0.0.1", 0), _App())
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self._stop_server)
        self.base_url = f"http://127.0.0.1:{self.server.server_port}"

    def _stop_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def test_health_reports_app_and_registered_capabilities(self):
        with urlopen(self.base_url + "/api/health", timeout=2) as response:
            self.assertEqual(response.status, 200)
            payload = json.loads(response.read().decode("utf-8"))
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["app"], "TARA-App")
        self.assertEqual(payload["api_version"], "1.0")
        self.assertEqual(payload["capability_count"], 2)
        self.assertEqual(payload["capabilities"], ["chat.respond", "models.catalog"])
        self.assertEqual(payload["model_runtime"], "omniroute")


    def test_health_reports_empty_catalog_as_not_configured(self):
        self.server.app.model_catalog = OllamaModelCatalog()
        with urlopen(self.base_url + "/api/health", timeout=2) as response:
            payload = json.loads(response.read().decode("utf-8"))
        self.assertEqual(payload["model_runtime"], "omniroute")

    def test_system_diagnostics_endpoint(self):
        with urlopen(self.base_url + "/api/system/diagnostics", timeout=2) as response:
            self.assertEqual(response.status, 200)
            payload = json.loads(response.read().decode("utf-8"))
        self.assertEqual(payload["status"], "success")
        self.assertIn("diagnostics", payload)
        self.assertIn("hardware", payload["diagnostics"])

    def test_settings_endpoints(self):
        # Test GET /api/settings
        with urlopen(self.base_url + "/api/settings", timeout=2) as response:
            self.assertEqual(response.status, 200)
            payload = json.loads(response.read().decode("utf-8"))
        self.assertEqual(payload["status"], "success")
        self.assertIn("settings", payload)
        self.assertIn("secrets", payload["settings"])

        # Test POST /api/settings/secret
        req = Request(
            self.base_url + "/api/settings/secret",
            data=json.dumps({"key": "TEST_VAULT_KEY", "value": "secret_123"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(req, timeout=2) as response:
            self.assertEqual(response.status, 200)
            res_payload = json.loads(response.read().decode("utf-8"))
        self.assertEqual(res_payload["status"], "success")
        self.assertEqual(res_payload["key"], "TEST_VAULT_KEY")

    def test_health_rejects_untrusted_origin(self):
        request = Request(
            self.base_url + "/api/health",
            headers={"Origin": "http://evil.example"},
        )
        with self.assertRaises(HTTPError) as caught:
            urlopen(request, timeout=2)
        self.assertEqual(caught.exception.code, 403)
        payload = json.loads(caught.exception.read().decode("utf-8"))
        self.assertEqual(payload["status"], "permission_denied")


if __name__ == "__main__":
    unittest.main()
