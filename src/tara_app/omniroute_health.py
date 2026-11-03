"""Bounded authenticated health probe for the local OmniRoute gateway."""

from __future__ import annotations

import json
from collections.abc import Mapping
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

_MAX_RESPONSE_BYTES = 1_000_000


class _NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, request, file, code, message, headers, new_url):
        return None


def check_gateway(base_url: str, api_key: str, *, timeout: float = 5.0) -> bool:
    """Return True only when authenticated GET /models returns a valid catalogue."""
    request = Request(
        base_url.rstrip("/") + "/models",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
            "User-Agent": "TARA-App/0.1",
        },
        method="GET",
    )
    try:
        with build_opener(ProxyHandler({}), _NoRedirectHandler()).open(request, timeout=timeout) as response:
            raw = response.read(_MAX_RESPONSE_BYTES + 1)
        if len(raw) > _MAX_RESPONSE_BYTES:
            return False
        payload = json.loads(raw.decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, OSError, UnicodeDecodeError, json.JSONDecodeError):
        return False
    return isinstance(payload, Mapping) and isinstance(payload.get("data"), list)
