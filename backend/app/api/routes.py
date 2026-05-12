from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from openai import AsyncOpenAI

from app.agent.trip_agent import TripAgent
from app.agent.errors import AgentTimeoutError, AgentOutputError
from app.core.settings import Settings, get_settings
from app.db.trip_repository import TripRepository
from app.db.database import get_database
from app.mcp.client import MCPClientManager
from app.mcp.config_loader import load_mcp_config
from app.mcp.models import MCPConfig
from app.models.trip import TripInput, TripOutput

router = APIRouter(prefix="/api")


async def get_trip_repository() -> AsyncIterator[TripRepository]:
    settings = get_settings()
    conn = get_database(settings.database_path)
    try:
        yield TripRepository(conn)
    finally:
        conn.close()


def build_llm_client(settings: Settings) -> AsyncOpenAI:
    if not settings.openai_api_key:
        raise HTTPException(status_code=503, detail="OPENAI_API_KEY is not configured")
    return AsyncOpenAI(
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
        timeout=settings.openai_timeout_seconds,
    )


def detect_region(city: str) -> str:
    if any("\u4e00" <= char <= "\u9fff" for char in city):
        return "domestic"
    return "international"


def resolve_required_servers(config: MCPConfig, trip_input: TripInput) -> set[str]:
    region = detect_region(trip_input.city)
    route = config.routes.get(region) or config.routes.get("domestic")
    if route is None:
        return set()

    required = {route.primary}
    primary = config.servers.get(route.primary)
    primary_tools = set(primary.tools) if primary else set()

    for server_name in route.shared:
        server = config.servers.get(server_name)
        if server is None:
            continue
        server_tools = set(server.tools)

        needs_weather = (
            ("get_weather" in server_tools or "get_forecast" in server_tools)
            and "get_weather" not in primary_tools
            and "get_forecast" not in primary_tools
        )
        needs_trains = "query_trains" in server_tools and bool(trip_input.departure_city)
        if needs_weather or needs_trains:
            required.add(server_name)

    return required


@router.post("/trips/generate", response_model=TripOutput, tags=["trips"])
async def generate_trip(
    trip_input: TripInput,
    settings: Settings = Depends(get_settings),
    repository: TripRepository = Depends(get_trip_repository),
) -> TripOutput:
    mcp_config = load_mcp_config(settings.mcp_config_path)
    mcp_manager = MCPClientManager(mcp_config)

    try:
        required_servers = resolve_required_servers(mcp_config, trip_input)
        llm_client = build_llm_client(settings)
        agent = TripAgent(
            llm_client=llm_client,
            mcp_manager=mcp_manager,
            model=settings.openai_model,
        )

        async def run_generation() -> TripOutput:
            await mcp_manager.initialize(required_servers)
            trip = await agent.run(trip_input)
            return repository.create_trip(trip)

        return await asyncio.wait_for(
            run_generation(),
            timeout=settings.generation_timeout_seconds,
        )
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=504,
            detail=f"Trip generation timed out after {settings.generation_timeout_seconds:.0f} seconds",
        )
    except AgentTimeoutError as exc:
        raise HTTPException(status_code=504, detail=str(exc))
    except AgentOutputError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    finally:
        await mcp_manager.close()


@router.get("/trips/{trip_id}", response_model=TripOutput, tags=["trips"])
async def get_trip(
    trip_id: str,
    repository: TripRepository = Depends(get_trip_repository),
) -> TripOutput:
    trip = repository.get_trip(trip_id)
    if trip is None:
        raise HTTPException(status_code=404, detail="Trip not found")
    return trip


@router.get("/trips", tags=["trips"])
async def list_trips(
    repository: TripRepository = Depends(get_trip_repository),
) -> list[dict[str, Any]]:
    return repository.list_trips()


@router.delete("/trips/{trip_id}", tags=["trips"])
async def delete_trip(
    trip_id: str,
    repository: TripRepository = Depends(get_trip_repository),
) -> dict[str, bool]:
    deleted = repository.delete_trip(trip_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Trip not found")
    return {"deleted": True}


@router.get("/config", tags=["config"])
async def get_config(settings: Settings = Depends(get_settings)) -> dict[str, Any]:
    return {
        "environment": settings.app_env,
        "model": settings.openai_model,
        "mcp_config_path": str(settings.mcp_config_path),
    }
