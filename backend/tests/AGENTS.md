# TESTS

pytest test suite.

## WHERE TO LOOK

| Task | File |
|------|------|
| Trip generation tests | test_trip_generation.py (267 lines) |
| API endpoint tests | test_api.py |
| Region routing tests | test_region.py |
| MCP config tests | test_mcp_config_loader.py |
| Database + refinement | test_database_and_refinement.py |

## CONVENTIONS

- `asyncio_mode = "auto"` - no `@pytest.mark.asyncio` decorator needed
- `testpaths = ["backend/tests"]` - pytest discovers here automatically
- `pythonpath = ["backend"]` - imports work as `from app.*`
- Tests mock MCP + LLM calls, not actual server connections

## EXAMPLE

```python
# No decorator needed
async def test_generate_trip():
    service = TripGenerationService(mcp_manager=mock_mcp, llm_client=mock_llm)
    result = await service.generate(trip_input)
    assert result.title
```

## NOTES

- Run: `uv run pytest backend/tests`
- Mock patterns: `AsyncMock` for MCP calls, fixture injection for settings