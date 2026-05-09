from __future__ import annotations

from pathlib import Path
import os
import re
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field

from app.mcp.errors import MCPConfigurationError

ENV_PATTERN = re.compile(r"\$\{([A-Z0-9_]+)\}")


class MCPServerConfig(BaseModel):
    enabled: bool = True
    region: Literal["domestic", "international", "shared"]
    command: str
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)
    tools: list[str] = Field(default_factory=list)


class MCPRouteConfig(BaseModel):
    primary: str
    shared: list[str] = Field(default_factory=list)


class MCPConfig(BaseModel):
    timeout_seconds: float = 30
    servers: dict[str, MCPServerConfig]
    routes: dict[Literal["domestic", "international"], MCPRouteConfig]


class RootMCPConfig(BaseModel):
    mcp: MCPConfig


def inject_environment_placeholders(value: Any) -> Any:
    if isinstance(value, str):
        return _replace_env_placeholders(value)
    if isinstance(value, list):
        return [inject_environment_placeholders(item) for item in value]
    if isinstance(value, dict):
        return {key: inject_environment_placeholders(item) for key, item in value.items()}
    return value


def _replace_env_placeholders(value: str) -> str:
    def replace(match: re.Match[str]) -> str:
        env_name = match.group(1)
        env_value = os.getenv(env_name)
        if env_value is None or env_value == "":
            raise MCPConfigurationError(f"Environment variable {env_name} is required")
        return env_value

    return ENV_PATTERN.sub(replace, value)


def load_mcp_config(path: Path | str, enabled_servers: set[str] | None = None) -> MCPConfig:
    config_path = Path(path)
    if not config_path.exists():
        raise MCPConfigurationError(f"MCP config file not found: {config_path}")

    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise MCPConfigurationError("MCP config must be a YAML mapping")

    if enabled_servers is not None:
        raw = _scope_enabled_servers(raw, enabled_servers)

    config = RootMCPConfig.model_validate(raw).mcp
    for server_name, server_config in config.servers.items():
        if server_config.enabled:
            server_config.env = inject_environment_placeholders(server_config.env)
            server_config.args = inject_environment_placeholders(server_config.args)
            server_config.command = inject_environment_placeholders(server_config.command)
    return config


def _scope_enabled_servers(raw: dict[str, Any], enabled_servers: set[str]) -> dict[str, Any]:
    scoped = dict(raw)
    mcp = dict(scoped.get("mcp", {}))
    servers = {
        name: {**server, "enabled": name in enabled_servers}
        for name, server in mcp.get("servers", {}).items()
    }
    mcp["servers"] = servers
    scoped["mcp"] = mcp
    return scoped
