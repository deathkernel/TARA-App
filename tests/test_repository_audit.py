from __future__ import annotations

import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from tara_chat.repository_audit import RepositoryAuditor


class RepositoryAuditorTests(unittest.TestCase):
    def make_repo(self, root: Path) -> None:
        for relative in RepositoryAuditor.REQUIRED_FILES:
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("# fixture\n", encoding="utf-8")

    def create_symlink_or_skip(self, link: Path, target: Path) -> None:
        try:
            link.symlink_to(target)
        except (OSError, NotImplementedError) as exc:
            self.skipTest(f"symlinks are unavailable in this environment: {exc}")

    def test_current_repository_checkout_has_no_missing_required_paths(self):
        repository_root = Path(__file__).resolve().parents[1]
        report = RepositoryAuditor(repository_root).audit()
        missing = [
            issue.path for issue in report.issues
            if issue.code == "MISSING_REQUIRED_FILE"
        ]
        self.assertEqual(missing, [])

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

    def test_external_python_symlink_is_not_scanned(self):
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as outside:
            root = Path(directory)
            self.make_repo(root)
            external = Path(outside) / "outside.py"
            external.write_text("def broken(:\n", encoding="utf-8")
            link = root / "src/tara_chat/external.py"
            self.create_symlink_or_skip(link, external)

            report = RepositoryAuditor(root).audit()

            self.assertNotIn(link, list(RepositoryAuditor(root)._python_files()))
            self.assertFalse(any(issue.path == "src/tara_chat/external.py" for issue in report.issues))

    def test_external_symlink_does_not_satisfy_required_file(self):
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as outside:
            root = Path(directory)
            self.make_repo(root)
            required = root / "src/tara_chat/brain.py"
            required.unlink()
            external = Path(outside) / "brain.py"
            external.write_text("# outside fixture\n", encoding="utf-8")
            self.create_symlink_or_skip(required, external)

            report = RepositoryAuditor(root).audit()

            missing = [issue.path for issue in report.issues if issue.code == "MISSING_REQUIRED_FILE"]
            self.assertIn("src/tara_chat/brain.py", missing)

    def test_external_workflow_symlink_is_not_counted_or_read(self):
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as outside:
            root = Path(directory)
            self.make_repo(root)
            external = Path(outside) / "external.yml"
            external.write_text("python -m pytest\n", encoding="utf-8")
            link = root / ".github/workflows/external.yml"
            self.create_symlink_or_skip(link, external)

            report = RepositoryAuditor(root).audit()

            self.assertEqual(report.workflow_files, 1)
            self.assertFalse(any(issue.code == "DUPLICATE_PYTEST_WORKFLOWS" for issue in report.issues))

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

    def test_generated_directories_are_pruned_before_traversal(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_repo(root)
            (root / "root.py").write_text("# root\n", encoding="utf-8")
            (root / "src/app.py").write_text("# app\n", encoding="utf-8")
            auditor = RepositoryAuditor(root)
            root_directories = [".git", "node_modules", "src", "build"]

            def walk(*args, **kwargs):
                yield str(root), root_directories, ["root.py"]
                yield str(root / "src"), [], ["app.py"]

            with patch("tara_chat.repository_audit.os.walk", side_effect=walk):
                paths = list(auditor._python_files())

            self.assertEqual(root_directories, ["src"])
            self.assertEqual([path.name for path in paths], ["root.py", "app.py"])

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
