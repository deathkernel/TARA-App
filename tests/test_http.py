from __future__ import annotations

import unittest
from urllib.request import Request

from tara_app.http import NoRedirectHandler


class NoRedirectHandlerTests(unittest.TestCase):
    def test_rejects_redirects(self) -> None:
        handler = NoRedirectHandler()
        request = Request("http://127.0.0.1:20128/v1/models")
        redirected = handler.redirect_request(
            request,
            None,
            302,
            "Found",
            {},
            "http://example.com/collect",
        )
        self.assertIsNone(redirected)


if __name__ == "__main__":
    unittest.main()
