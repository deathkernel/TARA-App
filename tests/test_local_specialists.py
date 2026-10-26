from __future__ import annotations

import base64
import os
import unittest
from unittest.mock import patch

from tara_code.__main__ import _ollama_origin, _read_attachments, handle_request as handle_code
from tara_research.__main__ import _crossref, _wikipedia, handle_request as handle_research


class CodeSpecialistTests(unittest.TestCase):
    def test_code_rejects_non_loopback_model_endpoint(self):
        with patch.dict(os.environ, {"TARA_CODE_OLLAMA_URL": "https://example.com"}):
            with self.assertRaises(ValueError):
                _ollama_origin()

    def test_code_accepts_only_bounded_utf8_source_attachments(self):
        encoded = base64.b64encode(b"print('safe')").decode("ascii")
        source = _read_attachments([{"name": "example.py", "content_base64": encoded}])
        self.assertIn("print('safe')", source)
        with self.assertRaises(ValueError):
            _read_attachments([{"name": "passwords.txt", "content_base64": encoded}])

    def test_code_health_does_not_call_a_model(self):
        result = handle_code({
            "schema_version": "1.0", "request_id": "code-health", "module": "code",
            "action": "health", "inputs": {},
        })
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["data"]["provider"], "ollama")


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
            "snippet": "A <span class=\"searchmatch\">plain</span> result",
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
