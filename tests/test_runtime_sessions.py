from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from tara_app.runtime import RuntimeConfigurationError, create_application  # noqa: E402
from tara_app.registry import CapabilityRegistry  # noqa: E402
from tara_app.sessions import SessionStore  # noqa: E402
from tara_app.orchestrator import Orchestrator  # noqa: E402


class RuntimeSessionConfigurationTests(unittest.TestCase):
    def write_config(self, root: Path, sessions: str = "") -> Path:
        config = root / "tara-app.toml"
        config.write_text(
            '[router]\n'
            'command = ["{python}", "-m", "tara_router"]\n'
            'working_directory = "."\n'
            + sessions,
            encoding="utf-8",
        )
        return config

    def test_sqlite_session_store_is_opt_in_and_resolves_relative_path(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config = self.write_config(
                root,
                '[sessions]\n'
                'database_path = "data/sessions.sqlite3"\n'
                'max_sessions = 20\n'
                'max_messages_per_session = 24\n'
                'max_content_chars = 20000\n',
            )
            app = create_application(config)
            self.assertIsInstance(app, Orchestrator)
            self.assertIsInstance(app.session_store, SessionStore)
            self.assertEqual(app.session_store.database_path, (root / "data/sessions.sqlite3").resolve())

    def test_session_persistence_is_disabled_without_database_path(self):
        with tempfile.TemporaryDirectory() as temp:
            app = create_application(self.write_config(Path(temp)))
            self.assertIsNone(app.session_store)

    def test_invalid_session_limits_fail_closed(self):
        for setting in ("max_sessions = 0", "max_messages_per_session = 1"):
            with self.subTest(setting=setting), tempfile.TemporaryDirectory() as temp:
                config = self.write_config(Path(temp), f'[sessions]\ndatabase_path = "sessions.sqlite3"\n{setting}\n')
                with self.assertRaises(RuntimeConfigurationError):
                    create_application(config)


if __name__ == "__main__":
    unittest.main()
