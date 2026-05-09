# Configuration

WeekendGo reads runtime settings from environment variables and MCP routing from `config/mcp_config.yaml`.

## Required Environment

- `OPENAI_API_KEY`: OpenAI-compatible API key.
- `OPENAI_MODEL`: chat model name.
- `OPENAI_BASE_URL`: optional OpenAI-compatible base URL for providers such as DeepSeek.
- `AMAP_API_KEY`: required for domestic city map and weather data.
- `GOOGLE_MAPS_API_KEY`: required for international Google Maps data.
- `DATABASE_PATH`: SQLite database path, defaults to `data/weekendgo.sqlite3`.
- `MCP_CONFIG_PATH`: MCP config path, defaults to `config/mcp_config.yaml`.

## MCP Config

Use `config/mcp_config.example.yaml` as a safe reference. Keep real credentials in the environment; do not write API keys directly into YAML files.

Each server has:

- `enabled`: whether the backend should initialize it.
- `region`: `domestic`, `international`, or `shared`.
- `command` and `args`: process launched by the Python MCP client.
- `env`: environment variables passed to the MCP server.
- `tools`: allowed tools for routing.
