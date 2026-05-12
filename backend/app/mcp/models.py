from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class MCPServerConfig(BaseModel):
    enabled: bool = True
    mode: Literal["local"] = "local"
    command: str | None = None
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)
    tools: list[str] = Field(default_factory=list)
    timeout_seconds: float = 30.0


class RouteConfig(BaseModel):
    primary: str
    shared: list[str] = Field(default_factory=list)


class MCPConfig(BaseModel):
    timeout_seconds: float = 30.0
    servers: dict[str, MCPServerConfig]
    routes: dict[str, RouteConfig] = Field(default_factory=dict)
