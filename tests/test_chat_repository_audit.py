from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tara_chat.__main__ import _run_repository_audit_command, chat_loop
from tara_chat.repository_audit import AuditIssue, AuditReport


def report_with(*issues: AuditIssue) -> AuditReport:
    return AuditReport(
        files_scanned=18,
        python_files=16,
        workflow_files=2,
        issues=tuple(issues),
        fingerprint="a" * 64,
    )


class RepositoryAuditCommandTests(unittest.TestCase):
    def test_audit_defaults_to_current_directory_and_reports_summary(self):
        with patch("tara_chat.repository_audit.RepositoryAuditor") as auditor:
            auditor.return_value.audit.return_value = report_with()
            result = _run_repository_audit_command("/audit")

        self.assertIn("Repository audit: HEALTHY", result)
        self.assertIn("Files scanned: 18", result)
        auditor.assert_called_once_with(Path.cwd().resolve())

    def test_audit_displays_bounded_findings_and_severity(self):
        issue = AuditIssue("PYTHON_SYNTAX", "src/broken.py", "invalid syntax")
        with patch("tara_chat.repository_audit.RepositoryAuditor") as auditor:
            auditor.return_value.audit.return_value = report_with(issue)
            result = _run_repository_audit_command("/audit")

        self.assertIn("Repository audit: ISSUES FOUND", result)
        self.assertIn("ERROR PYTHON_SYNTAX src/broken.py", result)

    def test_audit_rejects_absolute_paths_and_parent_traversal(self):
        with patch("tara_chat.repository_audit.RepositoryAuditor") as auditor:
            absolute = _run_repository_audit_command("/audit C:/Windows")
            traversal = _run_repository_audit_command("/audit ..")

        self.assertIn("relative folder", absolute)
        self.assertIn("inside the current working directory", traversal)
        auditor.assert_not_called()

    def test_audit_supports_quoted_relative_folder_names(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            target = workspace / "sample project"
            target.mkdir()
            with patch("pathlib.Path.cwd", return_value=workspace):
                with patch("tara_chat.repository_audit.RepositoryAuditor") as auditor:
                    auditor.return_value.audit.return_value = report_with()
                    result = _run_repository_audit_command('/audit "sample project"')

            self.assertIn("Repository audit: HEALTHY", result)
            auditor.assert_called_once_with(target.resolve())

    def test_chat_loop_handles_audit_without_calling_the_model(self):
        class NoModelBrain:
            llm_provider = None

            def respond(self, *args, **kwargs):
                raise AssertionError("audit command must not call the model")

        commands = iter(["/audit", "/exit"])
        output = []
        with patch("tara_chat.repository_audit.RepositoryAuditor") as auditor:
            auditor.return_value.audit.return_value = report_with()
            chat_loop(NoModelBrain(), input_fn=lambda _: next(commands), output_fn=output.append)

        self.assertTrue(any("Repository audit: HEALTHY" in line for line in output))


if __name__ == "__main__":
    unittest.main()
