from __future__ import annotations

import threading
import unittest

from tara_app.application.facade import ApplicationFacade
from tara_app.contracts import AdapterHealth, Capability, ModuleResult
from tara_app.registry import CapabilityRegistry


class FakeAdapter:
    module_id = "models"
    capabilities = (Capability("models", "catalog", "Model catalogue", True),)
    timeout_seconds = 8

    def __init__(self, result: ModuleResult, health: AdapterHealth | None = None):
        self.result = result
        self.health_result = health or AdapterHealth("healthy")

    def health(self):
        return self.health_result

    def execute(self, request):
        self.request = request
        return self.result


class FakeCoordinator:
    def __init__(self, registry=None):
        self.registry = registry or CapabilityRegistry()
        self.model_catalog = None
        self.history = None

    def replace_conversation_history(self, session_id, history):
        self.history = (session_id, history)

    def handle_question(self, question, **kwargs):
        return (question, kwargs)

    def approve(self, approval_id, *, session_id):
        return (approval_id, session_id)

    def cancel_approval(self, approval_id, *, session_id):
        return (approval_id, session_id, "cancelled")

    def mcp_status(self):
        return {"status": "disabled"}

    def list_mcp_tools(self, server_name=None):
        return []

    def issue_mcp_approval_token(self, server, tool, arguments, *, session_id):
        return "approval-token"

    def call_mcp_tool(self, server, tool, arguments, *, approval_token, session_id):
        return "tool-result"


class FakeModelCatalogue:
    profiles = {"chat": object()}

    def __init__(self):
        self.calls = []

    def ensure_service_started(self):
        self.calls.append("start")

    def ensure_model_installed(self, specialist):
        self.calls.append(("install", specialist))

    def preload_model(self, specialist, *, keep_alive):
        self.calls.append(("preload", specialist, keep_alive))

    def close(self):
        self.calls.append("close")


