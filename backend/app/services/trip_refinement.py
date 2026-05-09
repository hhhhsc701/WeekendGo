from __future__ import annotations

from dataclasses import dataclass

from app.db.trip_repository import TripRepository
from app.llm.client import LLMClient
from app.models.trip import RefinementIntent, TripOutput


class TripRefinementError(RuntimeError):
    """Raised when a trip cannot be refined."""


@dataclass(frozen=True)
class RefinementResult:
    intent: RefinementIntent
    trip: TripOutput | None
    history_record: dict | None = None


class TripRefinementService:
    def __init__(self, *, llm_client: LLMClient, repository: TripRepository | None = None) -> None:
        self.llm = llm_client
        self.repository = repository

    async def refine(self, trip_id: str, request_text: str) -> RefinementResult:
        if not request_text.strip():
            raise TripRefinementError("Refinement request cannot be empty")
        if self.repository is None:
            raise TripRefinementError("Trip repository is required for refinement")

        original_trip = self.repository.get_trip(trip_id)
        if original_trip is None:
            raise KeyError(trip_id)

        intent = await self.llm.parse_refinement_json(
            original_trip.model_dump(mode="json"),
            request_text,
            RefinementIntent,
        )
        self._detect_conflicts(intent)

        updated_trip = intent.updated_trip
        if updated_trip is not None and not intent.needs_clarification:
            updated_trip.id = original_trip.id
            self.repository.update_trip(trip_id, updated_trip)

        history_record = self.repository.create_adjustment(
            trip_id=trip_id,
            request_text=request_text,
            result=intent.model_dump(mode="json"),
        )
        return RefinementResult(intent=intent, trip=updated_trip, history_record=history_record)

    @staticmethod
    def _detect_conflicts(intent: RefinementIntent) -> None:
        if intent.needs_clarification:
            return
        trip = intent.updated_trip
        if trip is None:
            intent.conflicts.append("No updated trip was returned")
            return

        seen_slots: set[tuple[str, str]] = set()
        for item in trip.items:
            slot = (item.start_time, item.end_time)
            if slot in seen_slots:
                intent.conflicts.append(f"Duplicate time slot: {item.start_time}-{item.end_time}")
            seen_slots.add(slot)
