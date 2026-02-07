#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────
#  AutoAvenue Scraper — One-time project setup
# ──────────────────────────────────────────────────────────────────
#  Usage:  bash scripts/setup.sh
#
#  What it does:
#    1. Creates Python venv in backend/.venv
#    2. Installs backend deps + Playwright Chromium
#    3. Installs frontend deps (npm)
#    4. Copies .env.example → .env (if .env doesn't exist)
#    5. Initializes the SQLite database
#
#  After running:
#    make dev          # start both servers
#    make dev-back     # backend only
#    make dev-front    # frontend only
# ──────────────────────────────────────────────────────────────────

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"
VENV="$BACKEND/.venv"

echo ""
echo "  ╔══════════════════════════════════════════╗"
echo "  ║  AutoAvenue Scraper — Project Setup      ║"
echo "  ╚══════════════════════════════════════════╝"
echo ""

# ── 1. Environment file ─────────────────────────────────────────
if [ ! -f "$ROOT/.env" ]; then
    cp "$ROOT/.env.example" "$ROOT/.env"
    echo "  ✅  Created .env from .env.example"
else
    echo "  ⏭   .env already exists (skipped)"
fi

# ── 2. Python virtual environment ───────────────────────────────
echo ""
echo "  📦  Setting up Python environment..."
if [ ! -d "$VENV" ]; then
    python3 -m venv "$VENV"
    echo "  ✅  Created venv at $VENV"
else
    echo "  ⏭   venv already exists"
fi

source "$VENV/bin/activate"

# ── 3. Backend dependencies ─────────────────────────────────────
echo ""
echo "  📦  Installing backend dependencies..."
pip install --upgrade pip -q
pip install -r "$BACKEND/requirements.txt" -q
pip install -r "$BACKEND/requirements-dev.txt" -q 2>/dev/null || true
echo "  ✅  Backend deps installed"

# ── 4. Playwright Chromium ──────────────────────────────────────
echo ""
echo "  🌐  Installing Playwright Chromium browser..."
python -m playwright install chromium --with-deps 2>/dev/null || \
    python -m playwright install chromium
echo "  ✅  Playwright ready"

# ── 5. Frontend dependencies ────────────────────────────────────
echo ""
echo "  📦  Installing frontend dependencies..."
cd "$FRONTEND" && npm install --silent
echo "  ✅  Frontend deps installed"

# ── 6. Database ─────────────────────────────────────────────────
echo ""
echo "  🗄️   Initializing database..."
cd "$BACKEND" && python -m app.database --init
echo "  ✅  Database ready"

# ── Done ────────────────────────────────────────────────────────
echo ""
echo "  ╔══════════════════════════════════════════╗"
echo "  ║  ✅  Setup complete!                     ║"
echo "  ║                                          ║"
echo "  ║  Next steps:                             ║"
echo "  ║    make dev          → start both        ║"
echo "  ║    make dev-back     → backend only      ║"
echo "  ║    make dev-front    → frontend only     ║"
echo "  ║    make help         → all commands      ║"
echo "  ╚══════════════════════════════════════════╝"
echo ""
