from __future__ import annotations

import json
import logging
from typing import Any, TypeVar

from openai import AsyncOpenAI
from pydantic import BaseModel, ValidationError

from app.core.settings import Settings
from app.llm.errors import LLMConfigurationError, LLMOutputValidationError
from app.llm.prompts import (
    TRIP_GENERATION_SYSTEM_PROMPT,
    TRIP_REFINEMENT_SYSTEM_PROMPT,
    build_refinement_prompt,
    build_trip_generation_prompt,
)

logger = logging.getLogger(__name__)
ModelT = TypeVar("ModelT", bound=BaseModel)


class LLMClient:
    def __init__(
        self,
        *,
        api_key: str | None,
        model: str,
        base_url: str | None = None,
        max_retries: int = 3,
    ) -> None:
        if not api_key:
            raise LLMConfigurationError("OPENAI_API_KEY is required")
        self.model = model
        self.max_retries = max_retries
        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url)

    @classmethod
    def from_settings(cls, settings: Settings) -> "LLMClient":
        return cls(
            api_key=settings.openai_api_key,
            model=settings.openai_model,
            base_url=settings.openai_base_url,
        )

    async def generate_trip_json(self, context: dict[str, Any], output_model: type[ModelT]) -> ModelT:
        return await self.generate_json(
            system_prompt=TRIP_GENERATION_SYSTEM_PROMPT,
            user_prompt=build_trip_generation_prompt(context),
            output_model=output_model,
        )

    async def parse_refinement_json(
        self,
        original_trip: dict[str, Any],
        request_text: str,
        output_model: type[ModelT],
    ) -> ModelT:
        return await self.generate_json(
            system_prompt=TRIP_REFINEMENT_SYSTEM_PROMPT,
            user_prompt=build_refinement_prompt(original_trip, request_text),
            output_model=output_model,
        )

    async def generate_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        output_model: type[ModelT],
    ) -> ModelT:
        last_error: Exception | None = None
        messages: list[dict[str, str]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        for attempt in range(1, self.max_retries + 1):
            try:
                content = await self._request_json(messages)
                return self._validate_json(content, output_model)
            except (json.JSONDecodeError, ValidationError, LLMOutputValidationError) as exc:
                last_error = exc
                logger.warning("LLM JSON validation failed on attempt %s: %s", attempt, exc)
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            "上一次输出不是有效的目标 JSON 结构。"
                            "请修正并只输出 JSON，不要包含解释文字。"
                        ),
                    }
                )

        raise LLMOutputValidationError(
            f"LLM output failed validation after {self.max_retries} attempts: {last_error}"
        )

    async def _request_json(self, messages: list[dict[str, str]]) -> str:
        response = await self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.4,
        )
        content = response.choices[0].message.content
        if not content:
            raise LLMOutputValidationError("LLM returned empty content")
        return content

    @staticmethod
    def _validate_json(content: str, output_model: type[ModelT]) -> ModelT:
        payload = json.loads(content)
        return output_model.model_validate(payload)
