import json
from pathlib import Path
from typing import TypeVar

from openai import AsyncOpenAI, OpenAIError
from pydantic import BaseModel, ValidationError

from app.core.config import Settings
from app.core.errors import ExternalServiceError
from app.schemas.ai import ReplyDraft, TicketSummary, UserStory
from app.schemas.clickup import ClickUpTask
from app.schemas.insights import (
    ClusterGroup,
    ClusterPlan,
    ConsolidationGroup,
    ConsolidationPlan,
    DepartmentAnalysisPlan,
    ThemeDoc,
    TicketSignature,
)
from app.schemas.roadmap import (
    RoadmapGroupPlan,
    RoadmapListSummary,
    RoadmapPlan,
    RoadmapSummariesResponse,
    RoadmapSummaryListInput,
)
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

    async def text_to_user_story(self, description: str) -> UserStory:
        """Convert a free-text chat request into a user story, with no source ticket.

        Parameters:
            description: User's free-text description of what they want built.

        Returns:
            Validated user story.

        Edge cases:
            Missing OpenAI credentials return a conservative mock story that
            just echoes the description back so local development still works.
        """
        if self._client is None:
            return UserStory(
                title=description[:80],
                description=description,
                acceptance_criteria_in_gerkin=(
                    "Given the request described by the user\n"
                    "When the described behavior is implemented\n"
                    "Then it matches what was requested"
                ),
                constraints="Mock AI output because OPENAI_API_KEY is not configured",
                user_story_statement=f"As a user, I want {description.lower()}",
                out_of_scope="Not specified",
                requested_by="Not specified",
                functional_description=description,
            )
        return await self._json_completion("chat_user_story_v1.txt", {"description": description}, UserStory)

    async def generate_roadmap(self, tasks: list[ClickUpTask]) -> RoadmapPlan:
        """Group ClickUp tasks into themes/epics for a roadmap.

        Parameters:
            tasks: Source ClickUp tasks to organize.

        Returns:
            Raw grouping plan (theme titles + task IDs) for the service to
            rehydrate against the real tasks.

        Edge cases:
            Missing OpenAI key returns a single mock group containing every task,
            so the roadmap page still renders during local development.
        """
        if self._client is None:
            return RoadmapPlan(
                groups=[
                    RoadmapGroupPlan(
                        title="All tasks",
                        summary="Mock roadmap because OPENAI_API_KEY is not configured",
                        task_ids=[task.id for task in tasks],
                    )
                ]
            )
        context = {
            "tasks": [
                {
                    "id": task.id,
                    "name": task.name,
                    "status": task.status,
                    "description": task.description or "",
                }
                for task in tasks
            ]
        }
        return await self._json_completion("roadmap_v1.txt", context, RoadmapPlan)

    async def summarize_roadmap_lists(
        self, lists: list[RoadmapSummaryListInput]
    ) -> RoadmapSummariesResponse:
        """Summarize each ClickUp list from its (filtered) visible tasks.

        Parameters:
            lists: Lists with their currently-visible tasks.

        Returns:
            One summary per list.

        Edge cases:
            Missing OpenAI key returns deterministic mock summaries so the local
            dev flow still renders.
        """
        if self._client is None:
            return RoadmapSummariesResponse(
                summaries=[
                    RoadmapListSummary(
                        list_id=entry.list_id,
                        summary=f"Resumen mock: {len(entry.tasks)} tareas en {entry.list_name or entry.list_id}.",
                    )
                    for entry in lists
                ]
            )
        context = {
            "lists": [
                {
                    "list_id": entry.list_id,
                    "list_name": entry.list_name,
                    "tasks": [
                        {"name": t.name, "status": t.status, "description": t.description or ""}
                        for t in entry.tasks
                    ],
                }
                for entry in lists
            ]
        }
        return await self._json_completion("roadmap_summary_v1.txt", context, RoadmapSummariesResponse)

    async def summarize_ticket_history(self, context: dict) -> TicketSignature:
        """Summarize one historic ticket into a compact reusable signature.

        Parameters:
            context: Ticket context ({ticket_id, subject, description, status,
                priority, conversations:[{kind, body_text}]}).

        Returns:
            Validated ticket signature (problem/category/root_cause/resolution).

        Edge cases:
            Missing OpenAI key returns a deterministic mock signature so the
            knowledge pipeline runs locally without credentials.
        """
        if self._client is None:
            return TicketSignature(
                problem=str(context.get("subject") or "Mock problem"),
                category="general",
                root_cause="unknown",
                resolution="unresolved" if context.get("status") not in ("resolved", "closed") else "resolved",
                product_area="",
                tags=["mock"],
            )
        return await self._json_completion("insights_signature_v1.txt", context, TicketSignature)

    async def cluster_ticket_signatures(self, signatures: list[dict]) -> ClusterPlan:
        """Group ticket signatures into recurring themes.

        Parameters:
            signatures: List of {key, problem, category, product_area, tags}.

        Returns:
            Clustering plan (theme titles + the ticket keys they contain).

        Edge cases:
            Missing OpenAI key returns a single mock cluster with every key, so
            the reduce phase still produces output locally.
        """
        if self._client is None:
            return ClusterPlan(
                clusters=[ClusterGroup(title="All tickets", ticket_keys=[str(s.get("key")) for s in signatures])]
            )
        return await self._json_completion("insights_cluster_v1.txt", {"tickets": signatures}, ClusterPlan)

    async def consolidate_themes(self, context: dict) -> ConsolidationPlan:
        """Merge fragmented candidate cluster titles into a canonical taxonomy.

        Parameters:
            context: {labels:[{title, count}], target_min, target_max}.

        Returns:
            Canonical groups, each mapping to the candidate titles it absorbs.

        Edge cases:
            Missing OpenAI key returns an identity mapping (one canonical per
            label) so local/offline behavior is unchanged.
        """
        if self._client is None:
            return ConsolidationPlan(
                groups=[
                    ConsolidationGroup(canonical_title=str(entry.get("title")), members=[str(entry.get("title"))])
                    for entry in context.get("labels", [])
                ]
            )
        return await self._json_completion("insights_consolidate_v1.txt", context, ConsolidationPlan)

    async def write_theme_doc(self, context: dict) -> ThemeDoc:
        """Write a knowledge-base document for one theme cluster.

        Parameters:
            context: {title, signatures:[{problem, root_cause, resolution, product_area}]}.

        Returns:
            Validated theme document (summary/symptoms/root_causes/resolution_steps).

        Edge cases:
            Missing OpenAI key returns a deterministic mock document.
        """
        if self._client is None:
            title = str(context.get("title") or "Tema")
            n = len(context.get("signatures") or [])
            return ThemeDoc(
                title=title,
                summary=f"Resumen mock del tema '{title}' ({n} tickets).",
                symptoms="Síntomas mock.",
                root_causes="Causas mock.",
                resolution_steps="Pasos de resolución mock.",
            )
        return await self._json_completion("insights_theme_v1.txt", context, ThemeDoc)

    async def analyze_department(self, context: dict) -> DepartmentAnalysisPlan:
        """Identify a department's bottlenecks and automation opportunities.

        Parameters:
            context: {department, themes:[{title, frequency, summary}],
                metrics:[{category, volume, avg_resolution_hours, reopen_rate}]}.

        Returns:
            Bottlenecks + automation opportunities (each tagged with a category
            so the service can attach ticket references).

        Edge cases:
            Missing OpenAI key returns a deterministic mock analysis derived from
            the highest-volume metric so the department view still renders.
        """
        if self._client is None:
            metrics = context.get("metrics") or []
            top = max(metrics, key=lambda m: m.get("volume", 0), default=None)
            cat = (top or {}).get("category", "general")
            return DepartmentAnalysisPlan(
                bottlenecks=[
                    {
                        "title": f"Alto volumen en '{cat}'",
                        "description": "Análisis mock: categoría con más tickets.",
                        "severity": "medium",
                        "category": cat,
                    }
                ],
                automation=[
                    {
                        "title": f"Automatizar '{cat}'",
                        "description": "Análisis mock: patrón repetitivo candidato a automatización.",
                        "rationale": "Alto volumen recurrente.",
                        "category": cat,
                    }
                ],
            )
        return await self._json_completion("insights_department_analysis_v1.txt", context, DepartmentAnalysisPlan)

    async def _json_completion(
        self, prompt_file: str, context: Ticket | dict, schema: type[PromptModel]
    ) -> PromptModel:
        """Run an OpenAI JSON completion and validate the result.

        Parameters:
            prompt_file: Versioned prompt file name.
            context: Ticket or plain dict context serialized as the user message.
            schema: Pydantic schema used for validation.

        Returns:
            Validated AI response.

        Edge cases:
            Invalid JSON or schema mismatches become ExternalServiceError.
        """
        if self._client is None:
            raise ExternalServiceError("OpenAI client is not configured")
        prompt = self._load_prompt(prompt_file)
        context_payload = context.model_dump() if isinstance(context, BaseModel) else context
        try:
            response = await self._client.chat.completions.create(
                model=self.model,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": json.dumps(context_payload, default=str)},
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
