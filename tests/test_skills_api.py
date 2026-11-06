"""Loopback HTTP tests for the read-only chat skill catalogue."""
from __future__ import annotations

import json
import os
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from unittest.mock import patch

from tara_app.application.facade import ApplicationFacade
from tara_app.webapp import _Server


class SkillsApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.skills_root = Path(self.temp_dir.name)
        pack = self.skills_root / "study-notes"
        pack.mkdir()
        (pack / "SKILL.md").write_text("Private prompt instructions.", encoding="utf-8")
        (pack / "skill.toml").write_text(
            'title = "Study Notes"\ndescription = "Source-grounded study help"\nversion = "1.0.0"\ntags = ["study"]\nscripts = ["review.py"]\n',
            encoding="utf-8",
        )
        self.env = patch.dict(os.environ, {"TARA_SKILLS_ROOT": str(self.skills_root)})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.app = ApplicationFacade(object())
        self.server = _Server(("127.0.0.1", 0), self.app)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self._stop_server)
        self.base_url = f"http://127.0.0.1:{self.server.server_port}"

    def _stop_server(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def test_skill_catalogue_returns_display_metadata_only(self) -> None:
        with urlopen(self.base_url + "/api/skills", timeout=2) as response:
            payload = json.loads(response.read().decode("utf-8"))
        self.assertEqual(payload["status"], "available")
        self.assertEqual(len(payload["skills"]), 1)
        skill = payload["skills"][0]
        self.assertEqual(skill["name"], "study-notes")
        self.assertEqual(skill["title"], "Study Notes")
        self.assertEqual(skill["tags"], ["study"])
        self.assertNotIn("instructions", skill)
        self.assertNotIn("scripts", skill)

    def test_skill_catalogue_rejects_untrusted_origin(self) -> None:
        request = Request(
            self.base_url + "/api/skills",
            headers={"Origin": "http://evil.example"},
        )
        with self.assertRaises(HTTPError) as caught:
            urlopen(request, timeout=2)
        self.assertEqual(caught.exception.code, 403)


if __name__ == "__main__":
    unittest.main()
