"""Regression tests for OmniRoute-backed Model Hub dispatch."""
import unittest

from tara_app.contracts import AdapterHealth, Capability, ModuleResult, RouteDecision
from tara_app.orchestrator import Orchestrator
from tara_app.registry import CapabilityRegistry


class FakeAdapter:
    module_id = "models"
    capabilities = (Capability("models", "catalog", "OmniRoute model catalogue", True),)

    def __init__(self):
        self.calls = []

    def health(self):
        return AdapterHealth("healthy")

    def execute(self, request):
        self.calls.append(request)
        return ModuleResult("success", {
            "text": "# OmniRoute Model Hub\n\n- provider/model-a",
            "provider": "omniroute",
            "remote_data_transfer": True,
        })


class FakeRouter:
    def route(self, payload):
        return RouteDecision(
            request_id=payload["request_id"],
            status="unavailable",
            module=None,
            action=None,
            reason_code="capability_unavailable",
            reason="The models specialist is not installed or enabled.",
            intended_module="models",
            intended_action="catalog",
        )


class ModelHubResponseTests(unittest.TestCase):
    def test_catalog_is_dispatched_to_the_omniroute_module(self):
        adapter = FakeAdapter()
        registry = CapabilityRegistry()
        registry.register(adapter)
        app = Orchestrator(registry, FakeRouter(), model_catalog=None)
        result = app.handle_question("List all available models", request_id="models-1")
        self.assertEqual(result.status, "success")
        self.assertEqual(result.route.module, "models")
        self.assertEqual(result.route.action, "catalog")
        self.assertIn("# OmniRoute Model Hub", result.result.data["text"])
        self.assertEqual(result.result.data["provider"], "omniroute")
        self.assertTrue(result.result.data["remote_data_transfer"])
        self.assertEqual(len(adapter.calls), 1)


if __name__ == "__main__":
    unittest.main()
