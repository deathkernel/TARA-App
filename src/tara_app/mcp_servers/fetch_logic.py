"""Bounded, read-only HTTP(S) fetch helpers for the built-in MCP fetch server.

Blocks private/link-local targets, non-HTTP(S) schemes, oversized bodies, and
slow responses. This is not a browser and does not execute JavaScript.
"""
from __future__ import annotations

import ipaddress
import socket
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

_MAX_URL_LEN = 2048
_MAX_BODY_BYTES = 256_000
_DEFAULT_TIMEOUT = 15.0
_USER_AGENT = "TARA-App-MCP-Fetch/1.0 (+local; read-only)"


class FetchError(ValueError):
    """Raised when a fetch request is rejected or fails safely."""


def validate_public_https_url(url: str) -> str:
    if not isinstance(url, str) or not url.strip():
        raise FetchError("url must be a non-empty string")
    raw = url.strip()
    if len(raw) > _MAX_URL_LEN:
        raise FetchError("url is too long")
    parsed = urlparse(raw)
    if parsed.scheme not in {"http", "https"}:
        raise FetchError("only http and https URLs are allowed")
    if not parsed.hostname:
        raise FetchError("url must include a hostname")
    if parsed.username or parsed.password:
        raise FetchError("urls with embedded credentials are not allowed")
    host = parsed.hostname
    if host.lower() in {"localhost", "metadata", "metadata.google.internal"}:
        raise FetchError("local or metadata hosts are not allowed")
    try:
        addr = ipaddress.ip_address(host)
        if not addr.is_global:
            raise FetchError("non-public IP addresses are not allowed")
    except ValueError:
        try:
            infos = socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80))
        except socket.gaierror as exc:
            raise FetchError(f"hostname could not be resolved: {host}") from exc
        if not infos:
            raise FetchError(f"hostname could not be resolved: {host}")
        for info in infos:
            ip = ipaddress.ip_address(info[4][0])
            if not ip.is_global:
                raise FetchError("hostname resolves to a non-public address")
    return raw


def fetch_text(url: str, *, timeout_seconds: float = _DEFAULT_TIMEOUT) -> dict[str, str | int]:
    safe_url = validate_public_https_url(url)
    if not 1.0 <= timeout_seconds <= 60.0:
        raise FetchError("timeout_seconds must be between 1 and 60")
    request = Request(
        safe_url,
        headers={"User-Agent": _USER_AGENT, "Accept": "text/*,application/json,application/xml"},
        method="GET",
    )
    try:
        with urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310 — scheme validated
            status = int(getattr(response, "status", 200) or 200)
            content_type = response.headers.get("Content-Type", "")
            chunks: list[bytes] = []
            total = 0
            while True:
                block = response.read(64_000)
                if not block:
                    break
                total += len(block)
                if total > _MAX_BODY_BYTES:
                    raise FetchError(f"response exceeds {_MAX_BODY_BYTES} byte limit")
                chunks.append(block)
    except FetchError:
        raise
    except HTTPError as exc:
        raise FetchError(f"http error: {exc.code}") from exc
    except URLError as exc:
        raise FetchError(f"request failed: {exc.reason}") from exc
    except TimeoutError as exc:
        raise FetchError("request timed out") from exc
    body = b"".join(chunks)
    try:
        text = body.decode("utf-8")
    except UnicodeDecodeError:
        text = body.decode("utf-8", errors="replace")
    return {
        "url": safe_url,
        "status": status,
        "content_type": content_type,
        "body": text,
        "bytes": len(body),
    }
