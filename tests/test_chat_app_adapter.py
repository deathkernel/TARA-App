from __future__ import annotations

import unittest
from unittest.mock import patch

from tara_chat.app_adapter import CAPABILITIES, handle_request
from tara_chat.repository_audit import AuditIssue, AuditReport


def request(**overrides):
    payload = {
        "schema_version": "1.0",
        "request_id": "audit-1",
        "module": "chat",
        "action": "audit_repository",
        "inputs": {"question": "Audit this repository", "attachments": []},
    }
    payload.update(overrides)
    return payload


class ChatRepositoryAuditAdapterTests(unittest.TestCase):
    def test_audit_capability_is_declared(self):
        self.assertIn("audit_repository", CAPABILITIES)

    def test_repository_audit_is_local_and_does_not_initialize_a_model(self):
        report = AuditReport(
            files_scanned=12,
            python_files=10,
            workflow_files=2,
            issues=(AuditIssue("PYTHON_SYNTAX", "src/broken.py", "invalid syntax"),),
            fingerprint="b" * 64,
        )
        with patch("tara_chat.repository_audit.RepositoryAuditor") as auditor, patch(
            "tara_chat.app_adapter.provider_from_env",
            side_effect=AssertionError("repository audit must not initialize a model"),
        ):
            auditor.return_value.audit.return_value = report
            result = handle_request(request())

        self.assertEqual(result["status"], "success")
        self.assertIn("Repository audit: ISSUES FOUND", result["data"]["text"])
        self.assertEqual(result["data"]["files_scanned"], 12)
        self.assertFalse(result["data"]["remote_data_transfer"])
        auditor.assert_called_once()

    def test_repository_audit_rejects_attached_files(self):
        payload = request(inputs={"question": "Audit this repository", "attachments": [{"name": "source.py"}]})
        result = handle_request(payload)
        self.assertEqual(result["status"], "invalid_request")
        self.assertIn("does not accept attachments", result["error"])

    def test_repository_audit_rejects_empty_question(self):
        payload = request(inputs={"question": " ", "attachments": []})
        result = handle_request(payload)
        self.assertEqual(result["status"], "invalid_request")

    def test_unknown_chat_action_remains_denied(self):
        result = handle_request(request(action="execute_shell"))
        self.assertEqual(result["status"], "permission_denied")


if __name__ == "__main__":
    unittest.main()
