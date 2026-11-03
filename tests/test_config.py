"""Tests for the validated runtime settings layer."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from tara_app.config import SettingsError, load_runtime_settings  # noqa: E402


class RuntimeSettingsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "runtime.json"

    def write(self, data) -> None:
        self.path.write_text(json.dumps(data), encoding="utf-8")

    def test_missing_provider_fields_use_disabled_safe_defaults(self) -> None:
        self.write({"schema_version": 1, "providers": {"ollama": {}}})
        settings = load_runtime_settings(self.path)
        self.assertFalse(settings.providers["ollama"].enabled)
        self.assertEqual(settings.providers["ollama"].port, 11434)
        self.assertEqual(settings.providers["ollama"].timeout_seconds, 10.0)

    def test_valid_explicit_settings_are_normalized(self) -> None:
        self.write({"schema_version": 1, "providers": {
            "ollama": {"enabled": True, "port": 11435, "timeout_seconds": 5}
        }})
        settings = load_runtime_settings(self.path)
        self.assertTrue(settings.providers["ollama"].enabled)
        self.assertEqual(settings.providers["ollama"].timeout_seconds, 5.0)

    def test_rejects_invalid_schema_and_shape(self) -> None:
        for value in (
            {"schema_version": True, "providers": {}},
            {"schema_version": 2, "providers": {}},
            {"schema_version": 1, "providers": []},
            [],
        ):
            with self.subTest(value=value):
                self.write(value)
                with self.assertRaises(SettingsError):
                    load_runtime_settings(self.path)

    def test_rejects_invalid_provider_values(self) -> None:
        invalid_options = (
            {"enabled": "true"},
            {"port": True},
            {"port": 0},
            {"port": 65536},
            {"timeout_seconds": True},
            {"timeout_seconds": 0},
            {"timeout_seconds": 121},
        )
        for options in invalid_options:
            with self.subTest(options=options):
                self.write({"schema_version": 1, "providers": {"ollama": options}})
                with self.assertRaises(SettingsError):
                    load_runtime_settings(self.path)

    def test_rejects_non_object_provider_entry(self) -> None:
        self.write({"schema_version": 1, "providers": {"ollama": []}})
        with self.assertRaisesRegex(SettingsError, "must be an object"):
            load_runtime_settings(self.path)


if __name__ == "__main__":
    unittest.main()
