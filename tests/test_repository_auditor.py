from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tara_chat.repository_audit import RepositoryAuditor


class RepositoryAuditorTests(unittest.TestCase):
    def _make_repository(self, root: Path) -> None:
        required = (
            "pyproject.toml",
            "src/tara_app/__init__.py",
            "src/tara_app/cli.py",
            "src/tara_chat/__init__.py",
            "src/tara_chat/brain.py",
            "src/tara_chat/ollama_provider.py",
            "src/tara_chat/memory.py",
            "tests/test_app_core.py",
            ".github/workflows/ci.yml",
        )
        for relative in required:
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("# valid\\n", encoding="utf-8")

    def test_current_monorepo_layout_is_recognized(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self._make_repository(root)

            report = RepositoryAuditor(root).audit()

            self.assertTrue(report.healthy)
            self.assertEqual(report.issues, ())
            self.assertGreaterEqual(report.python_files, 7)
            self.assertEqual(report.workflow_files, 1)

    def test_python_syntax_errors_are_reported(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self._make_repository(root)
            broken = root / "src" / "tara_chat" / "broken.py"
            broken.write_text("def broken(:\\n", encoding="utf-8")

            report = RepositoryAuditor(root).audit()

            self.assertFalse(report.healthy)
            self.assertTrue(any(
                issue.code == "PYTHON_SYNTAX" and issue.path == "src/tara_chat/broken.py"
                for issue in report.issues
            ))

    def test_generated_and_dependency_directories_are_pruned(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self._make_repository(root)
            generated = root / "node_modules" / "package" / "bad.py"
            generated.parent.mkdir(parents=True)
            generated.write_text("def broken(:\\n", encoding="utf-8")
            virtualenv = root / ".venv" / "Lib" / "bad.py"
            virtualenv.parent.mkdir(parents=True)
            virtualenv.write_text("def broken(:\\n", encoding="utf-8")

            report = RepositoryAuditor(root).audit()

            self.assertTrue(report.healthy)
            self.assertFalse(any("node_modules" in issue.path or ".venv" in issue.path for issue in report.issues))

    def test_external_file_symlink_is_not_scanned_or_accepted_as_required(self):
        with tempfile.TemporaryDirectory() as temp, tempfile.TemporaryDirectory() as outside:
            root = Path(temp)
            self._make_repository(root)
            external = Path(outside) / "outside.py"
            external.write_text("def broken(:\\n", encoding="utf-8")
            link = root / "src" / "tara_chat" / "linked.py"
            try:
                link.symlink_to(external)
            except (OSError, NotImplementedError):
                self.skipTest("symlink creation is unavailable on this runner")

            report = RepositoryAuditor(root).audit()

            self.assertFalse(any(issue.path == "src/tara_chat/linked.py" for issue in report.issues))
            self.assertTrue(report.healthy)

    def test_duplicate_full_pytest_workflows_are_reported(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self._make_repository(root)
            second = root / ".github" / "workflows" / "tests.yml"
            second.write_text("run: python -m pytest\\n", encoding="utf-8")

            report = RepositoryAuditor(root).audit()

            self.assertTrue(any(issue.code == "DUPLICATE_PYTEST_WORKFLOWS" for issue in report.issues))


if __name__ == "__main__":
    unittest.main()
