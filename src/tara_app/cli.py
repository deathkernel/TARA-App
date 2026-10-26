"""Command-line entry point for the local TARA-App interface."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from tara_app.runtime import RuntimeConfigurationError, create_application
from tara_app.webapp import serve


def main() -> int:
    parser = argparse.ArgumentParser(prog="tara-app", description="Run the local TARA-App chat interface")
    parser.add_argument("--config", type=Path, default=Path("tara-app.toml"), help="path to trusted TARA-App TOML configuration")
    parser.add_argument("--port", type=int, default=8765, help="loopback web port (1024-65535)")
    args = parser.parse_args()
    app = None
    try:
        app = create_application(args.config)
        if app.model_catalog is not None:
            app.model_catalog.ensure_service_started()
        serve(app, port=args.port)
    except (RuntimeConfigurationError, OSError, RuntimeError, ValueError) as exc:
        print(f"TARA-App could not start: {exc}", file=sys.stderr)
        return 2
    finally:
        if app is not None and app.model_catalog is not None:
            app.model_catalog.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

