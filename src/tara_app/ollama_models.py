"""Read-only inventory of configured local Ollama models."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

_MAX_RESPONSE_BYTES = 256_000


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(
        self,
        req: Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> None:
        return None


class OllamaModelCatalog:
    """Report configured profiles and whether their weights are installed."""

    def __init__(self, profiles: Mapping[str, str] | None = None, base_url: str | None = None) -> None:
        self.profiles = dict(profiles or {})
        self.base_url = base_url
        if not self.profiles:
            if self.base_url is not None:
                raise ValueError("base_url cannot be set without configured Ollama profiles")
            return
        if not isinstance(base_url, str) or not base_url:
            raise ValueError("configured Ollama profiles require a local base URL")
        try:
            parsed = urlsplit(base_url)
            port = parsed.port
        except ValueError as exc:
            raise ValueError("Ollama base URL is invalid") from exc
        if (
            parsed.scheme not in {"http", "https"}
            or parsed.hostname not in {"localhost", "127.0.0.1", "::1"}
            or parsed.username
            or parsed.password
            or parsed.path not in {"", "/"}
            or parsed.query
            or parsed.fragment
            or (port is not None and not 1 <= port <= 65535)
        ):
            raise ValueError("Ollama model inventory only accepts a local origin")
        if any(
            not isinstance(module, str)
            or not module
            or not isinstance(model, str)
            or not model
            or len(model) > 200
            or any(char.isspace() or ord(char) < 32 for char in model)
            for module, model in self.profiles.items()
        ):
            raise ValueError("Ollama profile names are invalid")

    def status(self) -> dict[str, Any]:
        if not self.profiles or self.base_url is None:
            return {
                "status": "not_configured",
                "provider": "ollama",
                "service_available": False,
                "models": [],
            }

        installed = self._installed_models()
        service_available = installed is not None
        return {
            "status": "success" if service_available else "unavailable",
            "provider": "ollama",
            "service_available": service_available,
            "models": [
                {
                    "specialist": module_id,
                    "model": model,
                    "installed": model in installed if installed is not None else None,
                }
                for module_id, model in sorted(self.profiles.items())
            ],
        }

    def _installed_models(self) -> set[str] | None:
        request = Request(
            self.base_url + "/api/tags",
            headers={"Accept": "application/json"},
            method="GET",
        )
        try:
            with build_opener(ProxyHandler({}), _NoRedirect()).open(request, timeout=2) as response:
                raw = response.read(_MAX_RESPONSE_BYTES + 1)
        except (HTTPError, URLError, TimeoutError, OSError):
            return None
        if len(raw) > _MAX_RESPONSE_BYTES:
            return None
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None
        models = payload.get("models") if isinstance(payload, Mapping) else None
        if not isinstance(models, list):
            return None
        installed: set[str] = set()
        for model in models:
            if not isinstance(model, Mapping):
                continue
            for key in ("name", "model"):
                name = model.get(key)
                if isinstance(name, str):
                    installed.add(name)
        return installed
