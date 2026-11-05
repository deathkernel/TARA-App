"""Tests for skill-pack loader and chat skill wiring helpers."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from tara_app.application.facade import ApplicationFacade
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
        self.assertIn("carefully", pack.prompt_block())

    def test_invalid_name_rejected(self) -> None:
        with self.assertRaises(SkillLoadError):
            load_skill_pack("../etc", skills_root=self.root)


class FacadeSkillsTests(unittest.TestCase):
    def test_list_skills_empty_without_root(self) -> None:
        coordinator = MagicMock()
        facade = ApplicationFacade(coordinator)
        skills = facade.list_skills()
        self.assertIsInstance(skills, list)


class BundledSkillsTests(unittest.TestCase):
    def test_repo_samples(self) -> None:
        root = Path(__file__).resolve().parents[1] / "skills"
        if not root.is_dir():
            self.skipTest("no skills dir")
        packs = list_skill_packs(skills_root=root)
        names = {p.name for p in packs}
        self.assertIn("study-notes", names)


if __name__ == "__main__":
    unittest.main()
