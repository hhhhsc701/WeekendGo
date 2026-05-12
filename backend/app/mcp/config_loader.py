from __future__ import annotations

import os
import re
from pathlib import Path

import yaml

from app.mcp.models import MCPConfig
from app.mcp.errors import MCPConfigurationError

ENV_PATTERN = re.compile(r"\$\{([A-Z0-9_]+)(:-([^}]*))?\}")


def inject_environment_placeholders(value):
    if isinstance(value, str):
        return _replace_env_placeholders(value)
    if isinstance(value, list):
        return [inject_environment_placeholders(item) for item in value]
    if isinstance(value, dict):
        return {key: inject_environment_placeholders(item) for key, item in value.items()}
    return value


def _replace_env_placeholders(value: str) -> str:
    def replace(match):
        env_name = match.group(1)
        default_value = match.group(3) if match.group(2) else None
        env_value = _get_env_value(env_name)
        if env_value is None or env_value == "":
            if default_value is not None:
                return default_value
            return ""
        return env_value

    return ENV_PATTERN.sub(replace, value)


def _get_env_value(name: str) -> str | None:
    return os.getenv(name) or _read_dotenv().get(name)


def _read_dotenv() -> dict[str, str]:
    env_path = Path(".env")
    if not env_path.exists():
        return {}
    values: dict[str, str] = {}
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def load_mcp_config(path: Path | str) -> MCPConfig:
    config_path = Path(path)
    if not config_path.exists():
        raise MCPConfigurationError(f"MCP config file not found: {config_path}")

    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise MCPConfigurationError("MCP config must be a YAML mapping")

    raw = inject_environment_placeholders(raw)
    return MCPConfig.model_validate(raw.get("mcp", {}))