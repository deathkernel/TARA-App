"""Build and run TARA-Handler diagnostics on demand, with a local fallback."""

from __future__ import annotations

import hashlib
import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

_SOURCE = Path(__file__).resolve().parent / "native" / "handler"
_BUILD_TIMEOUT_SECONDS = 80


def _cache_root() -> Path:
    if os.name == "nt":
        root = os.environ.get("LOCALAPPDATA")
        if root:
            return Path(root) / "TARA" / "cache" / "handler"
    root = os.environ.get("XDG_CACHE_HOME")
    return Path(root) / "tara" / "handler" if root else Path.home() / ".cache" / "tara" / "handler"


def _source_files() -> list[Path]:
    if not _SOURCE.is_dir():
        return []
    return sorted(
        path for path in _SOURCE.rglob("*")
        if path.is_file() and path.suffix in {".cpp", ".h", ".txt"}
    )


def _fingerprint(paths: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in paths:
        digest.update(path.relative_to(_SOURCE).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _binary_path(build_dir: Path) -> Path:
    name = "tara-handler.exe" if os.name == "nt" else "tara-handler"
    return build_dir / "bin" / name


def _cached_native() -> Path | None:
    paths = _source_files()
    if not paths:
        return None
    build_dir = _cache_root()
    binary = _binary_path(build_dir)
    manifest = build_dir / "source.sha256"
    try:
        if binary.is_file() and manifest.read_text("ascii", errors="ignore").strip() == _fingerprint(paths):
            return binary
    except OSError:
        pass
    return None


def _build_native() -> Path | None:
    cmake = shutil.which("cmake")
    source_files = _source_files()
    if not cmake or not source_files or not (_SOURCE / "CMakeLists.txt").is_file():
        return None

    build_dir = _cache_root()
    try:
        build_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        return None
    fingerprint = _fingerprint(source_files)
    binary = _binary_path(build_dir)
    manifest = build_dir / "source.sha256"

    if binary.is_file() and manifest.is_file() and manifest.read_text("ascii", errors="ignore").strip() == fingerprint:
        return binary

    lock = build_dir / "build.lock"
    deadline = time.monotonic() + _BUILD_TIMEOUT_SECONDS
    while True:
        try:
            descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.close(descriptor)
            break
        except FileExistsError:
            if binary.is_file() and manifest.is_file() and manifest.read_text("ascii", errors="ignore").strip() == fingerprint:
                return binary
            if time.monotonic() >= deadline:
                return None
            time.sleep(0.25)
        except OSError:
            return None

    try:
        if binary.is_file() and manifest.is_file() and manifest.read_text("ascii", errors="ignore").strip() == fingerprint:
            return binary
        configure = subprocess.run(
            [cmake, "-S", str(_SOURCE), "-B", str(build_dir), "-DCMAKE_BUILD_TYPE=Release"],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if configure.returncode != 0:
            return None
        build = subprocess.run(
            [cmake, "--build", str(build_dir), "--config", "Release", "--target", "tara-handler", "--parallel", "2"],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=_BUILD_TIMEOUT_SECONDS,
            check=False,
        )
        if build.returncode != 0 or not binary.is_file():
            return None
        manifest.write_text(fingerprint + "\n", encoding="ascii")
        return binary
    except (OSError, subprocess.TimeoutExpired):
        return None
    finally:
        try:
            lock.unlink()
        except OSError:
            pass


def _python_diagnostic() -> int:
    print("TARA-Handler read-only diagnosis (Python fallback)")
    print(f"Operating system: {platform_name()}")
    print(f"Python: {sys.version.split()[0]}")
    print("\nToolchain:")
    for tool in ("python", "node", "git", "cmake", "dotnet", "java", "go", "cargo"):
        path = shutil.which(tool)
        print(f"  [{'OK' if path else 'MISSING'}] {tool}: {path or 'not found'}")
    print("\nPorts:")
    for port in (3000, 5000, 8000, 8080):
        probe = socket.socket()
        probe.settimeout(0.15)
        try:
            busy = probe.connect_ex(("127.0.0.1", port)) == 0
        except OSError:
            busy = False
        finally:
            probe.close()
        print(f"  [{'BUSY' if busy else 'FREE'}] {port}")
    markers = ("pyproject.toml", "package.json", "Cargo.toml", "CMakeLists.txt", ".git")
    project = next((parent for parent in (Path.cwd(), *Path.cwd().parents) if any((parent / marker).exists() for marker in markers)), None)
    print(f"\nProject: {project if project else 'not detected'}")
    return 0


def platform_name() -> str:
    import platform
    return f"{platform.system()} {platform.release()}"


def main() -> int:
    arguments = sys.argv[1:]
    if len(arguments) != 1 or arguments[0] not in {"doctor", "health", "prepare"}:
        print("Usage: python -m tara_app.handler_launcher doctor|health|prepare", file=sys.stderr)
        return 2
    if arguments[0] == "health":
        print("available (native Handler when prepared; otherwise read-only Python fallback)")
        return 0
    if arguments[0] == "prepare":
        print("Preparing the optional native TARA-Handler diagnostic...")
        binary = _build_native()
        print("Native Handler is ready." if binary else "Native Handler could not be prepared; read-only Python diagnosis remains available.")
        return 0
    binary = _cached_native()
    if binary is not None:
        try:
            completed = subprocess.run(
                [str(binary), "doctor"],
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            if completed.returncode == 0:
                sys.stdout.write(completed.stdout)
                if completed.stderr:
                    sys.stdout.write(completed.stderr)
                return 0
        except (OSError, subprocess.TimeoutExpired):
            pass
    print("Native C++ Handler is not prepared or unavailable; using read-only Python diagnosis.")
    return _python_diagnostic()


if __name__ == "__main__":
    raise SystemExit(main())
