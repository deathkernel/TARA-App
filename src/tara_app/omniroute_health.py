"""Bounded authenticated health probe for the local OmniRoute gateway."""

from __future__ import annotations

import json
from collections.abc import Mapping
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, Request, build_opener

from tara_app.http import NoRedirectHandler

_MAX_RESPONSE_BYTES = 1_000_000


def diagnose_gateway(base_url: str, api_key: str, *, timeout: float = 5.0) -> str | None:
    """Return None when the authenticated model catalogue is healthy, else a safe diagnostic."""
    if not isinstance(api_key, str) or not api_key.strip():
        return "TARA_OMNIROUTE_API_KEY is not set. Add a valid OmniRoute API key to the terminal environment used to launch SITA."
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
        with build_opener(ProxyHandler({}), NoRedirectHandler()).open(request, timeout=timeout) as response:
            raw = response.read(_MAX_RESPONSE_BYTES + 1)
    except HTTPError as exc:
        if exc.code in {401, 403}:
            return f"OmniRoute rejected the API key (HTTP {exc.code}). Check that the key is active and has model-list access."
        if exc.code == 404:
            return "OmniRoute returned HTTP 404 for /v1/models. Check TARA_OMNIROUTE_BASE_URL; it should end with /v1."
        if exc.code == 429:
            return "OmniRoute rate limit reached (HTTP 429). Wait for the gateway quota to reset."
        return f"OmniRoute model catalogue returned HTTP {exc.code}."
    except (URLError, TimeoutError, OSError):
        return "Cannot connect to OmniRoute. Start the local gateway and verify TARA_OMNIROUTE_BASE_URL."
    if len(raw) > _MAX_RESPONSE_BYTES:
        return "OmniRoute model catalogue exceeded SITA's 1 MB response limit."
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return "OmniRoute returned invalid JSON from /v1/models."
    if not isinstance(payload, Mapping) or not isinstance(payload.get("data"), list):
        return "OmniRoute /v1/models returned an unexpected response. Expected an OpenAI-compatible data array."
    return None


def check_gateway(base_url: str, api_key: str, *, timeout: float = 5.0) -> bool:
    """Return True only when authenticated GET /models returns a valid catalogue."""
    return diagnose_gateway(base_url, api_key, timeout=timeout) is None
