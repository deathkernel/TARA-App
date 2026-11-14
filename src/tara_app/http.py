"""Shared HTTP primitives for SITA network clients."""
from __future__ import annotations

from urllib.request import HTTPRedirectHandler


class NoRedirectHandler(HTTPRedirectHandler):
    """Reject HTTP redirects so credentials and requests stay on the configured endpoint."""

    def redirect_request(self, request, file, code, message, headers, new_url):
        return None
