from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tara_app.runtime import create_application


class OmniRouteRuntimeConfigTests(unittest.TestCase):
    def test_explicit_omniroute_environment_overrides_ollama_default(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / "tara-app.toml"
            config.write_text(
                """
[ollama]
base_url = "http://127.0.0.1:11434"
[ollama.models]
chat = "llama3.2:3b"

[router]
command = ["{python}", "-c", "pass"]
working_directory = "."

[[modules]]
id = "chat"
command = ["{python}", "-m", "tara_chat.app_adapter"]
working_directory = "."
environment = ["TARA_LLM_BACKEND", "TARA_OMNIROUTE_API_KEY", "TARA_OMNIROUTE_BASE_URL", "TARA_OMNIROUTE_MODEL"]
""",
                encoding="utf-8",
            )
            with patch.dict(os.environ, {
                "TARA_LLM_BACKEND": "omniroute",
                "TARA_OMNIROUTE_API_KEY": "test-key",
                "TARA_OMNIROUTE_MODEL": "auto",
            }, clear=True):
                app = create_application(config)
            adapter = app.registry.adapter("chat")
            self.assertEqual(adapter.environment["TARA_LLM_BACKEND"], "omniroute")
            self.assertEqual(adapter.environment["TARA_OMNIROUTE_API_KEY"], "test-key")
            self.assertEqual(adapter.environment["TARA_OMNIROUTE_MODEL"], "auto")
            self.assertEqual(adapter.environment["TARA_LLAMA_MODEL"], "llama3.2:3b")


if __name__ == "__main__":
    unittest.main()
