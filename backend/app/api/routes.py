from __future__ import annotations

import asyncio
import logging
import uuid
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
logger = logging.getLogger(__name__)


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


def detect_region(city: str | None) -> str:
    if not city:
        return "domestic"
    if any("\u4e00" <= char <= "\u9fff" for char in city):
        return "domestic"
    return "international"


def resolve_required_servers(config: MCPConfig, trip_input: TripInput) -> set[str]:
    region = detect_region(trip_input.city or trip_input.departure_city)
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
        needs_trains = bool(
            {"query_trains", "get-tickets"} & server_tools
        ) and bool(trip_input.departure_city)
        if needs_weather or needs_trains:
            required.add(server_name)

    return required


@router.post("/trips/generate", response_model=TripOutput, tags=["trips"])
async def generate_trip(
    trip_input: TripInput,
    settings: Settings = Depends(get_settings),
    repository: TripRepository = Depends(get_trip_repository),
) -> TripOutput:
    job_id = uuid.uuid4().hex[:8]
    logger.info(
        "trip_generation[%s] request received city=%s date=%s days=%s interests=%s departure_city=%s random_destination=%s",
        job_id,
        trip_input.city or "-",
        trip_input.date.isoformat(),
        trip_input.days,
        ",".join(trip_input.interests),
        trip_input.departure_city or "-",
        not bool(trip_input.city),
    )
    mcp_config = load_mcp_config(settings.mcp_config_path)
    mcp_manager = MCPClientManager(mcp_config, job_id=job_id)

    try:
        required_servers = resolve_required_servers(mcp_config, trip_input)
        logger.info(
            "trip_generation[%s] required MCP servers: %s",
            job_id,
            ", ".join(sorted(required_servers)) or "-",
        )
        llm_client = build_llm_client(settings)
        agent = TripAgent(
            llm_client=llm_client,
            mcp_manager=mcp_manager,
            model=settings.openai_model,
            job_id=job_id,
        )

        async def run_generation() -> TripOutput:
            logger.info("trip_generation[%s] initializing MCP servers", job_id)
            await mcp_manager.initialize(required_servers)
            logger.info("trip_generation[%s] MCP initialization finished", job_id)
            logger.info("trip_generation[%s] agent run started model=%s", job_id, settings.openai_model)
            trip = await agent.run(trip_input)
            logger.info(
                "trip_generation[%s] agent run finished title=%s items=%d",
                job_id,
                trip.title,
                len(trip.items),
            )
            saved_trip = repository.create_trip(trip)
            logger.info("trip_generation[%s] saved trip id=%s", job_id, saved_trip.id)
            return saved_trip

        result = await asyncio.wait_for(
            run_generation(),
            timeout=settings.generation_timeout_seconds,
        )
        logger.info("trip_generation[%s] request completed", job_id)
        return result
    except asyncio.TimeoutError:
        logger.warning(
            "trip_generation[%s] timed out after %.0f seconds",
            job_id,
            settings.generation_timeout_seconds,
        )
        raise HTTPException(
            status_code=504,
            detail=f"Trip generation timed out after {settings.generation_timeout_seconds:.0f} seconds",
        )
    except AgentTimeoutError as exc:
        logger.warning("trip_generation[%s] agent timeout: %s", job_id, exc)
        raise HTTPException(status_code=504, detail=str(exc))
    except AgentOutputError as exc:
        logger.warning("trip_generation[%s] agent output error: %s", job_id, exc)
        raise HTTPException(status_code=502, detail=str(exc))
    except asyncio.CancelledError:
        logger.warning("trip_generation[%s] request cancelled", job_id)
        raise
    finally:
        logger.info("trip_generation[%s] closing MCP manager", job_id)
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


@router.get("/trips", response_model=list[TripOutput], tags=["trips"])
async def list_trips(
    repository: TripRepository = Depends(get_trip_repository),
) -> list[TripOutput]:
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
