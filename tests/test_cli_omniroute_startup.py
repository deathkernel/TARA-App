from __future__ import annotations

import sys
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from tara_app import cli


class CliOmniRouteStartupTests(unittest.TestCase):
    def _run_with_backend(self, backend: str):
        catalog = Mock()
        catalog.profiles = {"chat": "llama3.2:3b"}
        adapter = SimpleNamespace(environment={"TARA_LLM_BACKEND": backend})
        app = SimpleNamespace(
            model_catalog=catalog,
            registry=SimpleNamespace(adapter=Mock(return_value=adapter)),
        )
        with (
            patch.object(sys, "argv", ["tara-app"]),
            patch.object(cli, "create_application", return_value=app),
            patch.object(cli, "serve") as serve,
        ):
            result = cli.main()
        return result, catalog, serve

    def test_omniroute_skips_local_chat_model_download_and_warmup(self):
        result, catalog, serve = self._run_with_backend("omniroute")

        self.assertEqual(result, 0)
        catalog.ensure_service_started.assert_called_once_with()
        catalog.ensure_model_installed.assert_not_called()
        catalog.preload_model.assert_not_called()
        serve.assert_called_once()

    def test_ollama_still_prepares_local_chat_model(self):
        result, catalog, serve = self._run_with_backend("ollama")

        self.assertEqual(result, 0)
        catalog.ensure_service_started.assert_called_once_with()
        catalog.ensure_model_installed.assert_called_once_with("chat")
        catalog.preload_model.assert_called_once_with("chat", keep_alive="15m")
        serve.assert_called_once()


if __name__ == "__main__":
    unittest.main()
