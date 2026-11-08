"""One-request JSON-over-stdio adapter for TARA."""
from __future__ import annotations

from tara_app.stdio_runner import run_module
from .service import MODULE_ID, execute


def main() -> int:
    return run_module(MODULE_ID, execute)


if __name__ == "__main__":
    raise SystemExit(main())
