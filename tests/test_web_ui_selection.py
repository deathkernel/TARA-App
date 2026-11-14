"""Tests for safe selection of the SITA web interface."""
from __future__ import annotations

import os
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.request import urlopen

from tara_app.webapp import _Server, _react_ui_enabled


class ReactUiSelectionTests(unittest.TestCase):
    def test_react_workspace_is_default(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            self.assertTrue(_react_ui_enabled())

    def test_static_ui_can_be_selected_explicitly(self) -> None:
        with patch.dict(os.environ, {"TARA_ENABLE_REACT_UI": "0"}, clear=True):
            self.assertFalse(_react_ui_enabled())

    def test_react_ui_can_be_enabled_explicitly(self) -> None:
        with patch.dict(os.environ, {"TARA_ENABLE_REACT_UI": "1"}):
            self.assertTrue(_react_ui_enabled())

    def _serve_root(self, web_root: Path) -> str:
        server = _Server(("127.0.0.1", 0), object())
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with patch("tara_app.webapp._WEB_ROOT", web_root), patch.dict(os.environ, {}, clear=True):
                with urlopen(f"http://127.0.0.1:{server.server_port}/", timeout=2) as response:
                    return response.read().decode("utf-8")
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_react_default_serves_static_fallback_when_no_build_exists(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "index.html").write_text("static fallback", encoding="utf-8")
            self.assertEqual(self._serve_root(root), "static fallback")

    def test_react_default_serves_compiled_workspace_when_present(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            react_root = root / "react-dist"
            react_root.mkdir()
            (react_root / "index.html").write_text("compiled workspace", encoding="utf-8")
            self.assertEqual(self._serve_root(root), "compiled workspace")


if __name__ == "__main__":
    unittest.main()
