#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────
#  AutoAvenue Scraper — Start development servers
# ──────────────────────────────────────────────────────────────────
#  Usage:  bash scripts/dev.sh          # both servers
#          bash scripts/dev.sh back     # backend only
#          bash scripts/dev.sh front    # frontend only
#
#  Backend:  http://localhost:8100  (FastAPI + Swagger at /docs)
#  Frontend: http://localhost:5273  (Vite HMR, proxies /api → backend)
# ──────────────────────────────────────────────────────────────────

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"
VENV="$BACKEND/.venv"
MODE="${1:-both}"

# Validate venv exists
if [ ! -d "$VENV" ]; then
    echo "  ❌  No venv found. Run 'bash scripts/setup.sh' first."
    exit 1
fi

source "$VENV/bin/activate"

cleanup() {
    echo ""
    echo "  🛑  Shutting down..."
    kill 0 2>/dev/null
    exit 0
}
trap cleanup SIGINT SIGTERM

case "$MODE" in
    back|backend)
        echo "  🚀  Starting backend on http://localhost:8100"
        cd "$BACKEND" && uvicorn app.main:app \
            --host 0.0.0.0 --port 8100 --reload --reload-dir app
        ;;
    front|frontend)
        echo "  🚀  Starting frontend on http://localhost:5273"
        cd "$FRONTEND" && npm run dev
        ;;
    both|*)
        echo "  🚀  Starting backend on :8100 + frontend on :5273"
        echo ""
        (cd "$BACKEND" && uvicorn app.main:app \
            --host 0.0.0.0 --port 8100 --reload --reload-dir app) &
        (cd "$FRONTEND" && npm run dev) &
        wait
        ;;
esac
