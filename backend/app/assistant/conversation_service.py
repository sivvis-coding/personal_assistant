import logging
from collections.abc import AsyncIterator
from datetime import date

from app.agents.conversation.agent import ConversationAgent
from app.agents.conversation.schemas import ConversationResponse
from app.agents.time.agent import TimeAgent
from app.agents.time.schemas import ActivityResolution, TimeAgentResult, TimeEntryParameters
from app.assistant.context_builder import AssistantContextBuilder
from app.assistant.schemas.actions import AssistantAction, AssistantActionCreate
from app.assistant.schemas.conversation import AssistantMessageResponse, ConversationDetailResponse, ConversationSummaryResponse
from app.assistant.schemas.recommendations import PrioritizedWorkPlan
from app.core.memory.interface import UserMemory
from app.repositories.conversation_repository import ConversationRepository
from app.tools.assistant_action.tool import AssistantActionTool
from app.tools.base import ToolInterface, ToolRegistry, ToolResult


logger = logging.getLogger(__name__)

# Phrases that let the user back out of a pending follow-up (client confirmation
# or narrative completion) instead of having the whole message consumed as a reply
# to it. When matched, the pending state is cleared and the message is routed
# normally, so "olvídalo, revisa mis tickets" changes topic cleanly.
CANCELLATION_PHRASES = (
    "cancela",
    "cancelar",
    "olvidalo",
    "olvídalo",
    "olvida",
    "dejalo",
    "déjalo",
    "deja eso",
    "no importa",
    "da igual",
    "mejor no",
    "cambia de tema",
    "otra cosa",
)


def _is_cancellation(message: str) -> bool:
    """Return whether a message backs out of a pending follow-up.

    Matches only at the start of the message (or the whole message) so ordinary
    replies that merely contain a word like "cancela" are not misread as a cancel.
    """
    normalized = " ".join(message.lower().strip().split())
    return any(
        normalized == phrase or normalized.startswith(f"{phrase} ") or normalized.startswith(f"{phrase},")
        for phrase in CANCELLATION_PHRASES
    )


