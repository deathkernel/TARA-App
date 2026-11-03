"""Tests for read-only proposed_changes diff preview formatting."""
from __future__ import annotations

import unittest

from tara_app.code_diff_preview import DiffPreviewError, format_proposed_changes_diff


class CodeDiffPreviewTests(unittest.TestCase):
    def test_empty_list_returns_empty_string(self) -> None:
        self.assertEqual(format_proposed_changes_diff([]), "")

    def test_modify_with_old_and_new_content(self) -> None:
        text = format_proposed_changes_diff(
            [
                {
                    "path": "src/hello.py",
                    "action": "modify",
                    "old_content": "print('a')\n",
                    "new_content": "print('b')\n",
                }
            ]
        )
        self.assertIn("--- a/src/hello.py", text)
        self.assertIn("+++ b/src/hello.py", text)
        self.assertIn("-print('a')", text)
        self.assertIn("+print('b')", text)

    def test_create_and_delete_use_dev_null_marker(self) -> None:
        create = format_proposed_changes_diff(
            [{"path": "new.txt", "action": "create", "new_content": "hi\n"}]
        )
        self.assertIn("--- /dev/null", create)
        self.assertIn("+++ b/new.txt", create)
        self.assertIn("+hi", create)
        self.assertIn("@@ -0,0 +1,1 @@", create)

        delete = format_proposed_changes_diff(
            [{"path": "gone.txt", "action": "delete", "old_content": "bye\n"}]
        )
        self.assertIn("--- a/gone.txt", delete)
        self.assertIn("+++ /dev/null", delete)
        self.assertIn("-bye", delete)
        self.assertIn("@@ -1,1 +0,0 @@", delete)

    def test_preformatted_diff_passthrough_without_content(self) -> None:
        raw = "--- a/x\n+++ b/x\n@@ -1 +1 @@\n-old\n+new\n"
        text = format_proposed_changes_diff([{"path": "x", "diff": raw}])
        self.assertEqual(text, raw)

    def test_content_sides_override_stale_diff(self) -> None:
        text = format_proposed_changes_diff(
            [
                {
                    "path": "x.py",
                    "action": "modify",
                    "diff": "--- a/x.py\n+++ b/x.py\n@@ -1 +1 @@\n-stale\n+stale\n",
                    "old_content": "old\n",
                    "new_content": "fresh\n",
                }
            ]
        )
        self.assertIn("-old", text)
        self.assertIn("+fresh", text)
        self.assertNotIn("stale", text)

    def test_non_string_diff_raises(self) -> None:
        with self.assertRaises(DiffPreviewError):
            format_proposed_changes_diff([{"path": "x", "diff": 123}])

    def test_rename_requires_from_path(self) -> None:
        with self.assertRaises(DiffPreviewError):
            format_proposed_changes_diff(
                [{"path": "new.py", "action": "rename", "new_content": "x\n"}]
            )
        text = format_proposed_changes_diff(
            [
                {
                    "path": "new.py",
                    "from_path": "old.py",
                    "action": "rename",
                    "old_content": "a\n",
                    "new_content": "b\n",
                }
            ]
        )
        self.assertIn("--- a/old.py", text)
        self.assertIn("+++ b/new.py", text)

    def test_rejects_parent_traversal_path(self) -> None:
        with self.assertRaises(DiffPreviewError):
            format_proposed_changes_diff(
                [{"path": "../secret", "action": "create", "new_content": "x"}]
            )

    def test_rejects_path_with_newline(self) -> None:
        with self.assertRaises(DiffPreviewError):
            format_proposed_changes_diff(
                [{"path": "safe.txt\n+++ b/other.txt", "action": "create", "new_content": "x"}]
            )

    def test_rejects_path_with_whitespace_edges(self) -> None:
        with self.assertRaises(DiffPreviewError):
            format_proposed_changes_diff(
                [{"path": "  spaced.txt  ", "action": "create", "new_content": "x"}]
            )

    def test_rejects_non_list(self) -> None:
        with self.assertRaises(DiffPreviewError):
            format_proposed_changes_diff("not-a-list")  # type: ignore[arg-type]

    def test_rejects_too_many_changes(self) -> None:
        changes = [{"path": f"f{i}.txt", "action": "create", "new_content": "x"} for i in range(65)]
        with self.assertRaises(DiffPreviewError):
            format_proposed_changes_diff(changes)


if __name__ == "__main__":
    unittest.main()
