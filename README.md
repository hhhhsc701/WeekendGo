# WeekendGo

WeekendGo is an AI weekend itinerary assistant using a **ReAct Agent architecture**. The LLM autonomously decides city type (domestic/international), selects MCP tools, and generates structured TripOutput through iterative Think→Act→Observe cycles.

## Architecture

### ReAct Agent Flow

```
User Input → TripAgent
    ↓
[Think] LLM analyzes city, plans tool usage
    ↓
[Act] Call MCP tools (geocode, search_poi, get_weather, query_trains)
    ↓
[Observe] Process tool results
    ↓
[Loop] Continue until finish tool called or max_iterations
    ↓
TripOutput → SQLite → Frontend Display
```

### Project Structure

- `backend/app/agent/`: TripAgent with ReAct loop, TOOL_DEFINITIONS
- `backend/app/mcp/`: MCPClientManager with dual-mode (API + Local MCP Server)
- `backend/app/models/`: Pydantic models with LLM output coercion
- `backend/app/api/`: FastAPI REST endpoints
- `backend/app/db/`: SQLite persistence with TripRepository
- `frontend/`: Next.js 15 App Router with Tailwind + Leaflet
- `config/mcp_config.yaml`: MCP server routing (AMap, Google Maps, Weather, 12306)
- `data/`: SQLite database directory

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

All services:

```bash
scripts/run_all.sh
```

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

### MCP Dual-Mode

- **API mode**: Direct HTTP calls to service APIs (AMap API, Google Maps API) - faster, production-ready
- **Local mode**: MCP Server process via `npx` (Weather MCP, 12306 MCP) - dev/testing

Domestic city routes use AMap and optional 12306. International routes use Google Maps and Weather MCP.

### Agent Tools

| Tool | Description | MCP Server |
|------|-------------|------------|
| `geocode` | City → coordinates | AMap (domestic) / Google Maps (international) |
| `search_poi` | Find attractions, restaurants | AMap / Google Maps |
| `get_weather` | Weather forecast | Weather MCP |
| `query_trains` | Train schedules | 12306 MCP |
| `finish` | Complete with TripOutput | LLM internal |

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/trips/generate` | POST | Generate trip itinerary (TripInput → TripOutput) |
| `/api/trips/{id}` | GET | Get trip by ID |
| `/api/trips` | GET | List all trips |
| `/api/trips/{id}` | DELETE | Delete trip |
| `/api/config` | GET | Get runtime config |

Full API docs: http://localhost:8000/docs

## Testing

```bash
# Run TripAgent tests (14 tests with mock LLM/MCP)
uv run pytest backend/tests/test_agent.py -v

# Run all tests
uv run pytest backend/tests -v
```

Test coverage includes:
- Agent complete flow (geocode→poi→finish)
- Agent timeout scenarios
- Tool failure degradation
- LLM output coercion
