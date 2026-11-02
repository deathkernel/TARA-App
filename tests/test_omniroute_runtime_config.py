from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tara_app.runtime import create_application


class OmniRouteRuntimeConfigTests(unittest.TestCase):
    def test_all_llm_specialists_use_omniroute_and_ignore_legacy_ollama_defaults(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / "tara-app.toml"
            config.write_text(
                """
[ollama]
base_url = "http://127.0.0.1:11434"
[ollama.models]
chat = "llama3.2:3b"
code = "qwen2.5-coder:3b"
vision = "gemma3:4b"
creative = "llama3.2:3b"

[omniroute]
base_url = "http://127.0.0.1:20128/v1"
[omniroute.models]
chat = "auto"
code = "auto/coding:cheap"
vision = "auto"
creative = "auto/cheap"
models = "auto"

[router]
command = ["{python}", "-c", "pass"]
working_directory = "."

[[modules]]
id = "chat"
command = ["{python}", "-c", "pass"]
working_directory = "."
environment = ["TARA_LLM_BACKEND", "TARA_OMNIROUTE_API_KEY", "TARA_OMNIROUTE_BASE_URL", "TARA_OMNIROUTE_MODEL"]

[[modules]]
id = "code"
command = ["{python}", "-c", "pass"]
working_directory = "."
environment = ["TARA_CODE_API_BASE_URL", "TARA_CODE_API_KEY", "TARA_CODE_MODEL"]

[[modules]]
id = "vision"
command = ["{python}", "-c", "pass"]
working_directory = "."
environment = ["TARA_VISION_API_BASE_URL", "TARA_VISION_API_KEY", "TARA_VISION_MODEL"]

[[modules]]
id = "creative"
command = ["{python}", "-c", "pass"]
working_directory = "."
environment = ["TARA_CREATIVE_API_BASE_URL", "TARA_CREATIVE_API_KEY", "TARA_CREATIVE_MODEL"]

[[modules]]
id = "models"
command = ["{python}", "-c", "pass"]
working_directory = "."
allow_remote = true
environment = ["TARA_MODELS_API_BASE_URL", "TARA_MODELS_API_KEY", "TARA_MODELS_MODEL"]
""",
                encoding="utf-8",
            )
            with patch.dict(os.environ, {"TARA_OMNIROUTE_API_KEY": "test-key"}, clear=True):
                app = create_application(config)

            expected = {
                "chat": ("TARA_OMNIROUTE_MODEL", "auto", "TARA_OMNIROUTE_API_KEY"),
                "code": ("TARA_CODE_MODEL", "auto/coding:cheap", "TARA_CODE_API_KEY"),
                "vision": ("TARA_VISION_MODEL", "auto", "TARA_VISION_API_KEY"),
                "creative": ("TARA_CREATIVE_MODEL", "auto/cheap", "TARA_CREATIVE_API_KEY"),
                "models": ("TARA_MODELS_MODEL", "auto", "TARA_MODELS_API_KEY"),
            }
            for module_id, (model_env, model, key_env) in expected.items():
                environment = app.registry.adapter(module_id).environment
                self.assertEqual(environment[model_env], model)
                self.assertEqual(environment[key_env], "test-key")
                self.assertFalse(any("OLLAMA" in name for name in environment))
                self.assertFalse(any(name == "GEMINI_API_KEY" for name in environment))
            self.assertEqual(app.registry.adapter("chat").environment["TARA_LLM_BACKEND"], "omniroute")
            self.assertEqual(app.model_catalog.profiles, {})

    def test_process_environment_overrides_omniroute_route_alias(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / "tara-app.toml"
            config.write_text(
                """
[omniroute]
base_url = "http://127.0.0.1:20128/v1"
[omniroute.models]
chat = "auto"
[router]
command = ["{python}", "-c", "pass"]
working_directory = "."
[[modules]]
id = "chat"
command = ["{python}", "-c", "pass"]
working_directory = "."
environment = ["TARA_OMNIROUTE_MODEL", "TARA_OMNIROUTE_API_KEY"]
""",
                encoding="utf-8",
            )
            with patch.dict(os.environ, {
                "TARA_OMNIROUTE_API_KEY": "test-key",
                "TARA_OMNIROUTE_MODEL": "auto/fast",
            }, clear=True):
                app = create_application(config)
            environment = app.registry.adapter("chat").environment
            self.assertEqual(environment["TARA_OMNIROUTE_MODEL"], "auto/fast")
            self.assertEqual(environment["TARA_LLM_BACKEND"], "omniroute")


if __name__ == "__main__":
    unittest.main()
