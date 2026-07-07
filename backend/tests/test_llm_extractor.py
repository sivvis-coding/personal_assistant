"""Tests for the LLM-based daily narrative extractor."""

from datetime import date, time
from typing import Any

import pytest

from app.agents.time.llm_extractor import DailyNarrativeExtractor
from app.agents.time.schemas import TimeEntryParameters
from app.core.llm.provider import LLMProvider


class FakeLLMProvider(LLMProvider):
    """LLM provider stub returning a fixed structured response."""

    def __init__(self, response: dict[str, Any]) -> None:
        self._response = response

    async def complete(self, prompt: str, context: dict[str, Any] | None = None) -> str:
        raise NotImplementedError

    async def complete_structured(
        self,
        prompt: str,
        context: dict[str, Any] | None = None,
        schema: type[Any] | None = None,
    ) -> dict[str, Any]:
        return self._response


@pytest.mark.asyncio
async def test_extract_maps_llm_activities_to_time_entry_parameters() -> None:
    """Verify extract() converts the LLM's structured activities into TimeEntryParameters."""
    provider = FakeLLMProvider(
        {
            "activities": [
                {
                    "task_name": "Refinamiento tech",
                    "client_name": "1200-DV - Desarrollo interno",
                    "description": "Refinamiento tech para dev",
                    "duration_minutes": 90,
                    "start_date": "2026-06-01",
                    "start_time": "09:00",
                }
            ]
        }
    )
    extractor = DailyNarrativeExtractor(provider)

    result = await extractor.extract("cualquier mensaje", today=date(2026, 6, 29))

    assert len(result) == 1
    assert result[0].client_name == "1200-DV - Desarrollo interno"
    assert result[0].duration_minutes == 90
    assert result[0].start_date == date(2026, 6, 1)
    assert result[0].start_time == time(9, 0)


@pytest.mark.asyncio
async def test_complete_fills_gaps_and_preserves_pending_fields() -> None:
    """Verify complete() applies the LLM's filled-in activities in order."""
    provider = FakeLLMProvider(
        {
            "activities": [
                {
                    "task_name": "Refinamiento tech",
                    "client_name": "1200-DV - Desarrollo interno",
                    "description": "Refinamiento tech para dev",
                    "duration_minutes": 90,
                    "start_date": "2026-06-01",
                    "start_time": "09:00",
                }
            ]
        }
    )
    extractor = DailyNarrativeExtractor(provider)
    pending = [
        TimeEntryParameters(
            task_name="Refinamiento tech",
            client_name="1200-DV - Desarrollo interno",
            description="Refinamiento tech para dev",
            duration_minutes=0,
            start_date=None,
            start_time=None,
        )
    ]

    result = await extractor.complete(pending, "duró de 9 a 10:30", today=date(2026, 6, 29))

    assert result[0].duration_minutes == 90
    assert result[0].start_time == time(9, 0)
    assert result[0].client_name == "1200-DV - Desarrollo interno"


@pytest.mark.asyncio
async def test_complete_falls_back_to_pending_activities_on_count_mismatch() -> None:
    """Verify complete() ignores a malformed LLM response that changes the activity count.

    Safer to keep the original activities unchanged than to silently misalign
    a shorter/longer list returned by the model against what was pending.
    """
    provider = FakeLLMProvider({"activities": []})
    extractor = DailyNarrativeExtractor(provider)
    pending = [
        TimeEntryParameters(
            task_name="Refinamiento tech",
            client_name="1200-DV - Desarrollo interno",
            description="Refinamiento tech para dev",
            duration_minutes=0,
            start_date=None,
            start_time=None,
        )
    ]

    result = await extractor.complete(pending, "duró de 9 a 10:30", today=date(2026, 6, 29))

    assert result == pending
