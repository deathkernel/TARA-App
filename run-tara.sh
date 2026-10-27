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
if ".venv/bin/python" -c "import sys; raise SystemExit(0 if sys.version_info < (3, 15) else 1)"; then
  if ! ".venv/bin/python" -m pip install -e ".[voice]"; then
    echo "Voice transcription dependencies could not be installed; TARA-App will continue without them."
  fi
else
  echo "Skipping optional Voice transcription dependencies on Python 3.15 or newer."
fi
if [ ! -f "tara-app.toml" ]; then
  cp "tara-app.example.toml" "tara-app.toml"
fi

".venv/bin/python" -m tara_app.handler_launcher prepare
exec ".venv/bin/python" -m tara_app --config "tara-app.toml"
