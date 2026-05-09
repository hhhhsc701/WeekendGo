# Deployment Notes

WeekendGo is designed as two processes: a FastAPI backend and a Next.js frontend.

## Backend

1. Set environment variables from `.env.example`.
2. Make sure `DATABASE_PATH` points to a writable SQLite file.
3. Run `uv run python backend/scripts/init_db.py` once per environment.
4. Start the API with:

```bash
uv run uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8000
```

## Frontend

1. Set `NEXT_PUBLIC_API_BASE_URL` to the public backend URL.
2. Install dependencies and build:

```bash
cd frontend
npm install
npm run build
npm run start
```

## MCP Requirements

The backend launches MCP servers from `config/mcp_config.yaml`. Production hosts must allow those commands to execute and must expose required API keys through environment variables.
