from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tara_chat.repository_audit import RepositoryAuditor


class RepositoryAuditorTests(unittest.TestCase):
    def make_repo(self, root: Path) -> None:
        for relative in RepositoryAuditor.REQUIRED_FILES:
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("# fixture\n", encoding="utf-8")

    def test_current_monorepo_required_paths_are_accepted(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_repo(root)
            report = RepositoryAuditor(root).audit()
            self.assertTrue(report.healthy)
            self.assertFalse(any(issue.code == "MISSING_REQUIRED_FILE" for issue in report.issues))

    def test_missing_current_monorepo_file_is_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_repo(root)
            (root / "src/tara_chat/brain.py").unlink()
            report = RepositoryAuditor(root).audit()
            missing = [issue.path for issue in report.issues if issue.code == "MISSING_REQUIRED_FILE"]
            self.assertEqual(missing, ["src/tara_chat/brain.py"])

    def test_generated_and_dependency_directories_are_excluded(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_repo(root)
            ignored = [
                root / ".venv/lib/hidden.py",
                root / "venv/lib/hidden.py",
                root / "__pycache__/hidden.py",
                root / "build/generated.py",
                root / "node_modules/package/index.py",
                root / "dist/generated.py",
            ]
            for path in ignored:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("def ok(): return True\n", encoding="utf-8")
            report = RepositoryAuditor(root).audit()
            self.assertEqual(report.python_files, 7)

    def test_auditor_reports_python_syntax_errors(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_repo(root)
            source = root / "src/tara_chat/broken.py"
            source.write_text("def broken(:\n", encoding="utf-8")
            report = RepositoryAuditor(root).audit()
            self.assertTrue(any(issue.code == "PYTHON_SYNTAX" and issue.path == "src/tara_chat/broken.py" for issue in report.issues))

    def test_auditor_fingerprint_is_stable_for_the_same_findings(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_repo(root)
            source = root / "src/tara_chat/broken.py"
            source.write_text("def broken(:\n", encoding="utf-8")
            first = RepositoryAuditor(root).audit()
            second = RepositoryAuditor(root).audit()
            self.assertEqual(first.fingerprint, second.fingerprint)


if __name__ == "__main__":
    unittest.main()
