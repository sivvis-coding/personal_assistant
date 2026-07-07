"""Time tracking agent."""

from datetime import date
from typing import Any

from app.agents.base import AgentContext, AgentResult, BaseAgent
from app.agents.time.llm_extractor import DailyNarrativeExtractor
from app.agents.time.schemas import ActivityResolution, TimeAgentResult, TimeEntryActionPayload, TimeEntryParameters
from app.core.events.base import DomainEvent
from app.core.memory.interface import MemoryConfig, MemoryFacade
from app.domain.assistant.events import TimeTrackingPrepared, TimeTrackingRequested
from app.services.settings_service import SettingsService
from app.tools.base import ToolResult

TIME_TRACKING_KEYWORDS = {
    "imputa",
    "imputar",
    "registra tiempo",
    "registrar tiempo",
    "apunta tiempo",
    "anota tiempo",
    "guarda tiempo",
    "horas en clickup",
    "time tracking",
    "timesheet",
}


class TimeAgent(BaseAgent):
    """Agent that turns a free-text daily narrative into ClickUp time entries.

    A single message may describe several activities for different clients.
    The agent extracts each activity via an LLM, resolves the client per
    activity against the configured personal ClickUp list, and returns one
    ActivityResolution per activity — ready ones can be proposed as pending
    `save_time_entry` actions, ambiguous ones need a follow-up client
    confirmation (see `resolve_pending_activity`).

    Parameters:
        memory_facade: Memory facade factory.
        narrative_extractor: LLM-based extractor that segments a message into activities.
        settings_service: Service used to resolve the configured personal ClickUp list.
        clickup_time_tool: Optional fallback tool instance when no AgentContext is provided.

    Returns:
        Time agent instance.
    """

    subscribed_events = [TimeTrackingRequested]
    produced_events = [TimeTrackingPrepared]
    agent_id = "time"

    def __init__(
        self,
        memory_facade: MemoryFacade,
        narrative_extractor: DailyNarrativeExtractor,
        settings_service: SettingsService,
        clickup_time_tool=None,
    ) -> None:
        super().__init__(
            agent_id=self.agent_id,
            memory_config=MemoryConfig(short_term=True, long_term=True),
            memory_facade=memory_facade,
        )
        self._narrative_extractor = narrative_extractor
        self._settings_service = settings_service
        self._clickup_time_tool = clickup_time_tool

    @staticmethod
    def is_time_tracking_request(message: str) -> bool:
        """Return whether a message looks like a time-tracking request."""
        normalized = " ".join(message.lower().strip().split())
        return any(keyword in normalized for keyword in TIME_TRACKING_KEYWORDS)

    async def _handle(self, event: DomainEvent, context: AgentContext) -> AgentResult:
        if isinstance(event, TimeTrackingRequested):
            result = await self.process(event.message, context)
            return AgentResult(
                events=[
                    TimeTrackingPrepared(
                        conversation_id=event.conversation_id,
                        success=result.success,
                        answer=result.answer,
                    )
                ],
                summary="Processed time tracking request",
            )
        return AgentResult(summary=f"{self.agent_id} ignored event {type(event).__name__}")

    async def process(
        self,
        message: str,
        context: AgentContext | None = None,
        target_date: date | None = None,
    ) -> TimeAgentResult:
        """Process a daily narrative and return one resolution per detected activity.

        Parameters:
            message: Natural language daily narrative in Spanish, possibly describing
                several activities.
            context: Optional agent context with tools.
            target_date: Day this narrative is scoped to, if the conversation was
                started for a specific day (e.g. from a calendar click). When set,
                activities with no date mentioned default to it instead of being
                reported as missing, and relative words ("hoy") resolve against it.

        Returns:
            TimeAgentResult with one ActivityResolution per detected activity.

        Edge cases:
            Returns a single failed result (no activities) when the personal ClickUp
            list is not configured or the narrative has no identifiable work.
        """
        list_id = await self._resolve_personal_list_id()
        if not list_id:
            return TimeAgentResult(
                success=False,
                answer=(
                    "No tengo configurada tu lista personal de ClickUp. "
                    "Ve a Configuración y selecciona una en 'Lista personal (imputación de horas)'."
                ),
                activities=[],
            )

        available_clients = await self._get_available_clients(list_id, context)
        extracted = await self._narrative_extractor.extract(
            message,
            today=target_date or date.today(),
            known_clients=available_clients,
            assume_today_if_missing=target_date is not None,
        )
        if not extracted:
            return TimeAgentResult(
                success=False,
                answer=(
                    "No he identificado ninguna actividad de trabajo en tu mensaje. "
                    "Cuéntame qué hiciste, con cuánto tiempo y para qué cliente."
                ),
                activities=[],
            )

        resolutions = [
            await self._resolve_activity(parameters, None, list_id, available_clients, context)
            for parameters in extracted
        ]
        return self._combine(resolutions, list_id)

    async def resolve_pending_activity(
        self,
        parameters: TimeEntryParameters,
        confirmed_client: str,
        list_id: str,
        context: AgentContext | None = None,
    ) -> ActivityResolution:
        """Continue a single previously-extracted activity with a confirmed client.

        Parameters:
            parameters: Time entry parameters extracted earlier for this activity.
            confirmed_client: Client name confirmed by the user for this activity.
            list_id: Personal ClickUp list ID to resolve the client field against.
            context: Optional agent context with tools.

        Returns:
            Resolution for this single activity, without re-running extraction.
        """
        available_clients = await self._get_available_clients(list_id, context)
        return await self._resolve_activity(parameters, confirmed_client, list_id, available_clients, context)

    async def complete_pending_activities(
        self,
        pending_activities: list[TimeEntryParameters],
        message: str,
        list_id: str,
        context: AgentContext | None = None,
        target_date: date | None = None,
    ) -> TimeAgentResult:
        """Fill in missing fields on previously-extracted activities from a follow-up reply.

        Unlike `process`, this does not re-segment the accumulated narrative
        from scratch — it merges the follow-up message into the activities
        already extracted, preserving fields already known (task, description,
        client) instead of risking the LLM re-deriving (and potentially
        dropping) them on every round.

        Parameters:
            pending_activities: Activities extracted in a previous turn, some fields possibly empty.
            message: The user's follow-up reply.
            list_id: Personal ClickUp list ID these activities belong to.
            context: Optional agent context with tools.
            target_date: Day this conversation is scoped to, if any — still-missing
                dates default to it instead of being reported as missing.

        Returns:
            TimeAgentResult with one ActivityResolution per activity, same order as input.
        """
        available_clients = await self._get_available_clients(list_id, context)
        updated = await self._narrative_extractor.complete(
            pending_activities,
            message,
            today=target_date or date.today(),
            known_clients=available_clients,
            assume_today_if_missing=target_date is not None,
        )
        resolutions = [
            await self._resolve_activity(parameters, None, list_id, available_clients, context)
            for parameters in updated
        ]
        return self._combine(resolutions, list_id)

    async def _get_available_clients(self, list_id: str, context: AgentContext | None) -> list[str]:
        """Fetch the valid client names configured on the personal ClickUp list.

        Parameters:
            list_id: Personal ClickUp list ID.
            context: Optional agent context with tools.

        Returns:
            Client names, or an empty list when the field is missing, free-text,
            or the tool call fails (callers fall back to free-text client names).
        """
        tool = self._get_clickup_time_tool(context)
        result: ToolResult = await tool.execute(operation="get_clients", list_id=list_id)
        if not result.success or result.data is None:
            return []
        return result.data.get("clients", [])

    def _combine(self, resolutions: list[ActivityResolution], list_id: str) -> TimeAgentResult:
        """Combine per-activity resolutions into one overall result and answer."""
        resolved = [r for r in resolutions if r.success and not r.needs_clarification]
        pending = [r for r in resolutions if r.needs_clarification]
        incomplete = [r for r in resolutions if not r.success and not r.needs_clarification]

        lines: list[str] = []
        if resolved:
            summary = "; ".join(r.answer for r in resolved)
            lines.append(f"He preparado {len(resolved)} imputación(es): {summary}")
        if incomplete:
            lines.append(" ".join(r.answer for r in incomplete))
        if pending:
            lines.append(pending[0].answer)
            if len(pending) > 1:
                lines.append(f"(quedan {len(pending) - 1} actividad(es) más por confirmar)")
        if not lines:
            lines.append("No he podido procesar ninguna actividad.")

        return TimeAgentResult(success=bool(resolved), answer=" ".join(lines), activities=resolutions, list_id=list_id)

    async def _resolve_personal_list_id(self) -> str:
        """Return the configured personal ClickUp list ID, or empty when unset."""
        app_settings = await self._settings_service.get_settings()
        return app_settings.clickup_personal_list_id

    async def _resolve_activity(
        self,
        parameters: TimeEntryParameters,
        confirmed_client: str | None,
        list_id: str,
        available_clients: list[str],
        context: AgentContext | None,
    ) -> ActivityResolution:
        """Resolve a single activity: validate completeness, then resolve its client."""
        if confirmed_client is not None:
            parameters.client_name = confirmed_client

        if not parameters.is_complete():
            missing = parameters.missing_fields()
            label = parameters.task_name or parameters.description or "una actividad"
            return ActivityResolution(
                success=False,
                answer=f"Para '{label}' necesito más datos: {', '.join(missing)}.",
                parameters=parameters,
            )

        clarification = self._resolve_client(parameters, available_clients)
        if clarification is not None:
            return ActivityResolution(parameters=parameters, **clarification)

        return await self._build_success_result(parameters, list_id, context)

    def _resolve_client(
        self,
        parameters: TimeEntryParameters,
        available_clients: list[str],
    ) -> dict[str, Any] | None:
        """Resolve the client name against the valid clients for this list.

        Client is optional. If the user did not mention a client (or the LLM
        could not confidently map one from context), no resolution is
        attempted. If a client was extracted but does not match the valid
        list closely enough, a clarification is returned.
        """
        requested_client = parameters.client_name.strip()

        if not requested_client:
            return None

        if not available_clients:
            return None

        best_name, best_score = self._rank_client(requested_client, available_clients)
        exact_threshold = 0.85
        candidate_threshold = 0.4
        task_label = parameters.task_name or "esta actividad"

        if best_score >= exact_threshold:
            parameters.client_name = best_name
            return None

        candidates = [
            name
            for name, score in self._rank_all_clients(requested_client, available_clients)
            if score >= candidate_threshold
        ][:5]
        if candidates:
            candidates_text = ", ".join(f"'{name}'" for name in candidates)
            return {
                "success": False,
                "answer": (
                    f"Para '{task_label}' no encontré el cliente '{requested_client}' exactamente. "
                    f"¿Te refieres a alguno de estos: {candidates_text}? Responde con el nombre correcto."
                ),
                "needs_clarification": True,
                "candidate_clients": candidates,
            }

        return {
            "success": False,
            "answer": (
                f"Para '{task_label}' no encontré '{requested_client}' en la lista de clientes de ClickUp. "
                "¿Para qué cliente es esta actividad?"
            ),
            "needs_clarification": True,
            "candidate_clients": [],
        }

    def _get_clickup_time_tool(self, context: AgentContext | None):
        """Return the clickup_time tool from context or the injected fallback."""
        if context is not None:
            return context.get_tool("clickup_time")
        if self._clickup_time_tool is None:
            raise RuntimeError("TimeAgent requires a clickup_time tool when no context is provided")
        return self._clickup_time_tool

    def _rank_client(self, input_name: str, available: list[str]) -> tuple[str, float]:
        """Return the best matching client and its score."""
        ranked = self._rank_all_clients(input_name, available)
        if not ranked:
            return ("", 0.0)
        return ranked[0]

    def _rank_all_clients(self, input_name: str, available: list[str]) -> list[tuple[str, float]]:
        """Rank available client names by similarity to the user input."""
        from difflib import SequenceMatcher

        input_lower = input_name.lower()
        scored: list[tuple[str, float]] = []
        for name in available:
            name_lower = name.lower()
            if name_lower == input_lower:
                scored.append((name, 1.0))
                continue
            if input_lower in name_lower or name_lower in input_lower:
                longer = max(len(input_lower), len(name_lower))
                shorter = min(len(input_lower), len(name_lower))
                score = 0.88 + 0.12 * (shorter / longer)
                scored.append((name, score))
                continue
            similarity = SequenceMatcher(None, input_lower, name_lower).ratio()
            scored.append((name, similarity))
        return sorted(scored, key=lambda item: item[1], reverse=True)

    async def _build_success_result(
        self,
        parameters: TimeEntryParameters,
        list_id: str,
        context: AgentContext | None,
    ) -> ActivityResolution:
        """Build a successful activity resolution with preview and action payload."""
        start_iso = parameters.build_start_datetime().strftime("%Y-%m-%dT%H:%M:%S")
        end_iso = parameters.build_end_datetime().strftime("%Y-%m-%dT%H:%M:%S")

        preview: dict[str, Any] = {}
        tool = self._get_clickup_time_tool(context)
        result: ToolResult = await tool.execute(
            operation="prepare",
            task_name=parameters.task_name,
            description=parameters.description,
            start_datetime=start_iso,
            end_datetime=end_iso,
            client_name=parameters.client_name,
        )
        if result.success and result.data is not None:
            preview = result.data

        action_payload = TimeEntryActionPayload(
            task_name=parameters.task_name,
            description=parameters.description,
            start_datetime=start_iso,
            end_datetime=end_iso,
            client_name=parameters.client_name,
        ).model_dump()

        duration = preview.get("duration_minutes", parameters.duration_minutes)
        hours, minutes = divmod(duration, 60)
        client_line = f" para el cliente '{parameters.client_name}'" if parameters.client_name else ""
        answer = f"'{parameters.task_name}': {hours}h {minutes}m{client_line} el {parameters.start_date}"

        return ActivityResolution(
            success=True,
            answer=answer,
            parameters=parameters,
            preview=preview,
            action_payload=action_payload,
            needs_clarification=False,
            candidate_clients=[],
        )
