"""Time tracking agent."""

from datetime import date
from typing import Any

from app.agents.base import AgentContext, AgentResult, BaseAgent
from app.agents.time.extractor import TimeAgentParameterExtractor, TimeEntryParameters
from app.agents.time.schemas import TimeAgentResult, TimeEntryActionPayload
from app.core.events.base import DomainEvent
from app.core.memory.interface import MemoryConfig, MemoryFacade
from app.domain.assistant.events import TimeTrackingPrepared, TimeTrackingRequested
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
    """Agent that processes natural language time tracking requests.

    The agent can be used directly through `process()` for synchronous chat
    responses or through `handle()` for event-driven flows.

    Parameters:
        memory_facade: Memory facade factory.
        extractor: Optional parameter extractor for deterministic tests.

    Returns:
        Time agent instance.
    """

    subscribed_events = [TimeTrackingRequested]
    produced_events = [TimeTrackingPrepared]
    agent_id = "time"

    def __init__(
        self,
        memory_facade: MemoryFacade,
        clickup_time_tool = None,
        extractor: TimeAgentParameterExtractor | None = None,
    ) -> None:
        super().__init__(
            agent_id=self.agent_id,
            memory_config=MemoryConfig(short_term=True, long_term=True),
            memory_facade=memory_facade,
        )
        self._extractor = extractor or TimeAgentParameterExtractor()
        self._clickup_time_tool = clickup_time_tool

    @staticmethod
    def is_time_tracking_request(message: str) -> bool:
        """Return whether a message looks like a time-tracking request."""
        normalized = " ".join(message.lower().strip().split())
        return any(keyword in normalized for keyword in TIME_TRACKING_KEYWORDS)

    async def _handle(self, event: DomainEvent, context: AgentContext) -> AgentResult:
        if isinstance(event, TimeTrackingRequested):
            result = await self.process(event.message, event.confirmed_client, context)
            return AgentResult(
                events=[
                    TimeTrackingPrepared(
                        conversation_id=event.conversation_id,
                        success=result.success,
                        answer=result.answer,
                        preview=result.preview,
                        action_payload=result.action_payload,
                        needs_clarification=result.needs_clarification,
                        candidate_clients=result.candidate_clients,
                        metadata=event.metadata,
                    )
                ],
                summary="Processed time tracking request",
            )
        return AgentResult(summary=f"{self.agent_id} ignored event {type(event).__name__}")

    async def process(
        self,
        message: str,
        confirmed_client: str | None = None,
        context: AgentContext | None = None,
    ) -> TimeAgentResult:
        """Process a user message and return a time agent result.

        Parameters:
            message: Natural language time tracking request.
            confirmed_client: Optional client name confirmed by the user.
            context: Optional agent context with tools.

        Returns:
            TimeAgentResult compatible with existing assistant services.
        """
        parameters = self._extractor.extract(message)

        if confirmed_client is not None:
            parameters.client_name = confirmed_client

        if not parameters.is_complete():
            missing = parameters.missing_fields()
            return TimeAgentResult(
                success=False,
                answer=f"Necesito más datos para imputar el tiempo. Falta: {', '.join(missing)}.",
                needs_clarification=True,
                candidate_clients=[],
            )

        if context is not None:
            clarification = await self._resolve_client(parameters, context)
            if clarification is not None:
                return TimeAgentResult(**clarification)

        result = await self._build_success_result(parameters, context)
        return TimeAgentResult(**result)

    async def _resolve_client(
        self,
        parameters: TimeEntryParameters,
        context: AgentContext,
    ) -> dict[str, Any] | None:
        """Resolve the client name using the clickup_time tool.

        Client is optional. If the user did not mention a client, no
        resolution is attempted. If the user mentioned a client and it cannot
        be matched, a clarification is returned.
        """
        requested_client = parameters.client_name.strip()

        if not requested_client:
            return None

        tool = self._get_clickup_time_tool(context)
        result: ToolResult = await tool.execute(operation="get_clients")
        if not result.success or result.data is None:
            return None

        available_clients = result.data.get("clients", [])
        if not available_clients:
            return None

        best_name, best_score = self._rank_client(requested_client, available_clients)
        exact_threshold = 0.85
        candidate_threshold = 0.4

        if best_score >= exact_threshold:
            parameters.client_name = best_name
            return None

        candidates = [name for name, score in self._rank_all_clients(requested_client, available_clients) if score >= candidate_threshold][:5]
        if candidates:
            candidates_text = ", ".join(f"'{name}'" for name in candidates)
            return {
                "success": False,
                "answer": f"No encontré '{requested_client}' exactamente. ¿Te refieres a alguno de estos: {candidates_text}? Responde con el nombre correcto.",
                "needs_clarification": True,
                "candidate_clients": candidates,
            }

        return {
            "success": False,
            "answer": f"No encontré '{requested_client}' en la lista de clientes de ClickUp. ¿Para qué cliente quieres imputar el tiempo?",
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
        context: AgentContext | None,
    ) -> dict[str, Any]:
        """Build a successful time agent result with preview and action payload."""
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
        answer = (
            f"He preparado una imputación de {hours}h {minutes}m{client_line} "
            f"para '{parameters.task_name}' el {parameters.start_date}. "
            f"Revisa y aprueba para crear la tarea y registrar el tiempo en ClickUp."
        )

        return {
            "success": True,
            "answer": answer,
            "preview": preview,
            "action_payload": action_payload,
            "needs_clarification": False,
            "candidate_clients": [],
        }
