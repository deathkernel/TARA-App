#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")"

if ! command -v python3 >/dev/null 2>&1; then
  echo "TARA-App requires Python 3.11 or newer."
  exit 1
fi

if [ ! -x ".venv/bin/python" ]; then
  python3 -m venv .venv
fi

".venv/bin/python" -m pip install -e .
if [ ! -f "tara-app.toml" ]; then
  cp "tara-app.example.toml" "tara-app.toml"
fi

".venv/bin/python" -m tara_app.handler_launcher prepare
exec ".venv/bin/python" -m tara_app --config "tara-app.toml"
