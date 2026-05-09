# WeekendGo Backend

FastAPI service for itinerary generation, MCP routing, LLM orchestration, and SQLite persistence.

## Development

```bash
uv sync --extra dev
uv run uvicorn app.main:app --app-dir backend --reload
```

The API is available at `http://localhost:8000`.
