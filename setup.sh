#!/usr/bin/env bash
# setup.sh — Create a virtual environment and install perido in editable mode.
#
# Handles the macOS UF_HIDDEN flag issue where iCloud Drive's File Provider
# daemon applies the hidden flag to .venv files, causing Python's site module
# to skip .pth files and breaking the editable install.
#
# Usage:
#   chmod +x setup.sh
#   ./setup.sh

set -euo pipefail

PYTHON="${PYTHON:-python3}"

# ---------------------------------------------------------------------------
# Colour helpers (disabled when stdout is not a TTY)
# ---------------------------------------------------------------------------
if [ -t 1 ]; then
    RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[0;33m'; NC='\033[0m'
else
    RED=''; GREEN=''; YELLOW=''; NC=''
fi

info()  { printf "${GREEN}▸${NC} %s\n" "$*"; }
warn()  { printf "${YELLOW}▸${NC} %s\n" "$*"; }
error() { printf "${RED}▸${NC} %s\n" "$*" >&2; }

# ---------------------------------------------------------------------------
# Check for Python 3.10+
# ---------------------------------------------------------------------------
if ! command -v "$PYTHON" &>/dev/null; then
    error "$PYTHON not found. Install Python 3.10+ and try again."
    exit 1
fi

PY_VERSION=$("$PYTHON" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PY_MAJOR=$("$PYTHON" -c "import sys; print(sys.version_info.major)")
PY_MINOR=$("$PYTHON" -c "import sys; print(sys.version_info.minor)")

if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 10 ]; }; then
    error "Python 3.10+ required (found $PY_VERSION)."
    exit 1
fi

info "Using Python $PY_VERSION ($PYTHON)"

# ---------------------------------------------------------------------------
# Create virtual environment
# ---------------------------------------------------------------------------
if [ -d .venv ]; then
    warn ".venv already exists — skipping creation."
else
    info "Creating virtual environment..."
    "$PYTHON" -m venv .venv
fi

# ---------------------------------------------------------------------------
# Activate
# ---------------------------------------------------------------------------
# shellcheck source=/dev/null
source .venv/bin/activate

# ---------------------------------------------------------------------------
# Install perido in editable mode
# ---------------------------------------------------------------------------
info "Installing perido in editable mode..."
pip install -e . --quiet

# ---------------------------------------------------------------------------
# Fix macOS UF_HIDDEN flag (iCloud Drive / File Provider)
# ---------------------------------------------------------------------------
if command -v chflags &>/dev/null; then
    # chflags is macOS-only; silently skip on Linux.
    HIDDEN_COUNT=$(find .venv -flags +hidden 2>/dev/null | wc -l | tr -d ' ')
    if [ "$HIDDEN_COUNT" -gt 0 ]; then
        info "Removing macOS UF_HIDDEN flag from $HIDDEN_COUNT files (iCloud fix)..."
        chflags -R nohidden .venv
    fi
fi

# ---------------------------------------------------------------------------
# Verify
# ---------------------------------------------------------------------------
if perido --version &>/dev/null; then
    info "Installation successful: $(perido --version)"
else
    error "Installation completed but 'perido --version' failed."
    error "Try: chflags -R nohidden .venv  (macOS only)"
    exit 1
fi

echo ""
info "Activate the environment with:  source .venv/bin/activate"