class AssistantConversationService:
    """Coordinate assistant conversation turns.

    Parameters:
        conversation_repository: Repository for conversation messages.
        assistant_action_tool: Tool for creating pending assistant actions.
        context_builder: Builder for current operational context.
        conversation_agent: LLM-backed agent for general messages.
        time_agent: Agent specialized in time tracking requests.

    Returns:
        Service used by assistant API routes.

    Edge cases:
        Proposed actions are persisted before returning so frontend approvals reference durable IDs.
    """

    # Tools exposed to the conversation agent for live data lookups.
    _CHAT_TOOL_NAMES = {"freshservice", "clickup", "clickup_time"}

    def __init__(
        self,
        conversation_repository: ConversationRepository,
        assistant_action_tool: AssistantActionTool,
        context_builder: AssistantContextBuilder,
        conversation_agent: ConversationAgent,
        time_agent: TimeAgent,
        tool_registry: ToolRegistry,
        user_prefs: UserMemory | None = None,
    ) -> None:
        """Initialize the conversation service.

        Parameters:
            conversation_repository: Repository for persisted conversation turns.
            assistant_action_tool: Tool used to create pending actions for approval.
            context_builder: Builder for operational assistant context.
            conversation_agent: LLM-backed agent for general messages.
            time_agent: Agent specialized in time tracking requests.
            tool_registry: Registry of available tools.
            user_prefs: Optional user preferences store for reading and writing memories.

        Returns:
            None.

        Edge cases:
            Dependencies are injected explicitly to keep tests free of hidden state.
        """
        self._conversation_repository = conversation_repository
        self._assistant_action_tool = assistant_action_tool
        self._context_builder = context_builder
        self._conversation_agent = conversation_agent
        self._time_agent = time_agent
        self._tool_registry = tool_registry
        self._user_prefs = user_prefs

    async def list_conversations(self) -> list[ConversationSummaryResponse]:
        """List all conversation summaries ordered by most recent.

        Parameters:
            None.

        Returns:
            List of conversation summaries.

        Edge cases:
            Empty list when no conversations exist.
        """
        raw = await self._conversation_repository.list_conversations()
        return [
            ConversationSummaryResponse(
                id=c["id"],
                title=c["title"],
                message_count=c["message_count"],
                updated_at=c["updated_at"],
            )
            for c in raw
        ]

    async def get_conversation(self, conversation_id: str) -> ConversationDetailResponse:
        """Get a complete conversation with all messages.

        Parameters:
            conversation_id: Conversation identifier.

        Returns:
            Complete conversation with messages.

        Edge cases:
            Raises ValueError if conversation not found.
        """
        raw = await self._conversation_repository.get_conversation(conversation_id)
        if raw is None:
            raise ValueError(f"Conversation {conversation_id} not found")

        return ConversationDetailResponse(
            id=raw["id"],
            title=raw.get("title", "Sin título"),
            messages=[
                {
                    "user_message": m["user_message"],
                    "assistant_answer": m["assistant_answer"],
                    "created_at": m["created_at"],
                }
                for m in raw.get("messages", [])
            ],
            created_at=raw["created_at"],
            updated_at=raw["updated_at"],
            target_date=raw.get("target_date"),
        )

    async def create_conversation(self, target_date: date | None = None) -> str:
        """Create a new assistant conversation.

        Parameters:
            target_date: Optional day this conversation is scoped to (e.g. started
                from a calendar click), so time-tracking messages default their
                date to it instead of requiring it to be spelled out every time.

        Returns:
            Conversation ID.

        Edge cases:
            Conversation has no operational context until the first message.
        """
        return await self._conversation_repository.create_conversation(target_date)

    async def handle_message(self, conversation_id: str, message: str) -> AssistantMessageResponse:
        """Handle a user message and return the assistant response.

        Parameters:
            conversation_id: Existing conversation ID.
            message: User message text.

        Returns:
            Assistant message response with recommendations and proposed actions.

        Edge cases:
            Time tracking requests are routed to the TimeAgent.
            Pending clarification state is checked before routing.
        """
        pending_state = await self._conversation_repository.get_pending_state(conversation_id)
        target_date = await self._conversation_repository.get_target_date(conversation_id)

        if pending_state is not None and _is_cancellation(message):
            # Let the user back out of a pending follow-up and change topic cleanly
            # instead of consuming this message as a reply to it.
            await self._conversation_repository.set_pending_state(conversation_id, None)
        elif pending_state is not None and pending_state.get("type") == "client_confirmation_queue":
            return await self._handle_client_confirmation(conversation_id, pending_state, message)
        elif pending_state is not None and pending_state.get("type") == "narrative_completion":
            return await self._handle_narrative_completion(conversation_id, pending_state, message, target_date)

        time_result = await self._maybe_process_time_tracking(message, target_date)
        if time_result is not None:
            return await self._finish_time_tracking_message(conversation_id, message, time_result)

        context = await self._context_builder.build()
        message_history = await self._conversation_repository.get_messages(conversation_id, limit=10)
        chat_tools = self._chat_tools()

        try:
            conversation_result = await self._conversation_agent.respond(
                message,
                context,
                chat_tools,
                message_history,
            )
        except Exception as error:  # noqa: BLE001
            logger.exception("LLM conversation agent failed for conversation %s", conversation_id)
            return AssistantMessageResponse(
                conversation_id=conversation_id,
                answer="Lo siento, no pude procesar tu mensaje. Inténtalo de nuevo.",
                recommendations=[],
                work_plan=_empty_work_plan(),
                proposed_actions=[],
                next_suggestions=[],
            )

        actions = await self._create_actions_from_response(conversation_result)
        await self._save_memory_updates(conversation_result.memory_updates)

        await self._conversation_repository.append_turn(
            conversation_id,
            message,
            conversation_result.answer,
            {
                "recommendation_count": len(conversation_result.recommendations),
                "proposed_action_ids": [action.id for action in actions],
                "ticket_source": context.ticket_source,
                "week_time_source": context.week_time.source,
            },
        )
        return AssistantMessageResponse(
            conversation_id=conversation_id,
            answer=conversation_result.answer,
            recommendations=conversation_result.recommendations,
            work_plan=conversation_result.work_plan or _empty_work_plan(),
            proposed_actions=actions,
            needs_clarification=conversation_result.needs_clarification,
            clarification_question=conversation_result.clarification_question,
            next_suggestions=conversation_result.next_suggestions,
        )

    async def delete_conversation(self, conversation_id: str) -> bool:
        """Permanently delete a conversation."""
        return await self._conversation_repository.delete_conversation(conversation_id)

    async def handle_message_stream(
        self,
        conversation_id: str,
        message: str,
    ) -> AsyncIterator[dict]:
        """Stream a user message response as SSE events.

        Yields token events immediately as the LLM generates them, then a done event
        with the full structured response (actions, suggestions, etc.).

        Time tracking and client confirmation paths fall back to non-streaming since
        they don't call the conversation agent.
        """
        pending_state = await self._conversation_repository.get_pending_state(conversation_id)
        target_date = await self._conversation_repository.get_target_date(conversation_id)

        if pending_state is not None and _is_cancellation(message):
            await self._conversation_repository.set_pending_state(conversation_id, None)
        elif pending_state is not None and pending_state.get("type") == "client_confirmation_queue":
            response = await self._handle_client_confirmation(conversation_id, pending_state, message)
            yield {"type": "token", "text": response.answer}
            yield {"type": "done", "data": response.model_dump(mode="json")}
            return
        elif pending_state is not None and pending_state.get("type") == "narrative_completion":
            response = await self._handle_narrative_completion(conversation_id, pending_state, message, target_date)
            yield {"type": "token", "text": response.answer}
            yield {"type": "done", "data": response.model_dump(mode="json")}
            return

        time_result = await self._maybe_process_time_tracking(message, target_date)
        if time_result is not None:
            response = await self._finish_time_tracking_message(conversation_id, message, time_result)
            yield {"type": "token", "text": response.answer}
            yield {"type": "done", "data": response.model_dump(mode="json")}
            return

        context = await self._context_builder.build()
        message_history = await self._conversation_repository.get_messages(conversation_id, limit=10)
        chat_tools = self._chat_tools()

        full_response_data: dict | None = None

        try:
            async for event in self._conversation_agent.respond_stream(
                message, context, chat_tools, message_history
            ):
                if event["type"] == "token":
                    yield event
                elif event["type"] == "done":
                    full_response_data = event["data"]
                elif event["type"] == "error":
                    yield event
                    return
        except Exception:  # noqa: BLE001
            logger.exception("Streaming conversation agent failed for conversation %s", conversation_id)
            yield {"type": "error", "message": "Lo siento, no pude procesar tu mensaje. Inténtalo de nuevo."}
            return

        if full_response_data is None:
            yield {"type": "error", "message": "No se recibió respuesta del agente."}
            return

        try:
            conversation_result = ConversationResponse.model_validate(full_response_data)
        except Exception:  # noqa: BLE001
            logger.exception("ConversationResponse validation failed after stream")
            yield {"type": "error", "message": "Error validando la respuesta."}
            return

        actions = await self._create_actions_from_response(conversation_result)
        await self._save_memory_updates(conversation_result.memory_updates)

        await self._conversation_repository.append_turn(
            conversation_id,
            message,
            conversation_result.answer,
            {
                "recommendation_count": len(conversation_result.recommendations),
                "proposed_action_ids": [action.id for action in actions],
                "ticket_source": context.ticket_source,
                "week_time_source": context.week_time.source,
            },
        )

        final_response = AssistantMessageResponse(
            conversation_id=conversation_id,
            answer=conversation_result.answer,
            recommendations=conversation_result.recommendations,
            work_plan=conversation_result.work_plan or _empty_work_plan(),
            proposed_actions=actions,
            needs_clarification=conversation_result.needs_clarification,
            clarification_question=conversation_result.clarification_question,
            next_suggestions=conversation_result.next_suggestions,
        )
        yield {"type": "done", "data": final_response.model_dump(mode="json")}

    async def _maybe_process_time_tracking(
        self, message: str, target_date: date | None = None
    ) -> TimeAgentResult | None:
        """Route a message to the TimeAgent only on explicit time-tracking intent.

        The TimeAgent runs only when the message carries an explicit keyword
        ("imputa", "registra tiempo", ...). This is deliberate: previously every
        message was speculatively run through the LLM extractor, which could
        hijack ordinary chat ("ayer miré el ticket de X, ¿qué opinas?") into a
        time entry. Explicit-only routing trades that magic for predictability —
        the agent never silently reinterprets a normal message as logged hours.

        Parameters:
            message: User message text.
            target_date: Day this conversation is scoped to, if any (e.g. started
                from a calendar click) — activities with no date mentioned default
                to it instead of requiring the user to spell it out.

        Returns:
            The TimeAgentResult when the message is an explicit time request,
            or None to fall back to the conversation agent.
        """
        if not TimeAgent.is_time_tracking_request(message):
            return None
        return await self._time_agent.process(message, target_date=target_date)

    async def _finish_time_tracking_message(
        self, conversation_id: str, message: str, time_result: TimeAgentResult
    ) -> AssistantMessageResponse:
        """Persist proposed actions and pending confirmations for a TimeAgent result.

        A single message may describe several activities. Fully resolved
        activities each get their own pending `save_time_entry` action;
        activities with an ambiguous client are queued for follow-up
        confirmation, one at a time, without blocking the resolved ones.

        Parameters:
            conversation_id: Existing conversation ID.
            message: User message text.
            time_result: Result already computed by `_maybe_process_time_tracking`.

        Returns:
            Assistant message response with pending time entry actions for
            every activity that was fully resolved.

        Edge cases:
            No identifiable activity returns success=False and no pending actions.
        """
        resolved = [a for a in time_result.activities if a.success and not a.needs_clarification]
        pending = [a for a in time_result.activities if a.needs_clarification]
        incomplete = [a for a in time_result.activities if not a.success and not a.needs_clarification]
        actions = await self._create_time_entry_actions(resolved)

        if pending:
            # Client ambiguity takes priority over missing-field completion — the user
            # resolves one queued client at a time before this narrative can complete.
            await self._conversation_repository.set_pending_state(
                conversation_id,
                {
                    "type": "client_confirmation_queue",
                    "list_id": time_result.list_id,
                    "queue": [_activity_to_queue_item(activity) for activity in pending],
                },
            )
        elif incomplete:
            # Remember the structured activities (task/description/client already known)
            # so the next reply only fills in the remaining gaps, instead of forcing the
            # user to restate everything or risking the LLM re-deriving (and dropping)
            # fields — like the client — that were already correctly extracted.
            await self._conversation_repository.set_pending_state(
                conversation_id,
                {
                    "type": "narrative_completion",
                    "list_id": time_result.list_id,
                    "activities": [activity.parameters.model_dump(mode="json") for activity in incomplete],
                },
            )
        else:
            await self._conversation_repository.set_pending_state(conversation_id, None)

        await self._conversation_repository.append_turn(
            conversation_id,
            message,
            time_result.answer,
            {
                "time_tracking_success": time_result.success,
                "pending_confirmations": len(pending),
                "proposed_action_ids": [action.id for action in actions],
            },
        )
        return AssistantMessageResponse(
            conversation_id=conversation_id,
            answer=time_result.answer,
            recommendations=[],
            work_plan=_empty_work_plan(),
            proposed_actions=actions,
            next_suggestions=[],
        )

    async def _handle_narrative_completion(
        self,
        conversation_id: str,
        pending_state: dict,
        message: str,
        target_date: date | None = None,
    ) -> AssistantMessageResponse:
        """Merge a follow-up reply into previously incomplete activities.

        Users naturally answer "necesito más datos" prompts with just the
        missing pieces (e.g. "el ref tech fue de 9 a 10:30..."), often
        covering several activities in one free-text reply. The already-known
        fields (task, description, client) are passed to the LLM alongside the
        reply and explicitly preserved — only the still-missing fields
        (duration/date/time, or client if it was never resolved) are filled in.

        Parameters:
            conversation_id: Existing conversation ID.
            pending_state: Stored activities awaiting completion, with their list_id.
            message: The user's follow-up reply.
            target_date: Day this conversation is scoped to, if any — still-missing
                dates default to it instead of requiring the user to spell it out.

        Returns:
            Assistant message response, same shape as a fresh time-tracking message.
        """
        list_id = pending_state.get("list_id", "")
        pending_activities = [
            TimeEntryParameters.model_validate(activity) for activity in pending_state.get("activities", [])
        ]
        time_result = await self._time_agent.complete_pending_activities(
            pending_activities, message, list_id, target_date=target_date
        )
        return await self._finish_time_tracking_message(conversation_id, message, time_result)

    async def _handle_client_confirmation(
        self,
        conversation_id: str,
        pending_state: dict,
        confirmed_client: str,
    ) -> AssistantMessageResponse:
        """Apply a confirmed client name to the next queued ambiguous activity.

        Parameters:
            conversation_id: Existing conversation ID.
            pending_state: Stored queue of activities awaiting client confirmation.
            confirmed_client: Client name confirmed by the user for the first queued activity.

        Returns:
            Assistant message response with the resolved activity's action, if any.

        Edge cases:
            An empty confirmation cancels the entire remaining queue.
            A client that is still ambiguous keeps the activity at the head of the
            queue with a refreshed clarifying question instead of dropping it.
        """
        queue: list[dict] = pending_state.get("queue", [])
        list_id = pending_state.get("list_id", "")
        cleaned_client = confirmed_client.strip()

        if not cleaned_client or not queue:
            await self._conversation_repository.set_pending_state(conversation_id, None)
            answer = "De acuerdo, cancelo la(s) imputación(es) pendiente(s)." if queue else "No tengo ninguna imputación pendiente de confirmar."
            return AssistantMessageResponse(
                conversation_id=conversation_id,
                answer=answer,
                recommendations=[],
                work_plan=_empty_work_plan(),
                proposed_actions=[],
                next_suggestions=[],
            )

        current, *rest = queue
        parameters = TimeEntryParameters.model_validate(current["parameters"])
        resolution = await self._time_agent.resolve_pending_activity(parameters, cleaned_client, list_id)

        actions: list[AssistantAction] = []
        answer = resolution.answer

        if resolution.needs_clarification:
            new_queue = [{**current, "answer": resolution.answer, "candidate_clients": resolution.candidate_clients}] + rest
        else:
            if resolution.success:
                action = await self._create_time_entry_action(resolution)
                if action is not None:
                    actions.append(action)
            new_queue = rest
            if new_queue:
                answer = f"{answer} {new_queue[0]['answer']}"

        await self._conversation_repository.set_pending_state(
            conversation_id,
            {"type": "client_confirmation_queue", "list_id": list_id, "queue": new_queue} if new_queue else None,
        )

        await self._conversation_repository.append_turn(
            conversation_id,
            confirmed_client,
            answer,
            {
                "time_tracking_success": resolution.success,
                "needs_clarification": resolution.needs_clarification,
                "proposed_action_ids": [action.id for action in actions],
            },
        )
        return AssistantMessageResponse(
            conversation_id=conversation_id,
            answer=answer,
            recommendations=[],
            work_plan=_empty_work_plan(),
            proposed_actions=actions,
            next_suggestions=[],
        )

    async def _save_memory_updates(self, updates: list[dict]) -> None:
        """Persist key/value pairs proposed by the agent as user preferences.

        Parameters:
            updates: List of dicts with "key" and "value" fields.

        Returns:
            None.

        Edge cases:
            Entries without a "key" field are skipped.
            Individual failures are logged and do not abort the loop.
        """
        if not updates or self._user_prefs is None:
            return
        for update in updates:
            key = update.get("key")
            value = update.get("value")
            if not key:
                continue
            try:
                await self._user_prefs.set_preference(key, value)
                logger.info("Saved user preference: %s=%r", key, value)
            except Exception:  # noqa: BLE001
                logger.warning("Failed to save user preference: %s", key)

    def _chat_tools(self) -> list[ToolInterface]:
        """Return the subset of tools available to the conversation agent.

        Returns:
            List of safe read-only or preview tools for live data lookup.

        Edge cases:
            Missing tools are ignored so the agent can still respond with context.
        """
        tools: list[ToolInterface] = []
        for name in self._CHAT_TOOL_NAMES:
            if self._tool_registry.has_tool(name):
                tools.append(self._tool_registry.get(name))
        return tools

    async def _create_time_entry_action(self, activity: ActivityResolution) -> AssistantAction | None:
        """Create a pending assistant action for one resolved activity.

        Parameters:
            activity: Resolution for a single activity from the time agent.

        Returns:
            Created assistant action or None when the activity is not resolved
            or the tool call fails.

        Edge cases:
            Unresolved or clarification-pending activities do not create actions.
        """
        if not activity.success or activity.preview is None:
            return None

        tool_result: ToolResult = await self._assistant_action_tool.execute(
            operation="create",
            action_type="save_time_entry",
            title=f"Imputar {activity.preview['duration_minutes']} min en ClickUp",
            description=activity.answer,
            payload=activity.action_payload,
        )
        if not tool_result.success or tool_result.data is None:
            logger.warning("Failed to create time entry action: %s", tool_result.message)
            return None
        return AssistantAction.model_validate(tool_result.data)

    async def _create_time_entry_actions(self, activities: list[ActivityResolution]) -> list[AssistantAction]:
        """Create pending assistant actions for every resolved activity.

        Parameters:
            activities: Resolved activities (success and not needing clarification).

        Returns:
            List of created actions. Individual tool failures are skipped, not raised.
        """
        actions: list[AssistantAction] = []
        for activity in activities:
            action = await self._create_time_entry_action(activity)
            if action is not None:
                actions.append(action)
        return actions

    async def _create_actions_from_response(
        self,
        response: ConversationResponse,
    ) -> list[AssistantAction]:
        """Create pending assistant actions proposed by the conversation agent.

        Parameters:
            response: Conversation agent response with proposed actions.

        Returns:
            List of created actions. Empty list when no actions are proposed
            or all tool calls fail.

        Edge cases:
            Tool failures for individual actions do not stop other actions.
        """
        actions: list[AssistantAction] = []
        for action_create in response.proposed_actions:
            payload = await self._with_generated_user_story(action_create)
            tool_result: ToolResult = await self._assistant_action_tool.execute(
                operation="create",
                action_type=action_create.action_type,
                title=action_create.title,
                description=action_create.description,
                payload=payload,
                ticket_id=action_create.ticket_id,
            )
            if tool_result.success and tool_result.data is not None:
                actions.append(AssistantAction.model_validate(tool_result.data))
            else:
                logger.warning("Failed to create proposed action: %s", tool_result.message)
        return actions

    async def _with_generated_user_story(self, action_create: AssistantActionCreate) -> dict:
        """Generate the ClickUp user story at propose time for task-creation actions.

        Embedding the draft in the payload lets the user review and edit it on the
        action card and approve the task in a single step (no second approval).

        Parameters:
            action_create: Proposed action from the conversation agent.

        Returns:
            The action payload, augmented with a 'user_story' for create-task
            actions. On generation failure the payload is returned unchanged; the
            executor regenerates the story as a fallback at approval time.
        """
        payload = dict(action_create.payload)
        if action_create.action_type not in ("send_ticket_to_backlog", "prepare_clickup_us"):
            return payload
        if payload.get("user_story") or not self._tool_registry.has_tool("ticket_to_clickup"):
            return payload

        tool = self._tool_registry.get("ticket_to_clickup")
        try:
            if action_create.action_type == "send_ticket_to_backlog" and action_create.ticket_id:
                result = await tool.execute(operation="prepare", ticket_id=action_create.ticket_id)
            else:
                result = await tool.execute(
                    operation="prepare_standalone", description=str(payload.get("description", ""))
                )
        except Exception:  # noqa: BLE001
            logger.warning("User story generation failed at propose time; deferring to approval.")
            return payload

        if result.success and isinstance(result.data, dict) and result.data.get("user_story"):
            payload["user_story"] = result.data["user_story"]
        return payload


def _activity_to_queue_item(activity: ActivityResolution) -> dict:
    """Serialize an ambiguous activity into a pending-state queue item."""
    return {
        "parameters": activity.parameters.model_dump(mode="json"),
        "answer": activity.answer,
        "candidate_clients": activity.candidate_clients,
    }


def _empty_work_plan() -> PrioritizedWorkPlan:
    """Return an empty prioritized work plan."""
    return PrioritizedWorkPlan(
        today_focus=[],
        next_actions=[],
        backlog_candidates=[],
        blocked_items=[],
        not_worth_actioning=[],
    )
