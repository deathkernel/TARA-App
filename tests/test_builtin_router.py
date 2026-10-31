from __future__ import annotations

import unittest

from tara_app.builtin_router import BuiltinRouter


class BuiltinRouterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.router = BuiltinRouter()
        self.capabilities = ["chat.respond", "chat.audit_repository", "code.plan", "research.answer", "security.assess"]

    def route(self, question: str, attachments=()):
        return self.router.route({
            "schema_version": "1.0",
            "request_id": "route-1",
            "question": question,
            "available_capabilities": self.capabilities,
            "attachments": list(attachments),
        })

    def test_general_question_uses_chat(self):
        decision = self.route("Hello, explain this simply")
        self.assertEqual((decision.status, decision.module, decision.action), ("routed", "chat", "respond"))

    def test_explicit_repository_audit_uses_local_chat_auditor(self):
        decision = self.route("Audit this repository")
        self.assertEqual((decision.status, decision.module, decision.action), ("routed", "chat", "audit_repository"))
        self.assertEqual(decision.reason_code, "repository_audit")

    def test_repository_audit_does_not_override_side_effect_gate(self):
        decision = self.route("Audit this repository and run all tests")
        self.assertEqual((decision.module, decision.action), ("security", "assess"))
        self.assertTrue(decision.requires_approval)

    def test_repository_audit_fails_closed_when_capability_is_disabled(self):
        self.capabilities.remove("chat.audit_repository")
        decision = self.route("Check this project")
        self.assertEqual(decision.status, "unavailable")
        self.assertEqual(decision.intended_module, "chat")
        self.assertEqual(decision.intended_action, "audit_repository")

    def test_coding_question_uses_code_specialist(self):
        decision = self.route("Help me debug this Python function")
        self.assertEqual((decision.module, decision.action), ("code", "plan"))

    def test_current_research_uses_public_research_specialist(self):
        decision = self.route("Find current sources about solar energy")
        self.assertEqual((decision.module, decision.action), ("research", "answer"))

    def test_image_attachment_prefers_vision(self):
        self.capabilities.append("vision.analyze")
        decision = self.route("What is shown?", [{"name": "photo.png", "media_type": "image/png"}])
        self.assertEqual((decision.module, decision.action), ("vision", "analyze"))
        self.assertEqual(decision.status, "routed")

    def test_side_effect_needs_security_gate(self):
        decision = self.route("Create a GitHub issue")
        self.assertEqual((decision.module, decision.action), ("security", "assess"))
        self.assertTrue(decision.requires_approval)
        self.assertEqual((decision.intended_module, decision.intended_action), ("action", "execute"))

    def test_missing_capability_fails_closed(self):
        decision = self.router.route({
            "request_id": "route-2",
            "question": "Find sources about the topic",
            "available_capabilities": ["chat.respond"],
            "attachments": [],
        })
        self.assertEqual(decision.status, "unavailable")
        self.assertEqual(decision.intended_module, "research")

    def test_invalid_request_is_rejected(self):
        decision = self.router.route({"request_id": "route-3", "question": "", "available_capabilities": []})
        self.assertEqual(decision.status, "invalid_request")

    def test_invalid_website_port_is_rejected_before_approval(self):
        self.capabilities.append("action.execute")
        decision = self.route("Open https://example.com:99999/path")
        self.assertEqual(decision.status, "invalid_request")
        self.assertEqual(decision.reason_code, "invalid_website_url")
        self.assertFalse(decision.requires_approval)

    def test_oversized_website_url_is_rejected_before_approval(self):
        self.capabilities.append("action.execute")
        decision = self.route("Open https://example.com/" + "a" * 2050)
        self.assertEqual(decision.status, "invalid_request")
        self.assertEqual(decision.reason_code, "invalid_website_url")

    def test_valid_website_still_requires_security_approval(self):
        self.capabilities.append("action.execute")
        decision = self.route("Open https://example.com/search?q=why?")
        self.assertEqual((decision.module, decision.action), ("security", "assess"))
        self.assertTrue(decision.requires_approval)


if __name__ == "__main__":
    unittest.main()
