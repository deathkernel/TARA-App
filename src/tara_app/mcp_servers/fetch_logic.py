"""Bounded, read-only HTTP(S) fetch helpers for the built-in MCP fetch server.

Only public destinations are contacted. DNS results are validated and the
connection is pinned to a validated address; redirects are rejected so a
public endpoint cannot redirect the fetcher into a private network.
"""
from __future__ import annotations

import http.client
import ipaddress
import socket
import ssl
from urllib.parse import urlsplit

_MAX_URL_LEN = 2048
_MAX_BODY_BYTES = 256_000
_DEFAULT_TIMEOUT = 15.0
_USER_AGENT = "TARA-App-MCP-Fetch/1.0 (+local; read-only)"


class FetchError(ValueError):
    """Raised when a fetch request is rejected or fails safely."""


def _public_address(host: str, port: int) -> str:
    if "%" in host:
        raise FetchError("scoped IP addresses are not allowed")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        try:
            infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
        except OSError as exc:
            raise FetchError("hostname could not be resolved") from exc
        addresses = []
        for info in infos:
            candidate = ipaddress.ip_address(info[4][0])
            if not candidate.is_global:
                raise FetchError("hostname resolves to a non-public address")
            if candidate.compressed not in addresses:
                addresses.append(candidate.compressed)
        if not addresses:
            raise FetchError("hostname could not be resolved")
        return addresses[0]
    if not address.is_global:
        raise FetchError("non-public IP addresses are not allowed")
    return address.compressed


class _PinnedHTTPConnection(http.client.HTTPConnection):
    def __init__(self, host: str, port: int, address: str, timeout: float) -> None:
        super().__init__(host, port, timeout=timeout)
        self._address = address

    def connect(self) -> None:
        self.sock = socket.create_connection((self._address, self.port), self.timeout)


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, host: str, port: int, address: str, timeout: float) -> None:
        super().__init__(host, port, timeout=timeout, context=ssl.create_default_context())
        self._address = address

    def connect(self) -> None:
        raw = socket.create_connection((self._address, self.port), self.timeout)
        try:
            self.sock = self._context.wrap_socket(raw, server_hostname=self.host)
        except BaseException:
            raw.close()
            raise


def validate_public_https_url(url: str) -> str:
    if not isinstance(url, str) or not url.strip():
        raise FetchError("url must be a non-empty string")
    raw = url.strip()
    if len(raw) > _MAX_URL_LEN:
        raise FetchError("url is too long")
    try:
        parsed = urlsplit(raw)
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
    except ValueError:
        raise FetchError("url is invalid") from None
    if parsed.scheme not in {"http", "https"}:
        raise FetchError("only http and https URLs are allowed")
    if not parsed.hostname:
        raise FetchError("url must include a hostname")
    if parsed.username is not None or parsed.password is not None:
        raise FetchError("urls with embedded credentials are not allowed")
    if parsed.fragment:
        raw = raw.split("#", 1)[0]
        parsed = urlsplit(raw)
    if parsed.hostname.lower() in {"localhost", "metadata", "metadata.google.internal"}:
        raise FetchError("local or metadata hosts are not allowed")
    if not 1 <= port <= 65535:
        raise FetchError("URL port is invalid")
    return raw


def fetch_text(url: str, *, timeout_seconds: float = _DEFAULT_TIMEOUT) -> dict[str, str | int]:
    safe_url = validate_public_https_url(url)
    if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, (int, float)) or not 1.0 <= timeout_seconds <= 60.0:
        raise FetchError("timeout_seconds must be between 1 and 60")
    parsed = urlsplit(safe_url)
    host = parsed.hostname
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    address = _public_address(host, port)
    connection_type = _PinnedHTTPSConnection if parsed.scheme == "https" else _PinnedHTTPConnection
    connection = connection_type(host, port, address, float(timeout_seconds))
    path = parsed.path or "/"
    if parsed.query:
        path += "?" + parsed.query
    try:
        connection.request(
            "GET",
            path,
            headers={
                "User-Agent": _USER_AGENT,
                "Accept": "text/*,application/json,application/xml",
                "Connection": "close",
            },
        )
        response = connection.getresponse()
        if response.status in {301, 302, 303, 307, 308}:
            raise FetchError("redirects are not followed by the safe fetch server")
        content_type = response.getheader("Content-Type", "")
        chunks: list[bytes] = []
        total = 0
        while True:
            block = response.read(min(64_000, _MAX_BODY_BYTES + 1 - total))
            if not block:
                break
            total += len(block)
            if total > _MAX_BODY_BYTES:
                raise FetchError(f"response exceeds {_MAX_BODY_BYTES} byte limit")
            chunks.append(block)
        body = b"".join(chunks)
        try:
            text = body.decode("utf-8")
        except UnicodeDecodeError:
            text = body.decode("utf-8", errors="replace")
        return {
            "url": safe_url,
            "status": int(response.status),
            "content_type": content_type,
            "body": text,
            "bytes": len(body),
        }
    except FetchError:
        raise
    except (TimeoutError, socket.timeout) as exc:
        raise FetchError("request timed out") from exc
    except (OSError, http.client.HTTPException) as exc:
        raise FetchError("request failed") from exc
    finally:
        connection.close()
