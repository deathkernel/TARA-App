"""Inventory and explicitly requested downloads for local Ollama models."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from collections.abc import Mapping
from threading import Lock, RLock, Thread
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
        self._lifecycle_lock = Lock()
        self._startup_lock = RLock()
        self._pull_lock = Lock()
        self._ensure_lock = Lock()
        self._pull_state: dict[str, Any] = {"status": "idle"}
        self._managed_server: subprocess.Popen[bytes] | None = None
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

    def ensure_service_started(self, *, timeout_seconds: float = 30.0) -> bool:
        with self._startup_lock:
            return self._ensure_service_started_locked(timeout_seconds=timeout_seconds)

    def _ensure_service_started_locked(self, *, timeout_seconds: float = 30.0) -> bool:
        """Reuse local Ollama or start it for this TARA-App process.

        Returns True only when this instance launched the service. The app
        never stops an Ollama process that was already running independently.
        """
        if not self.profiles or self.base_url is None:
            return False
        if self._installed_models() is not None:
            return False

        executable = shutil.which("ollama")
        if executable is None:
            raise RuntimeError("Ollama is not available. Install it and make the ollama command available on PATH.")

        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
        try:
            process = subprocess.Popen(
                [executable, "serve"],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=creationflags,
                start_new_session=os.name != "nt",
            )
        except OSError as exc:
            raise RuntimeError("TARA-App could not start the local Ollama service") from exc

        self._managed_server = process
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            if self._installed_models() is not None:
                return True
            if process.poll() is not None:
                self.close()
                raise RuntimeError("The Ollama service exited before it became ready")
            time.sleep(0.25)

        self.close()
        raise RuntimeError("Ollama did not become ready within the startup timeout")

    def close(self) -> None:
        """Stop only an Ollama process that this TARA-App instance started."""
        with self._startup_lock:
            process = self._managed_server
            self._managed_server = None
            if process is None or process.poll() is not None:
                return
            try:
                process.terminate()
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
            except OSError:
                return

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

        self.ensure_service_started()
        with self._lifecycle_lock, self._pull_lock:
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

    def ensure_model_installed(self, specialist: Any, *, timeout_seconds: float = 3600.0) -> dict[str, str]:
        """Install the selected profile on demand and wait until it is ready."""
        if not isinstance(specialist, str) or specialist not in self.profiles:
            raise ValueError("specialist is not a configured local model profile")
        if self.base_url is None:
            raise RuntimeError("local Ollama is not configured")
        if (
            isinstance(timeout_seconds, bool)
            or not isinstance(timeout_seconds, (int, float))
            or not 1 <= timeout_seconds <= 7200
        ):
            raise ValueError("model install timeout is outside the allowed range")

        model = self.profiles[specialist]
        deadline = time.monotonic() + timeout_seconds
        with self._ensure_lock:
            self.ensure_service_started()
            while True:
                installed = self._installed_models()
                if installed is None:
                    raise RuntimeError("local Ollama is unavailable")
                if model in installed:
                    return {"status": "installed", "specialist": specialist, "model": model}
                if time.monotonic() >= deadline:
                    raise RuntimeError("waiting for a local model download timed out")

                pull = self.pull_status()
                if pull.get("status") in _ACTIVE_PULL_STATES:
                    time.sleep(min(0.25, max(0.0, deadline - time.monotonic())))
                    continue
                if pull.get("status") == "failed" and pull.get("model") == model:
                    raise RuntimeError("the selected local model could not be installed")
                try:
                    self.start_pull(specialist)
                    break
                except RuntimeError:
                    if self.pull_status().get("status") not in _ACTIVE_PULL_STATES:
                        raise

            while True:
                installed = self._installed_models()
                if installed is None:
                    raise RuntimeError("local Ollama became unavailable during model installation")
                if model in installed:
                    return {"status": "installed", "specialist": specialist, "model": model}

                pull = self.pull_status()
                if pull.get("status") == "failed" and pull.get("model") == model:
                    raise RuntimeError("the selected local model could not be installed")
                if time.monotonic() >= deadline:
                    raise RuntimeError("local model installation is still in progress")
                time.sleep(min(0.5, max(0.0, deadline - time.monotonic())))

    def pull_status(self) -> dict[str, Any]:
        with self._pull_lock:
            return dict(self._pull_state)

    def unload_model(self, specialist: Any) -> dict[str, str]:
        self.ensure_service_started()
        with self._lifecycle_lock:
            return self._unload_model_locked(specialist)

    def _unload_model_locked(self, specialist: Any) -> dict[str, str]:
        """Unload a configured running model from memory without deleting its files."""
        if not isinstance(specialist, str) or specialist not in self.profiles:
            raise ValueError("specialist is not a configured local model profile")
        if self.base_url is None:
            raise RuntimeError("local Ollama is not configured")
        if self.pull_status().get("status") in _ACTIVE_PULL_STATES:
            raise RuntimeError("wait for the active local model download before unloading")

        model = self.profiles[specialist]
        running = self._running_models()
        if running is None:
            raise RuntimeError("local Ollama running-model status is unavailable")
        if model not in running:
            return {"status": "not_loaded", "specialist": specialist, "model": model}

        request = Request(
            self.base_url + "/api/generate",
            data=json.dumps(
                {"model": model, "prompt": "", "stream": False, "keep_alive": 0},
                separators=(",", ":"),
            ).encode("utf-8"),
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )
        try:
            with build_opener(ProxyHandler({}), _NoRedirect()).open(request, timeout=30) as response:
                raw = response.read(_MAX_RESPONSE_BYTES + 1)
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            raise RuntimeError("local Ollama could not unload the configured model") from exc
        if len(raw) > _MAX_RESPONSE_BYTES:
            raise RuntimeError("local Ollama returned an oversized unload response")
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RuntimeError("local Ollama returned an invalid unload response") from exc
        if not isinstance(payload, Mapping) or payload.get("done") is not True:
            raise RuntimeError("local Ollama did not confirm the model unload")
        return {"status": "unloaded", "specialist": specialist, "model": model}

    def preload_model(self, specialist: Any, *, keep_alive: str = "15m") -> dict[str, str]:
        """Load an installed local model before the first user request."""
        if not isinstance(specialist, str) or specialist not in self.profiles:
            raise ValueError("specialist is not a configured local model profile")
        if self.base_url is None:
            raise RuntimeError("local Ollama is not configured")
        if keep_alive not in {"5m", "10m", "15m", "30m"}:
            raise ValueError("keep_alive is outside the supported warm-up options")
        self.ensure_service_started()
        model = self.profiles[specialist]
        installed = self._installed_models()
        if installed is None or model not in installed:
            raise RuntimeError("the configured local model is not installed")
        request = Request(
            self.base_url + "/api/generate",
            data=json.dumps(
                {"model": model, "prompt": "", "stream": False, "keep_alive": keep_alive},
                separators=(",", ":"),
            ).encode("utf-8"),
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )
        try:
            with build_opener(ProxyHandler({}), _NoRedirect()).open(request, timeout=300) as response:
                raw = response.read(_MAX_RESPONSE_BYTES + 1)
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            raise RuntimeError("local Ollama could not warm the configured model") from exc
        if len(raw) > _MAX_RESPONSE_BYTES:
            raise RuntimeError("local Ollama returned an oversized warm-up response")
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RuntimeError("local Ollama returned an invalid warm-up response") from exc
        if not isinstance(payload, Mapping) or payload.get("done") is not True:
            raise RuntimeError("local Ollama did not confirm the model warm-up")
        return {"status": "ready", "specialist": specialist, "model": model}

    def remove_model(self, specialist: Any) -> dict[str, str]:
        self.ensure_service_started()
        with self._lifecycle_lock:
            return self._remove_model_locked(specialist)

    def _remove_model_locked(self, specialist: Any) -> dict[str, str]:
        """Remove a configured, installed model after it has been unloaded."""
        if not isinstance(specialist, str) or specialist not in self.profiles:
            raise ValueError("specialist is not a configured local model profile")
        if self.base_url is None:
            raise RuntimeError("local Ollama is not configured")
        if self.pull_status().get("status") in _ACTIVE_PULL_STATES:
            raise RuntimeError("wait for the active local model download before removing files")

        model = self.profiles[specialist]
        installed = self._installed_models()
        if installed is None:
            raise RuntimeError("local Ollama installed-model status is unavailable")
        if model not in installed:
            return {"status": "not_installed", "specialist": specialist, "model": model}
        running = self._running_models()
        if running is None:
            raise RuntimeError("local Ollama running-model status is unavailable")
        if model in running:
            raise RuntimeError("unload the configured model before removing its files")

        request = Request(
            self.base_url + "/api/delete",
            data=json.dumps({"model": model}, separators=(",", ":")).encode("utf-8"),
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="DELETE",
        )
        try:
            with build_opener(ProxyHandler({}), _NoRedirect()).open(request, timeout=30) as response:
                raw = response.read(_MAX_RESPONSE_BYTES + 1)
                status_code = response.status
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            raise RuntimeError("local Ollama could not remove the configured model") from exc
        if status_code not in {200, 204} or len(raw) > _MAX_RESPONSE_BYTES:
            raise RuntimeError("local Ollama returned an invalid model-removal response")
        if raw:
            try:
                payload = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise RuntimeError("local Ollama returned an invalid model-removal response") from exc
            if not isinstance(payload, Mapping) or payload.get("status") not in (None, "success"):
                raise RuntimeError("local Ollama did not confirm model removal")
        return {"status": "removed", "specialist": specialist, "model": model}

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
