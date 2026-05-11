#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
if [ -f .env ]; then
  set -a
  . ./.env
  set +a
fi
export UV_CACHE_DIR="${UV_CACHE_DIR:-/tmp/uv-cache}"
export PYTHONPATH="${PYTHONPATH:-backend}"
uv run python backend/scripts/init_db.py
uv run uvicorn app.main:app --app-dir backend --host "${BACKEND_HOST:-0.0.0.0}" --port "${BACKEND_PORT:-8000}"
