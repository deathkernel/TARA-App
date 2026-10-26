"""Inventory and explicitly requested downloads for local Ollama models."""

from __future__ import annotations

import json
from collections.abc import Mapping
from threading import Lock, Thread
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

_MAX_RESPONSE_BYTES = 256_000
_MAX_PULL_LINE_BYTES = 64_000
_ACTIVE_PULL_STATES = frozenset({"queued", "pulling"})


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
    """Report model readiness and pull only configured models on user request."""

    def __init__(self, profiles: Mapping[str, str] | None = None, base_url: str | None = None) -> None:
        self.profiles = dict(profiles or {})
        self.base_url = base_url
        self._pull_lock = Lock()
        self._pull_state: dict[str, Any] = {"status": "idle"}
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
                "pull": self.pull_status(),
            }

        installed = self._installed_models()
        service_available = installed is not None
        running = self._running_models() if service_available else None
        return {
            "status": "success" if service_available else "unavailable",
            "provider": "ollama",
            "service_available": service_available,
            "models": [
                {
                    "specialist": module_id,
                    "model": model,
                    "installed": model in installed if installed is not None else None,
                    "running": model in running if running is not None else None,
                    "memory_bytes": running.get(model, {}).get("size") if running is not None else None,
                    "vram_bytes": running.get(model, {}).get("size_vram") if running is not None else None,
                    "expires_at": running.get(model, {}).get("expires_at") if running is not None else None,
                }
                for module_id, model in sorted(self.profiles.items())
            ],
            "pull": self.pull_status(),
        }

    def start_pull(self, specialist: Any) -> dict[str, Any]:
        """Start one background pull for a configured specialist profile."""
        if not isinstance(specialist, str) or specialist not in self.profiles:
            raise ValueError("specialist is not a configured local model profile")
        if self.base_url is None:
            raise RuntimeError("local Ollama is not configured")

        with self._pull_lock:
            if self._pull_state.get("status") in _ACTIVE_PULL_STATES:
                raise RuntimeError("another local model download is already running")
            model = self.profiles[specialist]
            self._pull_state = {
                "status": "queued",
                "specialist": specialist,
                "model": model,
                "message": "Waiting for local Ollama",
                "completed": 0,
                "total": None,
                "percent": None,
            }
            worker = Thread(target=self._pull_model, args=(specialist, model), daemon=True)
            worker.start()
            return dict(self._pull_state)

    def pull_status(self) -> dict[str, Any]:
        with self._pull_lock:
            return dict(self._pull_state)

    def _pull_model(self, specialist: str, model: str) -> None:
        base_url = self.base_url
        if base_url is None:
            self._set_pull_state(
                status="failed",
                specialist=specialist,
                model=model,
                message="Local Ollama is not configured.",
                error="local_model_provider_unavailable",
            )
            return
        self._set_pull_state(status="pulling", message="Connecting to local Ollama")
        request = Request(
            base_url + "/api/pull",
            data=json.dumps({"model": model, "stream": True}, separators=(",", ":")).encode("utf-8"),
            headers={"Content-Type": "application/json", "Accept": "application/x-ndjson"},
            method="POST",
        )
        completed_successfully = False
        try:
            with build_opener(ProxyHandler({}), _NoRedirect()).open(request, timeout=60) as response:
                while True:
                    raw = response.readline(_MAX_PULL_LINE_BYTES + 1)
                    if not raw:
                        break
                    if len(raw) > _MAX_PULL_LINE_BYTES:
                        raise ValueError("Ollama progress event exceeded the size limit")
                    if not raw.strip():
                        continue
                    event = json.loads(raw.decode("utf-8"))
                    if not isinstance(event, Mapping):
                        raise ValueError("Ollama returned an invalid progress event")
                    if event.get("error"):
                        raise RuntimeError("Ollama reported a model download failure")
                    stage = event.get("status")
                    if not isinstance(stage, str) or len(stage) > 120:
                        raise ValueError("Ollama returned an invalid progress status")
                    total = event.get("total")
                    done = event.get("completed")
                    if (
                        isinstance(total, int)
                        and not isinstance(total, bool)
                        and total > 0
                        and isinstance(done, int)
                        and not isinstance(done, bool)
                        and done >= 0
                    ):
                        done = min(done, total)
                        percent = min(100, int(done * 100 / total))
                    else:
                        total = None
                        done = 0
                        percent = None
                    self._set_pull_state(
                        status="pulling",
                        specialist=specialist,
                        model=model,
                        message=stage,
                        completed=done,
                        total=total,
                        percent=percent,
                    )
                    if stage == "success":
                        completed_successfully = True
                        break
            if not completed_successfully:
                raise RuntimeError("Ollama download ended before completion")
        except Exception:
            self._set_pull_state(
                status="failed",
                specialist=specialist,
                model=model,
                message="Download failed. Check local Ollama and try again.",
                error="local_model_download_failed",
                completed=0,
                total=None,
                percent=None,
            )
            return
        self._set_pull_state(
            status="complete",
            specialist=specialist,
            model=model,
            message="Model is installed and ready.",
            completed=1,
            total=1,
            percent=100,
            error=None,
        )

    def _set_pull_state(self, **values: Any) -> None:
        with self._pull_lock:
            self._pull_state = {**self._pull_state, **values}

    def _installed_models(self) -> set[str] | None:
        payload = self._fetch_json("/api/tags")
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

    def _running_models(self) -> dict[str, dict[str, Any]] | None:
        payload = self._fetch_json("/api/ps")
        models = payload.get("models") if isinstance(payload, Mapping) else None
        if not isinstance(models, list):
            return None
        running: dict[str, dict[str, Any]] = {}
        for model in models:
            if not isinstance(model, Mapping):
                continue
            names = [model.get(key) for key in ("name", "model")]
            for name in names:
                if not isinstance(name, str):
                    continue
                details: dict[str, Any] = {}
                for key in ("size", "size_vram"):
                    value = model.get(key)
                    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
                        details[key] = value
                expires_at = model.get("expires_at")
                if isinstance(expires_at, str) and len(expires_at) <= 64:
                    details["expires_at"] = expires_at
                running[name] = details
        return running

    def _fetch_json(self, path: str) -> Any:
        if self.base_url is None:
            return None
        request = Request(
            self.base_url + path,
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
            return json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None
