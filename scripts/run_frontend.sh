#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../frontend"
npm run dev -- --hostname "${FRONTEND_HOST:-0.0.0.0}" --port "${FRONTEND_PORT:-3000}"
