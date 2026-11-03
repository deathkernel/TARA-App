"""Offline tests for the fail-closed runtime manager."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from tara_app.runtime_manager import RuntimeConfigurationError, RuntimeManager  # noqa: E402


class RuntimeManagerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.registry = self.root / "registry.json"
        self.settings = self.root / "runtime.json"
        source_registry = json.loads((ROOT / "config" / "ai_tool_registry.json").read_text(encoding="utf-8"))
        self.registry.write_text(json.dumps(source_registry), encoding="utf-8")
        self.settings.write_text(json.dumps({"schema_version": 1, "providers": {"ollama": {"enabled": False}}}), encoding="utf-8")
        self.provider = Mock()
        self.provider.health.return_value = True
        self.provider.list_models.return_value = [SimpleNamespace(
            name="tinyllama:latest",
            size=123,
            digest="sha256:abc",
            modified_at="2026-10-25T10:00:00Z",
            family="llama",
            parameter_size="1B",
            quantization_level="Q4_0",
            model_format="gguf",
        )]
        self.provider.chat.return_value = "local response"
        self.factory = Mock(return_value=self.provider)

    def manager(self) -> RuntimeManager:
        return RuntimeManager(self.registry, self.settings, provider_factory=self.factory)

    def write_settings(self, settings: dict) -> None:
        self.settings.write_text(json.dumps(settings), encoding="utf-8")

    def test_provider_is_disabled_by_default(self) -> None:
        manager = self.manager()
        self.assertEqual(manager.configured_provider_ids, ())
        status = manager.provider_status("ollama")
        self.assertFalse(status.configured)
        with self.assertRaisesRegex(RuntimeConfigurationError, "not enabled"):
            manager.list_models()

    def test_explicit_enablement_configures_only_local_provider(self) -> None:
        self.write_settings({
            "schema_version": 1,
            "providers": {"ollama": {"enabled": True, "port": 11434, "timeout_seconds": 5}},
        })
        manager = self.manager()
        self.assertEqual(manager.configured_provider_ids, ("ollama",))
        self.factory.assert_called_once_with(port=11434, timeout_seconds=5.0)
        self.assertTrue(manager.provider_status("ollama").healthy)

    def test_model_listing_is_normalized(self) -> None:
        self.write_settings({"schema_version": 1, "providers": {"ollama": {"enabled": True}}})
        models = self.manager().list_models()
        self.assertEqual(models[0].provider_id, "ollama")
        self.assertEqual(models[0].name, "tinyllama:latest")
        self.assertEqual(models[0].size_bytes, 123)
        self.assertEqual(models[0].digest, "sha256:abc")
        self.assertEqual(models[0].modified_at, "2026-10-25T10:00:00Z")
        self.assertEqual(models[0].family, "llama")
        self.assertEqual(models[0].parameter_size, "1B")
        self.assertEqual(models[0].quantization_level, "Q4_0")
        self.assertEqual(models[0].model_format, "gguf")

    def test_status_refresh_handles_adapter_failure(self) -> None:
        self.write_settings({"schema_version": 1, "providers": {"ollama": {"enabled": True}}})
        self.provider.health.side_effect = RuntimeError("internal adapter details")
        status = self.manager().refresh_provider_status("ollama")
        self.assertTrue(status.configured)
        self.assertFalse(status.healthy)
        self.assertEqual(status.message, "Local provider is unavailable")

    def test_chat_routes_through_selected_provider(self) -> None:
        self.write_settings({"schema_version": 1, "providers": {"ollama": {"enabled": True}}})
        result = self.manager().chat("tinyllama:latest", [{"role": "user", "content": "hello"}])
        self.assertEqual(result, "local response")
        self.provider.chat.assert_called_once()

    def test_unknown_or_unimplemented_provider_fails_closed(self) -> None:
        self.write_settings({"schema_version": 1, "providers": {"unknown": {"enabled": True}}})
        with self.assertRaisesRegex(RuntimeConfigurationError, "not present"):
            self.manager()

    def test_invalid_settings_fail_closed(self) -> None:
        self.write_settings({"schema_version": 1, "providers": {"ollama": {"enabled": True, "port": "bad"}}})
        with self.assertRaisesRegex(RuntimeConfigurationError, "port must be an integer"):
            self.manager()

    def test_missing_or_unknown_runtime_schema_fails_closed(self) -> None:
        for settings in ({"providers": {}}, {"schema_version": 2, "providers": {}}):
            with self.subTest(settings=settings):
                self.write_settings(settings)
                with self.assertRaisesRegex(RuntimeConfigurationError, "runtime settings schema_version"):
                    self.manager()

    def test_non_boolean_enabled_flag_fails_closed(self) -> None:
        self.write_settings({"schema_version": 1, "providers": {"ollama": {"enabled": "true"}}})
        with self.assertRaisesRegex(RuntimeConfigurationError, "enabled must be boolean"):
            self.manager()

    def test_duplicate_registry_ids_fail_closed(self) -> None:
        registry = json.loads(self.registry.read_text(encoding="utf-8"))
        registry["tools"].append(dict(registry["tools"][0]))
        self.registry.write_text(json.dumps(registry), encoding="utf-8")
        with self.assertRaisesRegex(RuntimeConfigurationError, "duplicate provider/tool id"):
            self.manager()


if __name__ == "__main__":
    unittest.main()
