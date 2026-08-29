#!/usr/bin/env bash
# Workspace setup: virtualenv + editable install of the perido CLI.
# Idempotent and safe to re-run.
set -euo pipefail

cd "$(dirname "$0")/.."

PYTHON="${PYTHON:-python3}"
command -v "$PYTHON" >/dev/null 2>&1 || PYTHON=python3

if [ ! -x .venv/bin/python ]; then
  echo "Creating .venv with $PYTHON..."
  "$PYTHON" -m venv .venv
fi

echo "Installing perido (editable)..."
.venv/bin/pip install --quiet -e . -r requirements.txt

echo "Verifying install..."
.venv/bin/perido --version
echo "Setup complete."
