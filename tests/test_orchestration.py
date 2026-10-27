"""Unit tests for the policy-gated capability orchestrator."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from tara_app.audit import JsonlAuditLog  # noqa: E402
from tara_app.orchestration import (  # noqa: E402
    CapabilityOrchestrator, CapabilityRequest, CapabilityUnavailable,
)
from tara_app.permissions import PermissionPolicy  # noqa: E402


class OrchestrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.audit_path = Path(self.temp.name) / "audit.jsonl"
        self.audit = JsonlAuditLog(self.audit_path)
        self.calls = []
        self.policy = PermissionPolicy.from_iterables(
            allowed_capabilities=["chat.reply", "code.apply_patch"],
            approval_required=["code.apply_patch"],
        )
        self.orchestrator = CapabilityOrchestrator(
            policy=self.policy,
            audit_log=self.audit,
            handlers={
                "chat.reply": lambda payload: self.calls.append(payload) or {"reply": "hello"},
                "code.apply_patch": lambda payload: self.calls.append(payload) or {"proposed": True},
            },
        )

    def test_allowed_request_dispatches_and_audits(self):
        response = self.orchestrator.dispatch(CapabilityRequest("chat.reply", {"text": "hello"}))
        self.assertEqual(response.status, "ok")
        self.assertEqual(response.result, {"reply": "hello"})
        records = [json.loads(line) for line in self.audit_path.read_text(encoding="utf-8").splitlines()]
        self.assertEqual([record["event_type"] for record in records], [
            "capability_policy_decision", "capability_completed"
        ])

    def test_denied_request_never_calls_handler(self):
        response = self.orchestrator.dispatch(CapabilityRequest("shell", {}))
        self.assertEqual(response.status, "permission_denied")
        self.assertEqual(self.calls, [])

    def test_approval_required_until_explicitly_approved(self):
        pending = self.orchestrator.dispatch(CapabilityRequest("code.apply_patch", {"diff": "x"}))
        self.assertEqual(pending.status, "approval_required")
        self.assertEqual(self.calls, [])
        approved = self.orchestrator.dispatch(CapabilityRequest("code.apply_patch", {"diff": "x"}, approved=True))
        self.assertEqual(approved.status, "ok")
        self.assertEqual(len(self.calls), 1)

    def test_missing_handler_is_unavailable(self):
        orchestrator = CapabilityOrchestrator(
            policy=PermissionPolicy.from_iterables(allowed_capabilities=["chat.reply"]),
            audit_log=self.audit,
        )
        self.assertEqual(orchestrator.dispatch(CapabilityRequest("chat.reply")).status, "unavailable")

    def test_bad_contract_version_is_rejected(self):
        with self.assertRaises(CapabilityUnavailable):
            self.orchestrator.dispatch(CapabilityRequest("chat.reply", contract_version=99))

    def test_handler_exception_is_normalized(self):
        orchestrator = CapabilityOrchestrator(
            policy=PermissionPolicy.from_iterables(allowed_capabilities=["chat.reply"]),
            audit_log=self.audit,
            handlers={"chat.reply": lambda payload: 1 / 0},
        )
        response = orchestrator.dispatch(CapabilityRequest("chat.reply"))
        self.assertEqual(response.status, "failed")
        self.assertNotIn("division", response.message)


if __name__ == "__main__":
    unittest.main()
