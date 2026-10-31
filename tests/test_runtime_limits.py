from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from tara_app.runtime import RuntimeConfigurationError, create_application  # noqa: E402


class LocalModelConcurrencyTests(unittest.TestCase):
    def write_config(self, root: Path, limit: int) -> Path:
        config = root / "tara-app.toml"
        config.write_text(
            '[router]\n'
            'command = ["{python}", "-m", "tara_router"]\n'
            'working_directory = "."\n'
            '[ollama]\n'
            'base_url = "http://127.0.0.1:11434"\n'
            f'max_concurrent_requests = {limit}\n'
            '[[modules]]\n'
            'id = "chat"\n'
            'command = ["{python}", "-m", "tara_chat.app_adapter"]\n'
            'working_directory = "."\n'
            '[[modules]]\n'
            'id = "code"\n'
            'command = ["{python}", "-m", "tara_code"]\n'
            'working_directory = "."\n',
            encoding="utf-8",
        )
        return config

    def test_chat_and_code_share_one_local_inference_slot_by_default(self):
        with tempfile.TemporaryDirectory() as temp:
            app = create_application(self.write_config(Path(temp), 1))
            chat = app.registry.adapter("chat")
            code = app.registry.adapter("code")
            self.assertIsNotNone(chat)
            self.assertIsNotNone(code)
            self.assertIs(chat.execution_semaphore, code.execution_semaphore)
            self.assertTrue(chat.execution_semaphore.acquire(blocking=False))
            self.assertFalse(code.execution_semaphore.acquire(blocking=False))
            chat.execution_semaphore.release()

    def test_configured_two_slots_allow_two_local_model_requests(self):
        with tempfile.TemporaryDirectory() as temp:
            app = create_application(self.write_config(Path(temp), 2))
            semaphore = app.registry.adapter("chat").execution_semaphore
            self.assertTrue(semaphore.acquire(blocking=False))
            self.assertTrue(semaphore.acquire(blocking=False))
            self.assertFalse(semaphore.acquire(blocking=False))
            semaphore.release()
            semaphore.release()

    def test_concurrency_limit_above_two_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(RuntimeConfigurationError):
                create_application(self.write_config(Path(temp), 3))


if __name__ == "__main__":
    unittest.main()
