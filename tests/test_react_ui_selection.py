from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from tara_app.webapp import _react_ui_enabled


class ReactUiSelectionTests(unittest.TestCase):
    def test_react_workspace_is_the_default(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertTrue(_react_ui_enabled())

    def test_static_ui_can_be_selected_explicitly(self):
        with patch.dict(os.environ, {"TARA_ENABLE_REACT_UI": "0"}, clear=True):
            self.assertFalse(_react_ui_enabled())

    def test_react_workspace_can_be_enabled_explicitly(self):
        with patch.dict(os.environ, {"TARA_ENABLE_REACT_UI": "1"}, clear=True):
            self.assertTrue(_react_ui_enabled())


if __name__ == "__main__":
    unittest.main()
