from __future__ import annotations

import base64
import os
import unittest
from unittest.mock import patch

from tara_code.__main__ import _ollama_origin, _read_attachments, handle_request as handle_code
from tara_chat.app_adapter import handle_request as handle_chat
from tara_research.__main__ import _crossref, _wikipedia, handle_request as handle_research


class CodeSpecialistTests(unittest.TestCase):

    def test_chat_app_adapter_uses_injected_local_provider_and_session_history(self):
        class FakeProvider:
            def __init__(self):
                self.prompt = None

            def complete(self, prompt, **kwargs):
                self.prompt = prompt
                return "The answer is four."

        provider = FakeProvider()
        request = {
            "schema_version": "1.0",
            "request_id": "chat-adapter-1",
            "session_id": "session-1",
            "module": "chat",
            "action": "respond",
            "inputs": {
                "question": "What is 2 + 2?",
                "history": [{"role": "user", "content": "Hi TARA"}],
            },
        }
        with patch.dict(os.environ, {"TARA_CHAT_MEMORY_PATH": ""}), patch(
            "tara_chat.app_adapter.provider_from_env", return_value=provider
        ):
            result = handle_chat(request)
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["request_id"], "chat-adapter-1")
        self.assertEqual(result["data"]["text"], "The answer is four.")
        self.assertIn("User: Hi TARA", provider.prompt)
        self.assertIn("User: What is 2 + 2?", provider.prompt)

    def test_code_plan_uses_only_the_configured_loopback_ollama_endpoint(self):
        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return None

            def read(self, _limit):
                return b'{"message":{"content":"Review complete."}}'

        class FakeOpener:
            def __init__(self):
                self.request = None

            def open(self, request, timeout):
                self.request = request
                self.timeout = timeout
                return FakeResponse()

        opener = FakeOpener()
        source = base64.b64encode(b"print('safe')").decode("ascii")
        request = {
            "schema_version": "1.0",
            "request_id": "code-plan-1",
            "module": "code",
            "action": "plan",
            "inputs": {
                "question": "Review this code",
                "attachments": [{"name": "example.py", "content_base64": source}],
            },
        }
        with patch.dict(os.environ, {
            "TARA_CODE_OLLAMA_URL": "http://127.0.0.1:11434",
            "TARA_CODE_MODEL": "qwen2.5-coder:3b",
        }), patch("tara_code.__main__.build_opener", return_value=opener):
            result = handle_code(request)
        self.assertEqual(result["status"], "success")
        self.assertFalse(result["data"]["execution_performed"])
        self.assertEqual(result["data"]["text"], "Review complete.")
        self.assertEqual(opener.request.full_url, "http://127.0.0.1:11434/api/chat")
        self.assertEqual(opener.timeout, 180)

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
