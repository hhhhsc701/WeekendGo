# PROJECT KNOWLEDGE BASE

**Generated:** 2026-05-11T10:51
**Commit:** 13b8343
**Branch:** main

## OVERVIEW

WeekendGo - AI weekend itinerary assistant. FastAPI backend with MCP tool integration + LLM orchestration. Next.js 15 frontend with App Router. SQLite persistence.

## STRUCTURE

```
WeekendGo/
├── backend/app/     # FastAPI service (api, llm, mcp, models, services, db)
├── backend/tests/   # pytest tests (asyncio mode)
├── frontend/        # Next.js 15 App Router + Tailwind
├── config/          # mcp_config.yaml - MCP server routing
├── data/            # SQLite database directory
├── scripts/         # run_backend.sh, run_frontend.sh
└── openspec/        # OpenSpec change artifacts
```

## WHERE TO LOOK

| Task | Location | Notes |
|------|----------|-------|
| Trip generation flow | `backend/app/services/trip_generation.py` | 471 lines, orchestrates MCP + LLM |
| MCP tool integration | `backend/app/mcp/client.py` | MCPClientManager, tool aliases |
| Region routing (domestic/international) | `backend/app/mcp/region.py` | AMap vs Google Maps routing |
| API endpoints | `backend/app/api/routes.py` | /api/trips/*, /api/config |
| Data models | `backend/app/models/trip.py` | TripInput, TripOutput, Place, etc. |
| LLM prompts | `backend/app/llm/prompts.py` | JSON schema for trip generation |
| Database persistence | `backend/app/db/trip_repository.py` | SQLite CRUD |
| Frontend API client | `frontend/lib/api.ts` | Fetch wrapper |
| Trip form UI | `frontend/components/trip-form.tsx` | Input collection |
| Itinerary display | `frontend/components/timeline-view.tsx` | Day schedule view |

## CODE MAP

| Symbol | Type | Location | Role |
|--------|------|----------|------|
| TripGenerationService | class | services/trip_generation.py | Core orchestration |
| MCPClientManager | class | mcp/client.py | MCP tool lifecycle |
| RegionRouter | class | mcp/region.py | domestic/international routing |
| TripInput | model | models/trip.py | User request schema |
| TripOutput | model | models/trip.py | Generated itinerary schema |
| GenerationContext | model | models/trip.py | MCP data accumulation |
| LLMClient | class | llm/client.py | OpenAI-compatible client |
| TripRepository | class | db/trip_repository.py | SQLite persistence |
| api | object | frontend/lib/api.ts | Frontend fetch helper |

## CONVENTIONS

- **Python**: ruff lint, line-length 100, py312 target
- **Tests**: pytest-asyncio auto mode, testpaths = backend/tests
- **Frontend**: Next.js 15 App Router, Tailwind CSS, TypeScript strict
- **MCP tools**: Configured in config/mcp_config.yaml, env vars `${AMAP_API_KEY}` style
- **Region routing**: "domestic" → AMap/12306, "international" → Google Maps/Weather

## UNIQUE STYLES

- `GenerationContext` accumulates MCP results before LLM synthesis
- `normalize_*` functions transform MCP responses into unified models
- Pydantic `model_validator(mode="before")` coerces LLM string outputs
- Tool aliases: `geocode` → `maps_geo` for AMap compatibility
- Frontend uses `"use client"` directive in client components

## COMMANDS

```bash
# Backend
uv sync --extra dev
BACKEND_PORT=8000 scripts/run_backend.sh

# Frontend
cd frontend && npm install
FRONTEND_PORT=3000 scripts/run_frontend.sh

# Tests
uv run pytest backend/tests
```

## NOTES

- API docs: http://localhost:8000/docs
- Frontend: http://localhost:3000
- `.env` required: OPENAI_API_KEY, AMAP_API_KEY, GOOGLE_MAPS_API_KEY
- MCP servers run via npx (e.g., `npx -y @amap/amap-maps-mcp-server`)