class ApplicationFacadeTests(unittest.TestCase):
    def test_health_status_exposes_diagnostics_without_registry_access(self):
        coordinator = FakeCoordinator()
        app = ApplicationFacade(coordinator)

        payload = app.health_status()

        self.assertEqual(payload["app"], "TARA-App")
        self.assertEqual(payload["status"], "degraded")
        self.assertEqual(payload["capabilities"], [])
        self.assertEqual(payload["model_runtime"], "omniroute")

    def test_health_status_checks_each_registered_specialist_independently(self):
        registry = CapabilityRegistry()
        adapters = {}
        for module_id, health in (
            ("chat", AdapterHealth("healthy")),
            ("code", AdapterHealth("degraded", "coding route is not configured")),
            ("vision", AdapterHealth("unavailable", "vision route is unavailable")),
            ("creative", AdapterHealth("healthy")),
            ("models", AdapterHealth("healthy")),
        ):
            adapter = FakeAdapter(
                ModuleResult("success", {}),
                health=health,
            )
            adapter.module_id = module_id
            adapter.capabilities = (Capability(module_id, "check", f"{module_id} check", True),)
            registry.register(adapter)
            adapters[module_id] = adapter

        payload = ApplicationFacade(FakeCoordinator(registry)).health_status()

        self.assertEqual(payload["specialists"]["chat"]["status"], "healthy")
        self.assertEqual(payload["specialists"]["code"]["status"], "degraded")
        self.assertEqual(payload["specialists"]["code"]["reason"], "coding route is not configured")
        self.assertEqual(payload["specialists"]["vision"]["status"], "unavailable")
        self.assertEqual(payload["specialists"]["vision"]["reason"], "vision route is unavailable")
        self.assertEqual(payload["specialists"]["creative"]["status"], "healthy")
        self.assertEqual(payload["specialists"]["models"]["status"], "healthy")
        self.assertEqual(payload["model_gateway"]["status"], "healthy")
        self.assertEqual(payload["status"], "degraded")

    def test_health_status_does_not_hide_specialist_health_exceptions(self):
        class BrokenHealthAdapter(FakeAdapter):
            def health(self):
                raise RuntimeError("private endpoint details must not leak")

        registry = CapabilityRegistry()
        adapter = BrokenHealthAdapter(ModuleResult("success", {}))
        adapter.module_id = "code"
        adapter.capabilities = (Capability("code", "check", "code check", True),)
        registry.register(adapter)

        payload = ApplicationFacade(FakeCoordinator(registry)).health_status()

        self.assertEqual(payload["specialists"]["code"]["status"], "unavailable")
        self.assertEqual(payload["specialists"]["code"]["reason"], "specialist health check failed")

    def test_invalid_health_payload_fails_closed(self):
        class InvalidHealthAdapter(FakeAdapter):
            def health(self):
                return {"status": "healthy"}

        registry = CapabilityRegistry()
        adapter = InvalidHealthAdapter(ModuleResult("success", {}))
        adapter.module_id = "code"
        adapter.capabilities = (Capability("code", "check", "code check", True),)
        registry.register(adapter)

        payload = ApplicationFacade(FakeCoordinator(registry)).health_status()

        self.assertEqual(payload["specialists"]["code"]["status"], "unavailable")
        self.assertEqual(payload["specialists"]["code"]["reason"], "specialist returned an invalid health response")

    def test_health_status_degrades_when_only_unlisted_specialists_are_registered(self):
        registry = CapabilityRegistry()
        adapter = FakeAdapter(ModuleResult("success", {}))
        adapter.module_id = "planner"
        adapter.capabilities = (Capability("planner", "plan", "Planning", True),)
        registry.register(adapter)

        payload = ApplicationFacade(FakeCoordinator(registry)).health_status()

        self.assertEqual(payload["capability_count"], 1)
        self.assertEqual(payload["status"], "degraded")

    def test_health_status_checks_registered_specialists_concurrently(self):
        barrier = threading.Barrier(2)

        class ConcurrentHealthAdapter(FakeAdapter):
            def health(self):
                barrier.wait(timeout=1)
                return AdapterHealth("healthy")

        registry = CapabilityRegistry()
        for module_id in ("chat", "code"):
            adapter = ConcurrentHealthAdapter(ModuleResult("success", {}))
            adapter.module_id = module_id
            adapter.capabilities = (Capability(module_id, "check", f"{module_id} check", True),)
            registry.register(adapter)

        payload = ApplicationFacade(FakeCoordinator(registry)).health_status()

        self.assertEqual(payload["specialists"]["chat"]["status"], "healthy")
        self.assertEqual(payload["specialists"]["code"]["status"], "healthy")
        self.assertEqual(payload["status"], "ok")

    def test_model_catalogue_uses_registered_operation(self):
        registry = CapabilityRegistry()
        adapter = FakeAdapter(ModuleResult("success", {"models": [{"id": "auto"}]}))
        registry.register(adapter)
        app = ApplicationFacade(FakeCoordinator(registry))

        payload = app.model_catalogue()

        self.assertEqual(payload["status"], "available")
        self.assertEqual(payload["models"], [{"id": "auto"}])
        self.assertEqual(adapter.request.module, "models")
        self.assertEqual(adapter.request.action, "catalog")
        self.assertEqual(adapter.request.timeout_seconds, 8)

    def test_model_lifecycle_stays_disabled_when_gateway_owns_lifecycle(self):
        app = ApplicationFacade(FakeCoordinator())

        self.assertIsNone(app.model_lifecycle_action("pull", "chat"))

    def test_optional_model_catalogue_startup_and_cleanup_are_preserved(self):
        coordinator = FakeCoordinator()
        coordinator.model_catalog = FakeModelCatalogue()
        app = ApplicationFacade(coordinator)

        self.assertIsNone(app.prepare_runtime())
        app.close()

        self.assertEqual(
            coordinator.model_catalog.calls,
            ["start", ("install", "chat"), ("preload", "chat", "15m"), "close"],
        )

    def test_runtime_lifecycle_is_a_noop_without_local_catalogue(self):
        app = ApplicationFacade(FakeCoordinator())

        self.assertIsNone(app.prepare_runtime())
        app.close()

    def test_interface_calls_are_forwarded_through_facade(self):
        coordinator = FakeCoordinator()
        app = ApplicationFacade(coordinator)

        app.replace_conversation_history("session-1", [{"role": "user", "content": "hello"}])
        self.assertEqual(coordinator.history[0], "session-1")
        self.assertEqual(app.handle_question("hello", session_id="session-1")[0], "hello")
        self.assertEqual(app.approve("approval-1", session_id="session-1"), ("approval-1", "session-1"))
        self.assertEqual(app.cancel_approval("approval-1", session_id="session-1")[2], "cancelled")
        self.assertEqual(app.mcp_status(), {"status": "disabled"})
        self.assertEqual(app.list_mcp_tools(), [])
        self.assertEqual(
            app.issue_mcp_approval_token("time", "now", {}, session_id="session-1"),
            "approval-token",
        )
        self.assertEqual(
            app.call_mcp_tool("time", "now", {}, approval_token="approval-token", session_id="session-1"),
            "tool-result",
        )


if __name__ == "__main__":
    unittest.main()
