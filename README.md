# WeekendGo

WeekendGo is an AI weekend itinerary assistant. It accepts city, date, budget, interests, companions, and optional departure-city context, then coordinates MCP tools and an LLM to produce a structured itinerary.

## Architecture

- `backend/`: FastAPI service, MCP integration, LLM orchestration, and SQLite persistence.
- `frontend/`: Next.js App Router frontend.
- `config/mcp_config.yaml`: MCP server routing configuration.
- `data/`: local SQLite database directory.
- `openspec/`: OpenSpec change artifacts and task tracking.

## Prerequisites

- Python 3.12+
- Node.js 20+
- `uv` for Python dependency management
- API keys for OpenAI-compatible LLMs, AMap, and Google Maps when live MCP calls are enabled

## Setup

```bash
cp .env.example .env
uv sync --extra dev
uv run python backend/scripts/init_db.py
cd frontend
npm install
```

Fill `.env` with the required keys before running live MCP or LLM flows.

## Run

Backend:

```bash
BACKEND_PORT=8000 scripts/run_backend.sh
```

Frontend:

```bash
FRONTEND_PORT=3000 scripts/run_frontend.sh
```

Open `http://localhost:3000` for the frontend and `http://localhost:8000/docs` for the backend API docs.

Custom ports can be set in `.env`:

```bash
BACKEND_PORT=8100
FRONTEND_PORT=3100
NEXT_PUBLIC_API_BASE_URL=http://localhost:8100
CORS_ORIGINS=http://localhost:3100
```

## Configuration

MCP tools are configured in `config/mcp_config.yaml`. Values like `${AMAP_API_KEY}` are resolved from the process environment or `.env` loader before MCP servers are initialized.

Domestic city routes use AMap and optional 12306. International routes use Google Maps and Weather MCP.
