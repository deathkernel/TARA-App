from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from tara_app.ollama_models import OllamaModelCatalog  # noqa: E402


class OllamaRecoveryTests(unittest.TestCase):
    def catalog(self) -> OllamaModelCatalog:
        return OllamaModelCatalog({"chat": "llama3.2:3b"}, "http://127.0.0.1:11434")

    def test_model_readiness_attempts_service_recovery_before_checking_tags(self):
        catalog = self.catalog()
        with patch.object(catalog, "ensure_service_started") as recover, patch.object(
            catalog, "_installed_models", return_value={"llama3.2:3b"}
        ):
            result = catalog.ensure_model_installed("chat")
        recover.assert_called_once_with()
        self.assertEqual(result["status"], "installed")

    def test_manual_pull_recovers_service_before_starting_worker(self):
        catalog = self.catalog()
        with patch.object(catalog, "ensure_service_started") as recover, patch(
            "tara_app.ollama_models.Thread"
        ) as worker:
            result = catalog.start_pull("chat")
        recover.assert_called_once_with()
        worker.return_value.start.assert_called_once_with()
        self.assertEqual(result["status"], "queued")

    def test_unload_and_remove_recover_service_before_model_operations(self):
        catalog = self.catalog()
        with patch.object(catalog, "ensure_service_started") as recover, patch.object(
            catalog, "_unload_model_locked", return_value={"status": "unloaded"}
        ):
            self.assertEqual(catalog.unload_model("chat")["status"], "unloaded")
        recover.assert_called_once_with()

        with patch.object(catalog, "ensure_service_started") as recover, patch.object(
            catalog, "_remove_model_locked", return_value={"status": "removed"}
        ):
            self.assertEqual(catalog.remove_model("chat")["status"], "removed")
        recover.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
