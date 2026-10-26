"""Restricted stdio adapter for the separate TARA-Router package."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Mapping, Sequence

from tara_app.contracts import MAX_PAYLOAD_BYTES, RouteDecision


class RouterUnavailableError(RuntimeError):
    """Raised when TARA-Router cannot safely return a route decision."""


class StdioRouterClient:
    """Invoke a trusted, configured Router command without a shell or secrets."""

    def __init__(
        self,
        command: Sequence[str],
        *,
        working_directory: str | Path,
        timeout_seconds: int = 10,
        max_response_bytes: int = 64_000,
    ) -> None:
        if isinstance(command, (str, bytes)) or not command or any(not isinstance(arg, str) or not arg or "\x00" in arg for arg in command):
            raise ValueError("command must be a non-empty sequence of safe argument strings")
        if not 1 <= timeout_seconds <= 60:
            raise ValueError("timeout_seconds must be between 1 and 60")
        if not 256 <= max_response_bytes <= 1_000_000:
            raise ValueError("max_response_bytes must be between 256 and 1000000")
        self.command = tuple(command)
        self.working_directory = Path(working_directory).expanduser().resolve(strict=True)
        if not self.working_directory.is_dir():
            raise ValueError("working_directory must be an existing directory")
        self.timeout_seconds = timeout_seconds
        self.max_response_bytes = max_response_bytes

    def route(self, request_payload: Mapping[str, object]) -> RouteDecision:
        try:
            encoded = json.dumps(dict(request_payload), ensure_ascii=False, separators=(",", ":"))
        except (TypeError, ValueError) as exc:
            raise RouterUnavailableError("routing request is not valid JSON") from exc
        if len(encoded.encode("utf-8")) > MAX_PAYLOAD_BYTES:
            raise RouterUnavailableError("routing request exceeds the size limit")

        try:
            completed = subprocess.run(
                self.command,
                input=encoded,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                cwd=self.working_directory,
                env=self._safe_environment(),
                timeout=self.timeout_seconds,
                shell=False,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise RouterUnavailableError("TARA-Router process is unavailable or timed out") from exc

        if completed.returncode != 0:
            raise RouterUnavailableError("TARA-Router returned a failure status")
        if len(completed.stdout.encode("utf-8")) > self.max_response_bytes:
            raise RouterUnavailableError("TARA-Router response exceeds the size limit")
        try:
            payload = json.loads(completed.stdout)
            return RouteDecision.from_payload(payload)
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            raise RouterUnavailableError("TARA-Router returned an invalid response") from exc

    @staticmethod
    def _safe_environment() -> dict[str, str]:
        environment = {
            "PATH": os.environ.get("PATH", ""),
            "PYTHONIOENCODING": "utf-8",
        }
        if os.name == "nt":
            for name in ("SYSTEMROOT", "WINDIR", "TEMP", "TMP"):
                value = os.environ.get(name)
                if value:
                    environment[name] = value
        return environment
