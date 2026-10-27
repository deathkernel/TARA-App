"""Restricted JSON-over-stdio client for independently packaged modules."""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Mapping, Sequence

from tara_app.contracts import AdapterHealth, Capability, MAX_PAYLOAD_BYTES, ModuleRequest, ModuleResult, SCHEMA_VERSION

_ENV_NAME = re.compile(r"^[A-Z][A-Z0-9_]{0,127}$")
_RESULT_FIELDS = {"schema_version", "request_id", "status", "data", "error", "duration_ms"}


class ModuleProcessError(RuntimeError):
    """Raised when a trusted module process violates the adapter protocol."""


class StdioModuleAdapter:
    """Run one module command per request with bounded input and output.

    Command arguments, working directory, and environment values come from
    trusted application configuration. Request data never changes the command
    or environment and is never interpolated into a shell command.
    """

    def __init__(
        self,
        module_id: str,
        capabilities: Sequence[Capability],
        command: Sequence[str],
        *,
        working_directory: str | Path,
        timeout_seconds: int = 30,
        max_response_bytes: int = 1_000_000,
        environment: Mapping[str, str] | None = None,
    ) -> None:
        if not isinstance(module_id, str) or not module_id:
            raise ValueError("module_id must be non-empty")
        if isinstance(command, (str, bytes)) or not command or any(not isinstance(arg, str) or not arg or "\x00" in arg for arg in command):
            raise ValueError("command must be a non-empty sequence of safe argument strings")
        if not 1 <= timeout_seconds <= 600:
            raise ValueError("timeout_seconds must be between 1 and 600")
        if not 256 <= max_response_bytes <= MAX_PAYLOAD_BYTES:
            raise ValueError("max_response_bytes is outside the allowed range")
        if not capabilities or any(cap.module_id != module_id for cap in capabilities):
            raise ValueError("capabilities must belong to module_id")
        self.module_id = module_id
        self.capabilities = tuple(capabilities)
        self.command = tuple(command)
        self.working_directory = Path(working_directory).expanduser().resolve(strict=True)
        if not self.working_directory.is_dir():
            raise ValueError("working_directory must be an existing directory")
        self.timeout_seconds = timeout_seconds
        self.max_response_bytes = max_response_bytes
        self.environment = dict(environment or {})
        for name, value in self.environment.items():
            if not _ENV_NAME.fullmatch(name) or not isinstance(value, str) or "\x00" in value or len(value) > 4096:
                raise ValueError("module environment contains an invalid entry")

    def health(self) -> AdapterHealth:
        payload = {
            "schema_version": SCHEMA_VERSION,
            "request_id": "tara-health-check",
            "session_id": "tara-health-check",
            "module": self.module_id,
            "action": "health",
            "inputs": {},
            "timeout_seconds": min(self.timeout_seconds, 10),
            "workspace_root": None,
            "approval_token": None,
        }
        try:
            response = self._invoke(payload, timeout=min(self.timeout_seconds, 10), request_id="tara-health-check")
            if response.status != "success" or response.data.get("healthy") is not True:
                return AdapterHealth("unavailable", "module health check did not succeed")
            return AdapterHealth("healthy")
        except (ModuleProcessError, OSError, subprocess.TimeoutExpired):
            return AdapterHealth("unavailable", "module process did not pass its health check")

    def execute(self, request: ModuleRequest) -> ModuleResult:
        if request.module != self.module_id:
            return ModuleResult("permission_denied", error="request module does not match this adapter")
        capability = next((cap for cap in self.capabilities if cap.action == request.action), None)
        if capability is None:
            return ModuleResult("permission_denied", error="action is not registered for this module")
        if capability.requires_approval and not request.approval_token:
            return ModuleResult("approval_required", error="capability requires an approval token")
        if not capability.read_only and not request.approval_token:
            return ModuleResult("approval_required", error="side-effecting capability requires an approval token")
        return self._invoke(request.to_payload(), timeout=min(self.timeout_seconds, request.timeout_seconds), request_id=request.request_id)

    def _invoke(self, payload: Mapping[str, object], *, timeout: int, request_id: str | None = None) -> ModuleResult:
        try:
            encoded = json.dumps(dict(payload), ensure_ascii=False, separators=(",", ":"))
        except (TypeError, ValueError) as exc:
            raise ModuleProcessError("module request is not valid JSON") from exc
        if len(encoded.encode("utf-8")) > MAX_PAYLOAD_BYTES:
            raise ModuleProcessError("module request exceeds the payload limit")
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
                timeout=timeout,
                shell=False,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ModuleProcessError("module process is unavailable or timed out") from exc
        if completed.returncode != 0:
            raise ModuleProcessError("module process returned a failure status")
        output = completed.stdout.encode("utf-8")
        if len(output) > self.max_response_bytes:
            raise ModuleProcessError("module response exceeds the configured limit")
        try:
            response = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise ModuleProcessError("module returned malformed JSON") from exc
        if not isinstance(response, dict) or set(response) - _RESULT_FIELDS:
            raise ModuleProcessError("module response has an invalid shape")
        if response.get("schema_version") != SCHEMA_VERSION:
            raise ModuleProcessError("module response has an unsupported schema version")
        if request_id is not None and response.get("request_id") != request_id:
            raise ModuleProcessError("module response request ID did not match")
        try:
            return ModuleResult(
                schema_version=response["schema_version"],
                status=response["status"],
                data=response.get("data", {}),
                error=response.get("error"),
                duration_ms=response.get("duration_ms", 0),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ModuleProcessError("module response failed contract validation") from exc

    def _safe_environment(self) -> dict[str, str]:
        environment = {"PATH": os.environ.get("PATH", ""), "PYTHONIOENCODING": "utf-8"}
        if os.name == "nt":
            for name in ("SYSTEMROOT", "WINDIR", "TEMP", "TMP"):
                value = os.environ.get(name)
                if value:
                    environment[name] = value
        environment.update(self.environment)
        return environment

