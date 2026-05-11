from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.dependencies import get_trip_repository
from app.core.settings import Settings, get_settings
from app.db.trip_repository import TripRepository
from app.llm.client import LLMClient
from app.llm.errors import LLMConfigurationError
from app.mcp.client import MCPClientManager
from app.mcp.config_loader import load_mcp_config
from app.models.trip import TripInput, TripOutput
from app.services.trip_generation import TripGenerationService
from app.services.trip_refinement import TripRefinementService

router = APIRouter(prefix="/api")


class RefineRequest(BaseModel):
    request: str = Field(min_length=1)


@router.post("/trips/generate", response_model=TripOutput, tags=["trips"])
async def generate_trip(
    trip_input: TripInput,
    settings: Settings = Depends(get_settings),
    repository: TripRepository = Depends(get_trip_repository),
) -> TripOutput:
    llm_client = build_llm_client(settings)
    mcp_config = load_mcp_config(settings.mcp_config_path)
    mcp_manager = MCPClientManager(mcp_config)
    await mcp_manager.initialize()
    try:
        service = TripGenerationService(mcp_manager=mcp_manager, llm_client=llm_client)
        trip = await service.generate(trip_input)
        return repository.create_trip(trip)
    finally:
        await mcp_manager.close()


@router.post("/trips/refine/{trip_id}", response_model=TripOutput | dict[str, Any], tags=["trips"])
async def refine_trip(
    trip_id: str,
    payload: RefineRequest,
    settings: Settings = Depends(get_settings),
    repository: TripRepository = Depends(get_trip_repository),
) -> TripOutput | dict[str, Any]:
    if repository.get_trip(trip_id) is None:
        raise HTTPException(status_code=404, detail="Trip not found")

    service = TripRefinementService(llm_client=build_llm_client(settings), repository=repository)
    result = await service.refine(trip_id, payload.request)
    if result.intent.needs_clarification:
        return result.intent.model_dump(mode="json")
    if result.trip is None:
        raise HTTPException(status_code=409, detail={"conflicts": result.intent.conflicts})
    return result.trip


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
async def list_trips(repository: TripRepository = Depends(get_trip_repository)) -> list[dict[str, Any]]:
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
    config = load_mcp_config(settings.mcp_config_path)
    return {
        "environment": settings.app_env,
        "llmModel": settings.openai_model,
        "mcp": {
            "timeoutSeconds": config.timeout_seconds,
            "servers": [
                {
                    "name": name,
                    "enabled": server.enabled,
                    "region": server.region,
                    "tools": server.tools,
                    "unavailableReason": server.unavailable_reason,
                }
                for name, server in config.servers.items()
            ],
            "routes": {name: route.model_dump() for name, route in config.routes.items()},
        },
    }


def build_llm_client(settings: Settings) -> LLMClient:
    try:
        return LLMClient.from_settings(settings)
    except LLMConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
