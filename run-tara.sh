#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")"

if ! command -v python3 >/dev/null 2>&1; then
  echo "SITA requires Python 3.11 or newer."
  exit 1
fi

if [ ! -x ".venv/bin/python" ]; then
  python3 -m venv .venv
fi

".venv/bin/python" -m pip install -e .
if ".venv/bin/python" -c "import sys; raise SystemExit(0 if sys.version_info < (3, 15) else 1)"; then
  if ! ".venv/bin/python" -m pip install -e ".[voice]"; then
    echo "Voice transcription dependencies could not be installed; SITA will continue without them."
  fi
else
  echo "Skipping optional Voice transcription dependencies on Python 3.15 or newer."
fi
# Build the premium React workspace when Node.js is available.
# The Python app retains its static UI fallback if the optional build cannot run.
if command -v npm >/dev/null 2>&1; then
  cd frontend
  if [ ! -x "node_modules/.bin/vite" ]; then
    if ! npm install --no-audit --no-fund; then
      echo "React dependencies could not be installed; using the static UI fallback."
    fi
  fi
  if [ -x "node_modules/.bin/vite" ]; then
    if ! npm run build; then
      echo "React workspace build failed; using the last available build or static UI fallback."
    fi
  fi
  cd ..
else
  echo "Node.js/npm is unavailable; using the bundled static UI fallback."
fi

if [ ! -f "tara-app.toml" ]; then
  cp "tara-app.example.toml" "tara-app.toml"
fi

".venv/bin/python" -m tara_app.handler_launcher prepare
exec ".venv/bin/python" -m tara_app --config "tara-app.toml"
