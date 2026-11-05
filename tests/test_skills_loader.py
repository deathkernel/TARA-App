"""Tests for the allowlisted skill-pack loader."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tara_app.skills.loader import SkillLoadError, list_skill_packs, load_skill_pack


class SkillsLoaderTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        pack = self.root / "demo-skill"
        pack.mkdir()
        (pack / "SKILL.md").write_text("Do the thing carefully.\n", encoding="utf-8")
        (pack / "skill.toml").write_text(
            'title = "Demo"\ndescription = "A demo skill"\nversion = "1.0.0"\ntags = ["demo"]\n',
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_load_pack(self) -> None:
        pack = load_skill_pack("demo-skill", skills_root=self.root)
        self.assertEqual(pack.title, "Demo")
        self.assertIn("carefully", pack.instructions)
        self.assertIn("Skill: Demo", pack.prompt_block())

    def test_list_packs(self) -> None:
        packs = list_skill_packs(skills_root=self.root)
        self.assertEqual(len(packs), 1)
        self.assertEqual(packs[0].name, "demo-skill")

    def test_invalid_name_rejected(self) -> None:
        with self.assertRaises(SkillLoadError):
            load_skill_pack("../etc", skills_root=self.root)

    def test_missing_skill_md(self) -> None:
        empty = self.root / "empty-pack"
        empty.mkdir()
        with self.assertRaises(SkillLoadError):
            load_skill_pack("empty-pack", skills_root=self.root)

    def test_script_traversal_rejected(self) -> None:
        pack = self.root / "bad-scripts"
        pack.mkdir()
        (pack / "SKILL.md").write_text("x\n", encoding="utf-8")
        (pack / "skill.toml").write_text('scripts = ["../../evil.sh"]\n', encoding="utf-8")
        with self.assertRaises(SkillLoadError):
            load_skill_pack("bad-scripts", skills_root=self.root)


class BundledSkillsTests(unittest.TestCase):
    def test_repo_sample_skills_load(self) -> None:
        root = Path(__file__).resolve().parents[1] / "skills"
        if not root.is_dir():
            self.skipTest("sample skills directory not present")
        packs = list_skill_packs(skills_root=root)
        names = {p.name for p in packs}
        self.assertIn("study-notes", names)
        self.assertIn("code-review", names)
        self.assertIn("planner-outline", names)


if __name__ == "__main__":
    unittest.main()
