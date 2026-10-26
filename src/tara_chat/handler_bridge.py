"""Safe, opt-in integration with the native TARA-Handler CLI.

TARA remains a conversational assistant. Handler performs deterministic inspection
and applies its own policy/confirmation checks. This bridge deliberately exposes
only read-only diagnostic commands; repair and mutation commands are not available
through natural-language tool dispatch.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


# Exact command allowlist. Never accept an executable or arbitrary CLI arguments
# from the model/user.
_READ_ONLY_COMMANDS: dict[str, tuple[str, ...]] = {
    "health": ("health",),
    "self-check": ("self-check",),
    "doctor": ("doctor",),
    "discover": ("discover",),
    "project": ("project",),
    "deps": ("deps",),
    "graph": ("graph",),
    "path-audit": ("path-audit",),
    "protect": ("protect",),
    "updates": ("updates",),
    "version": ("version",),
    "status": ("status",),
    "history": ("history",),
    "snapshots": ("snapshots",),
    "modules": ("modules",),
}


@dataclass(frozen=True)
class HandlerResult:
    ok: bool
    command: str
    output: str
    returncode: int | None = None


class HandlerUnavailable(RuntimeError):
    """Raised when the Handler executable cannot be resolved or safely run."""


class TARAHandler:
    """Call an installed/built Handler executable through a narrow read-only API."""

    def __init__(
        self,
        executable: str | os.PathLike[str] | None = None,
        *,
        timeout_seconds: int = 30,
        working_directory: str | os.PathLike[str] | None = None,
    ) -> None:
        if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, int) or not 1 <= timeout_seconds <= 120:
            raise ValueError("timeout_seconds must be an integer between 1 and 120")
        configured = str(executable or os.getenv("TARA_HANDLER_EXECUTABLE", "")).strip()
        self.executable = self._resolve_executable(configured)
        self.timeout_seconds = timeout_seconds
        self.working_directory = Path(working_directory or os.getcwd()).resolve()

    @staticmethod
    def _resolve_executable(configured: str) -> str:
        candidates: list[str] = []
        if configured:
            candidates.append(configured)
        # Optional local build layouts, then PATH. No silent download/install.
        root = Path(__file__).resolve().parent.parent
        names = ("handler.exe", "handler") if os.name == "nt" else ("handler", "handler.exe")
        for relative in ("TARA-Handler/build/Release", "TARA-Handler/build", "../TARA-Handler/build/Release", "../TARA-Handler/build"):
            for name in names:
                candidates.append(str((root / relative / name).resolve()))
        for candidate in candidates:
            path = Path(candidate).expanduser()
            if path.is_file():
                return str(path.resolve())
            if os.name == "nt" and path.suffix.lower() == ".cmd":
                continue
            located = shutil.which(candidate) if not Path(candidate).is_absolute() else None
            if located:
                return str(Path(located).resolve())
        located = shutil.which("handler.exe" if os.name == "nt" else "handler")
        if located:
            return str(Path(located).resolve())
        raise HandlerUnavailable(
            "TARA-Handler executable not found. Build TARA-Handler with CMake, "
            "then set TARA_HANDLER_EXECUTABLE to the handler executable path."
        )

    @staticmethod
    def available_commands() -> tuple[str, ...]:
        return tuple(sorted(_READ_ONLY_COMMANDS))

    def run(self, action: str) -> HandlerResult:
        """Run one fixed, read-only Handler action; no free-form arguments accepted."""
        if not isinstance(action, str) or action not in _READ_ONLY_COMMANDS:
            raise ValueError(
                "Unsupported Handler action. Allowed actions: "
                + ", ".join(self.available_commands())
            )
        argv: Sequence[str] = (self.executable, *_READ_ONLY_COMMANDS[action])
        try:
            completed = subprocess.run(
                list(argv),
                cwd=str(self.working_directory),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self.timeout_seconds,
                shell=False,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            partial = exc.stdout or ""
            if isinstance(partial, bytes):
                partial = partial.decode("utf-8", errors="replace")
            return HandlerResult(False, action, f"Handler timed out after {self.timeout_seconds}s.\n{partial}", None)
        except OSError as exc:
            raise HandlerUnavailable(f"Could not start Handler: {exc}") from exc
        output = completed.stdout.strip()
        return HandlerResult(completed.returncode == 0, action, output, completed.returncode)


def handler_from_env() -> TARAHandler:
    """Construct the optional bridge. Raises HandlerUnavailable when not installed."""
    return TARAHandler()
