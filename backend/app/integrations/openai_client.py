import json
from pathlib import Path
from typing import TypeVar

from openai import AsyncOpenAI, OpenAIError
from pydantic import BaseModel, ValidationError

from app.core.config import Settings
from app.core.errors import ExternalServiceError
from app.schemas.ai import ReplyDraft, TicketSummary, UserStory
from app.schemas.ticket import Ticket

PromptModel = TypeVar("PromptModel", bound=BaseModel)


class OpenAIClient:
    """Client for AI ticket transformations.

    Parameters:
        settings: Application settings with OpenAI credentials and model.

    Returns:
        OpenAI integration client.

    Edge cases:
        Missing API key returns deterministic mock outputs for local development.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = AsyncOpenAI(api_key=settings.openai_api_key) if settings.has_openai_key else None
        self.model = settings.openai_model

    async def summarize_ticket(self, ticket: Ticket) -> TicketSummary:
        """Generate a structured ticket summary.

        Parameters:
            ticket: Ticket to summarize.

        Returns:
            Validated ticket summary.

        Edge cases:
            Missing OpenAI key returns mock summary.
        """
        if self._client is None:
            return TicketSummary(
                title=ticket.subject,
                problem=ticket.description or "No description provided.",
                impact="Impact requires human validation.",
                suggested_next_steps=["Review ticket details", "Confirm reproduction steps"],
                risks=["Mock AI output because OPENAI_API_KEY is not configured"],
            )
        return await self._json_completion("ticket_summary_v1.txt", ticket, TicketSummary)

    async def draft_reply(self, ticket: Ticket) -> ReplyDraft:
        """Generate a customer reply draft.

        Parameters:
            ticket: Ticket requiring a draft reply.

        Returns:
            Validated reply draft.

        Edge cases:
            Draft is not sent to Fresh automatically.
        """
        if self._client is None:
            return ReplyDraft(
                subject=f"Re: {ticket.subject}",
                body="Thanks for the details. I am reviewing the issue and will confirm the next steps after validating the current behavior.",
                tone="professional",
                requires_human_review=True,
            )
        return await self._json_completion("draft_reply_v1.txt", ticket, ReplyDraft)

    async def ticket_to_user_story(self, ticket: Ticket) -> UserStory:
        """Convert a support ticket into a user story.

        Parameters:
            ticket: Source ticket.

        Returns:
            Validated user story.

        Edge cases:
            Missing ticket detail produces conservative generic criteria.
        """
        if self._client is None:
            return UserStory(
                title=ticket.subject,
                description=ticket.description or "Ticket without detailed description.",
                acceptance_criteria_in_gerkin=(
                    "Given the reported ticket context\n"
                    "When the support team validates the expected behavior\n"
                    "Then the resolution criteria are documented and confirmed"
                ),
                constraints="Review logs, permissions, and recent changes before implementation.",
                user_story_statement=f"As an affected user, I want {ticket.subject.lower()}, so that I can continue working without blockers.",
                out_of_scope="Not specified",
                requested_by=ticket.requester.name,
                functional_description="The system should support the expected customer workflow described in the ticket.",
            )
        return await self._json_completion("ticket_user_story_v1.txt", ticket, UserStory)

    async def _json_completion(self, prompt_file: str, ticket: Ticket, schema: type[PromptModel]) -> PromptModel:
        """Run an OpenAI JSON completion and validate the result.

        Parameters:
            prompt_file: Versioned prompt file name.
            ticket: Ticket context.
            schema: Pydantic schema used for validation.

        Returns:
            Validated AI response.

        Edge cases:
            Invalid JSON or schema mismatches become ExternalServiceError.
        """
        if self._client is None:
            raise ExternalServiceError("OpenAI client is not configured")
        prompt = self._load_prompt(prompt_file)
        try:
            response = await self._client.chat.completions.create(
                model=self.model,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": json.dumps(ticket.model_dump(), default=str)},
                ],
            )
            content = response.choices[0].message.content or "{}"
            return schema.model_validate_json(content)
        except (OpenAIError, ValidationError, json.JSONDecodeError) as error:
            raise ExternalServiceError(f"OpenAI response failed validation: {error}") from error

    def _load_prompt(self, prompt_file: str) -> str:
        """Load a versioned prompt file.

        Parameters:
            prompt_file: Prompt file name.

        Returns:
            Prompt text.

        Edge cases:
            Missing prompt file raises FileNotFoundError because deployment is invalid.
        """
        return (Path(__file__).resolve().parents[1] / "prompts" / prompt_file).read_text(encoding="utf-8")
