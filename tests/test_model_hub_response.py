"""Regression tests for the local Free Model Hub response."""
import unittest

from tara_app.contracts import RouteDecision
from tara_app.orchestrator import Orchestrator
from tara_app.registry import CapabilityRegistry


class FakeCatalog:
    def status(self):
        return {"models": [
            {"specialist": "chat", "model": "llama3.2:3b", "installed": True},
            {"specialist": "creative", "model": "llama3.2:3b", "installed": True},
            {"specialist": "code", "model": "qwen2.5-coder:3b", "installed": True},
            {"specialist": "vision", "model": "gemma3:4b", "installed": True},
        ]}


class FakeRouter:
    def route(self, payload):
        return RouteDecision(
            request_id=payload["request_id"], status="unavailable",
            module=None, action=None, reason_code="catalog_request",
            reason="Local model catalog request.",
            intended_module="models", intended_action="catalog",
        )


class ModelHubResponseTests(unittest.TestCase):
    def test_catalog_has_markdown_newlines_and_installed_model_names(self):
        app = Orchestrator(CapabilityRegistry(), FakeRouter(), model_catalog=FakeCatalog())
        result = app.handle_question("List all available free models")
        self.assertEqual(result.status, "success")
        text = result.result.data["text"]
        self.assertIn("# Free Model Hub\n\n## Gemini free-tier candidates", text)
        self.assertIn("## Models installed on this device\n- gemma3:4b", text)
        self.assertIn("- llama3.2:3b", text)
        self.assertIn("- qwen2.5-coder:3b", text)
        self.assertNotIn("\\n", text)
        self.assertNotIn("- unknown", text)
        self.assertEqual(text.count("- llama3.2:3b"), 1)


if __name__ == "__main__":
    unittest.main()
