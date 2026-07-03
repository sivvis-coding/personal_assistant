"""LLM-based extractor that segments a free-text daily narrative into activities."""

from datetime import date
from pathlib import Path

from app.agents.time.schemas import DailyNarrativeExtraction, TimeEntryParameters
from app.core.llm.provider import LLMProvider


def _load_prompt(prompt_file: str) -> str:
    """Load a versioned prompt file from the time agent prompts directory.

    Parameters:
        prompt_file: Prompt file name.

    Returns:
        Prompt text.

    Edge cases:
        Missing prompt file raises FileNotFoundError because deployment is invalid.
    """
    return (Path(__file__).resolve().parent / "prompts" / prompt_file).read_text(encoding="utf-8")


class DailyNarrativeExtractor:
    """Extract one or more time entry activities from a free-text daily narrative.

    Parameters:
        llm_provider: LLM provider used for structured extraction.

    Returns:
        Extractor capable of segmenting multi-activity Spanish narratives.

    Edge cases:
        A narrative describing a single activity still returns a one-item list.
        Missing OpenAI credentials fall back to the LLM provider's deterministic
        mock output, which returns an empty activity list.
    """

    def __init__(self, llm_provider: LLMProvider) -> None:
        self._llm_provider = llm_provider

    async def extract(self, message: str, today: date) -> list[TimeEntryParameters]:
        """Extract time entry parameters for each activity mentioned in the message.

        Parameters:
            message: Natural language daily narrative in Spanish.
            today: Reference date used to resolve relative date words such as "hoy".

        Returns:
            List of extracted parameters, one per detected activity, in the order mentioned.
        """
        prompt = _load_prompt("daily_narrative_v1.txt")
        context = {"message": message, "today": today.isoformat()}
        data = await self._llm_provider.complete_structured(
            prompt=prompt,
            context=context,
            schema=DailyNarrativeExtraction,
        )
        extraction = DailyNarrativeExtraction.model_validate(data)
        return [
            TimeEntryParameters(
                task_name=activity.task_name,
                client_name=activity.client_name,
                description=activity.description,
                duration_minutes=activity.duration_minutes,
                start_date=activity.start_date,
                start_time=activity.start_time,
            )
            for activity in extraction.activities
        ]
