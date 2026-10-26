from __future__ import annotations

import unittest
from typing import Mapping, Sequence

from tara_app.contracts import AdapterHealth, Capability, ModuleRequest, ModuleResult, RouteDecision
from tara_app.orchestrator import Orchestrator
from tara_app.registry import CapabilityRegistry, RegistryError


class FakeAdapter:
    def __init__(self, module_id: str, capabilities: Sequence[Capability], result: ModuleResult | None = None):
        self.module_id = module_id
        self.capabilities = tuple(capabilities)
        self.result = result or ModuleResult("success", {"reply": "ok"})
        self.calls: list[ModuleRequest] = []
        self.health_state = AdapterHealth("healthy")

    def health(self) -> AdapterHealth:
        return self.health_state

    def execute(self, request: ModuleRequest) -> ModuleResult:
        self.calls.append(request)
        return self.result


class FakeRouter:
    def __init__(self, decision: RouteDecision):
        self.decision = decision
        self.payloads: list[Mapping[str, object]] = []

    def route(self, request_payload: dict[str, object]) -> RouteDecision:
        self.payloads.append(request_payload)
        return self.decision


class AppCoreTests(unittest.TestCase):
    def test_chat_history_is_session_scoped_and_bounded(self) -> None:
        chat = FakeAdapter(
            "chat",
            (Capability("chat", "respond", "Conversation response", True),),
            ModuleResult("success", {"text": "TARA reply"}),
        )
        registry = CapabilityRegistry()
        registry.register(chat)

        class SessionRouter:
            def route(self, payload):
                return RouteDecision(payload["request_id"], "routed", "chat", "respond", "conversation", "Chat intent")

        app = Orchestrator(registry, SessionRouter())
        for index in range(14):
            app.handle_question(f"Question {index}", session_id="session-a", request_id=f"req-{index}")
        app.handle_question("Separate session", session_id="session-b", request_id="req-other")
        history_a = chat.calls[-2].inputs["history"]
        history_b = chat.calls[-1].inputs["history"]
        self.assertEqual(len(history_a), 24)
        self.assertEqual(history_a[-2]["content"], "Question 12")
        self.assertEqual(history_a[-1]["content"], "TARA reply")
        self.assertEqual(history_b, [])

    def test_read_only_route_dispatches_to_its_own_adapter(self) -> None:
        chat = FakeAdapter("chat", (Capability("chat", "respond", "Conversation response", True),))
        registry = CapabilityRegistry()
        registry.register(chat)
        router = FakeRouter(RouteDecision("req-1", "routed", "chat", "respond", "conversation", "Chat intent"))
        result = Orchestrator(registry, router).handle_question("Hello", request_id="req-1")
        self.assertEqual(result.status, "success")
        self.assertEqual(len(chat.calls), 1)
        self.assertEqual(router.payloads[0]["available_capabilities"], ["chat.respond"])

    def test_side_effect_is_security_assessed_but_never_auto_executed(self) -> None:
        action = FakeAdapter("action", (Capability("action", "execute", "External action", False, True),))
        security = FakeAdapter(
            "security",
            (Capability("security", "assess", "Policy assessment", True),),
            ModuleResult("success", {"decision": "allow"}),
        )
        registry = CapabilityRegistry()
        registry.register(action)
        registry.register(security)
        decision = RouteDecision(
            "req-2", "routed", "security", "assess", "policy_review_required", "Approval needed",
            "action", "execute", True, ("side_effect", "human_approval"),
        )
        result = Orchestrator(registry, FakeRouter(decision)).handle_question("Send a report", request_id="req-2")
        self.assertEqual(result.status, "approval_required")
        self.assertEqual(len(security.calls), 1)
        self.assertEqual(len(action.calls), 0)

    def test_unavailable_route_does_not_fall_back_or_dispatch(self) -> None:
        chat = FakeAdapter("chat", (Capability("chat", "respond", "Conversation response", True),))
        registry = CapabilityRegistry()
        registry.register(chat)
        decision = RouteDecision("req-3", "unavailable", None, None, "capability_unavailable", "Research is unavailable", "research", "answer")
        result = Orchestrator(registry, FakeRouter(decision)).handle_question("Find sources", request_id="req-3")
        self.assertEqual(result.status, "unavailable")
        self.assertEqual(chat.calls, [])

    def test_non_read_only_capability_cannot_be_called_directly(self) -> None:
        action = FakeAdapter("action", (Capability("action", "execute", "External action", False, True),))
        registry = CapabilityRegistry()
        registry.register(action)
        decision = RouteDecision("req-4", "routed", "action", "execute", "action", "Action requested")
        result = Orchestrator(registry, FakeRouter(decision)).handle_question("Do it", request_id="req-4")
        self.assertEqual(result.status, "permission_denied")
        self.assertEqual(action.calls, [])

    def test_duplicate_capability_registration_is_rejected(self) -> None:
        registry = CapabilityRegistry()
        registry.register(FakeAdapter("chat", (Capability("chat", "respond", "Chat", True),)))
        with self.assertRaises(RegistryError):
            registry.register(FakeAdapter("chat", (Capability("chat", "respond", "Duplicate", True),)))

    def test_unhealthy_adapter_is_not_invoked(self) -> None:
        chat = FakeAdapter("chat", (Capability("chat", "respond", "Chat", True),))
        chat.health_state = AdapterHealth("unavailable")
        registry = CapabilityRegistry()
        registry.register(chat)
        decision = RouteDecision("req-5", "routed", "chat", "respond", "conversation", "Chat intent")
        result = Orchestrator(registry, FakeRouter(decision)).handle_question("Hi", request_id="req-5")
        self.assertEqual(result.status, "unavailable")
        self.assertEqual(chat.calls, [])

    def test_mismatched_router_request_id_is_rejected(self) -> None:
        chat = FakeAdapter("chat", (Capability("chat", "respond", "Chat", True),))
        registry = CapabilityRegistry()
        registry.register(chat)
        decision = RouteDecision("other", "routed", "chat", "respond", "conversation", "Chat intent")
        result = Orchestrator(registry, FakeRouter(decision)).handle_question("Hi", request_id="expected")
        self.assertEqual(result.status, "failed")
        self.assertEqual(chat.calls, [])


if __name__ == "__main__":
    unittest.main()

