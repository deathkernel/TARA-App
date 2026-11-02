from __future__ import annotations

import base64
import os
import unittest
from unittest.mock import patch

from tara_code.__main__ import (
    _omniroute_api_key,
    _omniroute_base_url,
    _read_attachments,
    handle_request as handle_code,
)
from tara_research.__main__ import _crossref, _wikipedia, handle_request as handle_research


class CodeSpecialistTests(unittest.TestCase):
    def test_code_rejects_non_loopback_gateway_endpoint(self):
        invalid_urls = (
            "https://example.com/v1",
            "http://example.com/v1",
            "http://127.0.0.1:20128/",
            "http://127.0.0.1:20128/v1?token=secret",
        )
        for url in invalid_urls:
            with self.subTest(url=url), patch.dict(os.environ, {"TARA_CODE_API_BASE_URL": url}):
                with self.assertRaises(ValueError):
                    _omniroute_base_url()

    def test_code_accepts_only_local_omniroute_v1_endpoint(self):
        with patch.dict(os.environ, {"TARA_CODE_API_BASE_URL": "http://localhost:20128/v1"}):
            self.assertEqual(_omniroute_base_url(), "http://localhost:20128/v1")

    def test_code_requires_a_bounded_non_empty_api_key(self):
        for key in ("", "   ", "bad key", "x" * 4097):
            with self.subTest(key_length=len(key)), patch.dict(os.environ, {"TARA_CODE_API_KEY": key}):
                with self.assertRaises(ValueError):
                    _omniroute_api_key()

        with patch.dict(os.environ, {"TARA_CODE_API_KEY": "local-test-key"}):
            self.assertEqual(_omniroute_api_key(), "local-test-key")

    def test_code_accepts_only_bounded_utf8_source_attachments(self):
        encoded = base64.b64encode(b"print('safe')").decode("ascii")
        source = _read_attachments([{"name": "example.py", "content_base64": encoded}])
        self.assertIn("print('safe')", source)
        with self.assertRaises(ValueError):
            _read_attachments([{"name": "passwords.txt", "content_base64": encoded}])

    def test_code_health_checks_the_omniroute_gateway_without_generating(self):
        environment = {
            "TARA_CODE_API_BASE_URL": "http://127.0.0.1:20128/v1",
            "TARA_CODE_API_KEY": "local-test-key",
        }
        with patch.dict(os.environ, environment), patch(
            "tara_code.__main__._check_gateway", return_value=True
        ) as check_gateway:
            result = handle_code({
                "schema_version": "1.0", "request_id": "code-health", "module": "code",
                "action": "health", "inputs": {},
            })

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["data"]["provider"], "omniroute")
        self.assertTrue(result["data"]["healthy"])
        check_gateway.assert_called_once_with(environment["TARA_CODE_API_BASE_URL"], environment["TARA_CODE_API_KEY"])

    def test_code_health_reports_unavailable_gateway(self):
        environment = {
            "TARA_CODE_API_BASE_URL": "http://127.0.0.1:20128/v1",
            "TARA_CODE_API_KEY": "local-test-key",
        }
        with patch.dict(os.environ, environment), patch(
            "tara_code.__main__._check_gateway", return_value=False
        ):
            result = handle_code({
                "schema_version": "1.0", "request_id": "code-health-down", "module": "code",
                "action": "health", "inputs": {},
            })

        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["error"], "OmniRoute gateway is unavailable")


class FreeResearchTests(unittest.TestCase):
    def test_crossref_results_include_a_direct_doi_link(self):
        payload = {"message": {"items": [{
            "title": ["Open research result"], "DOI": "10.1234/example",
            "author": [{"family": "Researcher"}],
            "published-print": {"date-parts": [[2025, 1, 1]]},
        }]}}
        with patch("tara_research.__main__._get_json", return_value=payload):
            items = _crossref("open research")
        self.assertEqual(items[0]["url"], "https://doi.org/10.1234/example")
        self.assertEqual(items[0]["author"], "Researcher")
        self.assertEqual(items[0]["year"], "2025")

    def test_wikipedia_search_snippet_is_plain_text(self):
        payload = {"query": {"search": [{
            "title": "Example topic",
            "snippet": "A <span class=\\"searchmatch\\">plain</span> result",
        }]}}
        with patch("tara_research.__main__._get_json", return_value=payload):
            items = _wikipedia("example topic")
        self.assertEqual(items[0]["snippet"], "A plain result")

    def test_research_returns_public_source_links_without_an_llm(self):
        with patch("tara_research.__main__._crossref", return_value=[
            {"title": "Paper title", "source": "Crossref", "url": "https://doi.org/10.1234/paper"}
        ]), patch("tara_research.__main__._wikipedia", return_value=[]):
            result = handle_research({
                "schema_version": "1.0", "request_id": "research-1",
                "module": "research", "action": "answer",
                "inputs": {"question": "public health research"},
            })
        self.assertEqual(result["status"], "success")
        self.assertFalse(result["data"]["paid_model_used"])
        self.assertIn("https://doi.org/10.1234/paper", result["data"]["text"])

    def test_research_rejects_an_empty_query(self):
        result = handle_research({
            "schema_version": "1.0", "request_id": "research-2",
            "module": "research", "action": "answer", "inputs": {"question": " "},
        })
        self.assertEqual(result["status"], "invalid_request")


if __name__ == "__main__":
    unittest.main()
