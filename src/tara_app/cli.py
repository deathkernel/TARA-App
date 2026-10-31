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
    parser.add_argument(
        "--floating-pet",
        action="store_true",
        help="show the native Windows floating pet instead of the browser interface",
    )
    args = parser.parse_args()
    app = None
    try:
        if args.floating_pet and sys.platform != "win32":
            raise RuntimeConfigurationError("--floating-pet is supported on Windows only")
        app = create_application(args.config)
        if app.model_catalog is not None:
            app.model_catalog.ensure_service_started()
            if "chat" in app.model_catalog.profiles:
                print("Preparing TARA's local chat model before the app opens.", flush=True)
                try:
                    app.model_catalog.ensure_model_installed("chat")
                    app.model_catalog.preload_model("chat", keep_alive="15m")
                    print("TARA's chat model is ready.", flush=True)
                except RuntimeError:
                    print("TARA-App will start, but the chat model could not be prepared. Check the Models panel.", file=sys.stderr, flush=True)
        if args.floating_pet:
            from tara_app.windows_pet import run_floating_pet
            run_floating_pet(app, port=args.port)
        else:
            serve(app, port=args.port)
    except (RuntimeConfigurationError, OSError, RuntimeError, ValueError) as exc:
        print(f"TARA-App could not start: {exc}", file=sys.stderr)
        return 2
    finally:
        if app is not None:
            app.shutdown()
            if app.model_catalog is not None:
                app.model_catalog.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
