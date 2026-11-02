"""Tests for safe selection of the TARA web interface."""
from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from tara_app.webapp import _react_ui_enabled


class ReactUiSelectionTests(unittest.TestCase):
    def test_static_ui_remains_default(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(_react_ui_enabled())

    def test_react_ui_requires_explicit_opt_in(self) -> None:
        for value in ("", "true", "yes", "0", "TRUE"):
            with self.subTest(value=value), patch.dict(os.environ, {"TARA_ENABLE_REACT_UI": value}):
                self.assertFalse(_react_ui_enabled())

    def test_react_ui_can_be_enabled_explicitly(self) -> None:
        with patch.dict(os.environ, {"TARA_ENABLE_REACT_UI": "1"}):
            self.assertTrue(_react_ui_enabled())


if __name__ == "__main__":
    unittest.main()
