# Deployment Notes

WeekendGo is designed as two processes: a FastAPI backend and a Next.js frontend.

## Backend

1. Set environment variables from `.env.example`.
2. Make sure `DATABASE_PATH` points to a writable SQLite file.
3. Run `uv run python backend/scripts/init_db.py` once per environment.
4. Start the API with:

```bash
BACKEND_PORT=8000 scripts/run_backend.sh
```

Set `BACKEND_PORT` to use a different host port.

## Frontend

1. Set `NEXT_PUBLIC_API_BASE_URL` to the public backend URL.
2. Install dependencies and build:

```bash
cd frontend
npm install
FRONTEND_PORT=3000 npm run dev -- --hostname 0.0.0.0 --port "$FRONTEND_PORT"
```

Set `NEXT_PUBLIC_API_BASE_URL` to the browser-visible backend URL, especially when `BACKEND_PORT` is customized.

## MCP Requirements

The backend launches MCP servers from `config/mcp_config.yaml`. Production hosts must allow those commands to execute and must expose required API keys through environment variables.
