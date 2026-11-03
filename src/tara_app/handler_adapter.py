"""Narrow wrapper for TARA-Handler's read-only doctor command."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Mapping, Sequence

from tara_app.contracts import AdapterHealth, Capability, ModuleRequest, ModuleResult

_ENV_NAME = re.compile(r"^[A-Z][A-Z0-9_]{0,127}$")


class HandlerProcessAdapter:
    """Call one configured Handler diagnostic command without passing prompt data."""

    module_id = "handler"

    def __init__(
        self,
        command: Sequence[str],
        *,
        working_directory: str | Path,
        timeout_seconds: int = 30,
        max_response_bytes: int = 256_000,
        environment: Mapping[str, str] | None = None,
    ) -> None:
        if isinstance(command, (str, bytes)) or not command or any(not isinstance(arg, str) or not arg or "\x00" in arg for arg in command):
            raise ValueError("Handler command must be a non-empty argument list")
        packaged_launcher = (
            len(command) == 4
            and command[1:3] == ("-m", "tara_app.handler_launcher")
            and command[3].casefold() in {"doctor", "health"}
        )
        direct_diagnostic = len(command) == 2 and command[1].casefold() in {"doctor", "health"}
        if not (packaged_launcher or direct_diagnostic):
            raise ValueError("Handler adapter only permits the packaged launcher or a doctor/health command")
        if not 1 <= timeout_seconds <= 120 or not 256 <= max_response_bytes <= 1_000_000:
            raise ValueError("Handler timeout or response limit is outside the allowed range")
        self.command = tuple(command)
        self.working_directory = Path(working_directory).expanduser().resolve(strict=True)
        if not self.working_directory.is_dir():
            raise ValueError("Handler working_directory must be an existing directory")
        self.timeout_seconds = timeout_seconds
        self.max_response_bytes = max_response_bytes
        self.environment = dict(environment or {})
        for name, value in self.environment.items():
            if not _ENV_NAME.fullmatch(name) or not isinstance(value, str) or "\x00" in value or len(value) > 4096:
                raise ValueError("Handler environment contains an invalid value")

    @property
    def capabilities(self) -> tuple[Capability, ...]:
        return (Capability("handler", "diagnose", "Inspect the local developer environment", True),)

    def health(self) -> AdapterHealth:
        executable = Path(self.command[0])
        if not executable.is_absolute() and (self.working_directory / executable).is_file():
            return AdapterHealth("healthy")
        if executable.is_file() or shutil.which(self.command[0], path=os.environ.get("PATH", "")):
            return AdapterHealth("healthy")
        return AdapterHealth("unavailable", "configured Handler executable is not available")

    def execute(self, request: ModuleRequest) -> ModuleResult:
        if request.module != self.module_id or request.action != "diagnose":
            return ModuleResult("permission_denied", error="Handler adapter only permits read-only diagnostics")
        try:
            completed = subprocess.run(
                self.command,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                cwd=self.working_directory,
                env=self._safe_environment(),
                timeout=min(self.timeout_seconds, request.timeout_seconds),
                shell=False,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return ModuleResult("timeout", error="TARA-Handler diagnostic timed out")
        except OSError:
            return ModuleResult("unavailable", error="configured TARA-Handler command could not start")
        output = (completed.stdout + completed.stderr).strip()
        if len(output.encode("utf-8")) > self.max_response_bytes:
            return ModuleResult("failed", error="TARA-Handler output exceeds the configured size limit")
        if completed.returncode != 0:
            return ModuleResult("failed", {"text": output[:20_000], "exit_code": completed.returncode}, "TARA-Handler diagnostic returned a failure status")
        return ModuleResult("success", {"text": output[:20_000], "exit_code": 0})

    def _safe_environment(self) -> dict[str, str]:
        environment = {"PATH": os.environ.get("PATH", ""), "PYTHONIOENCODING": "utf-8"}
        inherited = ("SYSTEMROOT", "WINDIR", "TEMP", "TMP", "USERPROFILE", "APPDATA", "LOCALAPPDATA", "PROGRAMDATA", "HOME", "XDG_STATE_HOME", "TMPDIR")
        for name in inherited:
            value = os.environ.get(name)
            if value:
                environment[name] = value
        environment.update(self.environment)
        return environment

