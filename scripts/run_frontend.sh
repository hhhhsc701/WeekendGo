#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
if [ -f .env ]; then
  set -a
  . ./.env
  set +a
fi

export NEXT_PUBLIC_API_BASE_URL="${NEXT_PUBLIC_API_BASE_URL:-http://${BACKEND_PUBLIC_HOST:-localhost}:${BACKEND_PORT:-8000}}"

cd frontend
npm run dev -- --hostname "${FRONTEND_HOST:-0.0.0.0}" --port "${FRONTEND_PORT:-3000}"
