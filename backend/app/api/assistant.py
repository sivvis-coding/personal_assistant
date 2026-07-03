import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.api.deps import (
    get_assistant_action_executor,
    get_assistant_action_repository,
    get_assistant_action_tool,
    get_assistant_conversation_service,
    get_time_agent,
    require_auth,
)
from app.assistant.action_executor import AssistantActionExecutor
from app.agents.time.agent import TimeAgent
from app.assistant.schemas.actions import AssistantAction, AssistantActionCreate
from app.assistant.schemas.conversation import (
    AssistantConversationCreateResponse,
    AssistantMessageRequest,
    AssistantMessageResponse,
    ConversationDetailResponse,
    ConversationSummaryResponse,
)
from app.assistant.schemas.time_agent import TimeTrackingProcessResponse, TimeTrackingRequest
from app.assistant.conversation_service import AssistantConversationService
from app.repositories.assistant_action_repository import AssistantActionRepository
from app.tools.assistant_action.tool import AssistantActionTool
from app.tools.base import ToolResult

router = APIRouter(prefix="/assistant", tags=["assistant"], dependencies=[Depends(require_auth)])


@router.post("/conversations", response_model=AssistantConversationCreateResponse)
async def create_conversation(service: AssistantConversationService = Depends(get_assistant_conversation_service)) -> AssistantConversationCreateResponse:
    """Create a new assistant conversation.

    Parameters:
        service: Assistant conversation service dependency.

    Returns:
        Created conversation identifier.

    Edge cases:
        Authentication is enforced by router dependency.
    """
    conversation_id = await service.create_conversation()
    return AssistantConversationCreateResponse(conversation_id=conversation_id)


@router.get("/conversations", response_model=list[ConversationSummaryResponse])
async def list_conversations(service: AssistantConversationService = Depends(get_assistant_conversation_service)) -> list[ConversationSummaryResponse]:
    """List all conversation summaries ordered by most recent.

    Parameters:
        service: Assistant conversation service dependency.

    Returns:
        List of conversation summaries.

    Edge cases:
        Empty list when no conversations exist.
    """
    return await service.list_conversations()


@router.get("/conversations/{conversation_id}", response_model=ConversationDetailResponse)
async def get_conversation(
    conversation_id: str,
    service: AssistantConversationService = Depends(get_assistant_conversation_service),
) -> ConversationDetailResponse:
    """Get a complete conversation with all messages.

    Parameters:
        conversation_id: Conversation identifier.
        service: Assistant conversation service dependency.

    Returns:
        Complete conversation with all messages.

    Edge cases:
        Unknown conversation IDs return HTTP 404.
    """
    try:
        return await service.get_conversation(conversation_id)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@router.post("/conversations/{conversation_id}/messages", response_model=AssistantMessageResponse)
async def send_message(
    conversation_id: str,
    request: AssistantMessageRequest,
    service: AssistantConversationService = Depends(get_assistant_conversation_service),
) -> AssistantMessageResponse:
    """Send a message to the assistant.

    Parameters:
        conversation_id: Conversation identifier.
        request: User message payload.
        service: Assistant conversation service dependency.

    Returns:
        Assistant response with recommendations and proposed actions.

    Edge cases:
        Invalid conversation IDs return HTTP 400.
    """
    try:
        return await service.handle_message(conversation_id, request.message)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error


@router.delete("/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conversation_id: str,
    service: AssistantConversationService = Depends(get_assistant_conversation_service),
) -> None:
    """Permanently delete a conversation and all its messages."""
    deleted = await service.delete_conversation(conversation_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")


@router.post("/conversations/{conversation_id}/messages/stream")
async def stream_message(
    conversation_id: str,
    request: AssistantMessageRequest,
    service: AssistantConversationService = Depends(get_assistant_conversation_service),
) -> StreamingResponse:
    """Stream assistant response tokens via Server-Sent Events.

    Yields 'token' events as text is generated, then a 'done' event with the
    full structured response (proposed_actions, next_suggestions, etc.).
    """
    async def generate():
        try:
            async for event in service.handle_message_stream(conversation_id, request.message):
                yield f"data: {json.dumps(event, default=str)}\n\n"
        except Exception as exc:  # noqa: BLE001
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


class AssistantActionPayloadUpdateRequest(BaseModel):
    """Payload update request for an assistant action before approval.

    Parameters:
        payload: New payload to store on the pending action.

    Returns:
        Validated payload update input.

    Edge cases:
        Only proposed actions may be updated.
    """

    payload: dict[str, Any]


class DirectActionCreateRequest(BaseModel):
    """Direct action creation request (bypasses the conversation agent)."""

    action_type: str
    title: str
    description: str
    ticket_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


@router.post("/actions", response_model=AssistantAction, status_code=status.HTTP_201_CREATED)
async def create_action(
    request: DirectActionCreateRequest,
    repository: AssistantActionRepository = Depends(get_assistant_action_repository),
) -> AssistantAction:
    """Create a pending action directly without going through the conversation agent."""
    action = AssistantActionCreate(
        action_type=request.action_type,
        title=request.title,
        description=request.description,
        ticket_id=request.ticket_id,
        payload=request.payload,
    )
    return await repository.create_action(action)


@router.get("/actions/pending", response_model=list[AssistantAction])
async def list_pending_actions(repository: AssistantActionRepository = Depends(get_assistant_action_repository)) -> list[AssistantAction]:
    """List assistant actions pending approval.

    Parameters:
        repository: Assistant action repository dependency.

    Returns:
        Pending assistant actions.

    Edge cases:
        Empty list means no action requires review.
    """
    return await repository.list_pending()


@router.patch("/actions/{action_id}", response_model=AssistantAction)
async def update_action_payload(
    action_id: str,
    request: AssistantActionPayloadUpdateRequest,
    repository: AssistantActionRepository = Depends(get_assistant_action_repository),
) -> AssistantAction:
    """Update the payload of a pending action before approval.

    Parameters:
        action_id: Assistant action identifier.
        request: New payload to store.
        repository: Assistant action repository dependency.

    Returns:
        Updated assistant action.

    Edge cases:
        Non-proposed actions return HTTP 400.
    """
    action = await repository.get_action(action_id)
    if action is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Action not found")
    if action.status != "proposed":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only proposed actions can be edited")
    try:
        return await repository.update_payload(action_id, request.payload)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error


@router.post("/actions/{action_id}/approve", response_model=AssistantAction)
async def approve_action(action_id: str, executor: AssistantActionExecutor = Depends(get_assistant_action_executor)) -> AssistantAction:
    """Approve and execute one assistant action.

    Parameters:
        action_id: Assistant action identifier.
        executor: Assistant action executor dependency.

    Returns:
        Updated assistant action.

    Edge cases:
        Prepare actions only generate a second approval action for final ClickUp creation.
    """
    try:
        return await executor.approve(action_id)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error


@router.post("/actions/{action_id}/reject", response_model=AssistantAction)
async def reject_action(action_id: str, executor: AssistantActionExecutor = Depends(get_assistant_action_executor)) -> AssistantAction:
    """Reject one proposed assistant action.

    Parameters:
        action_id: Assistant action identifier.
        executor: Assistant action executor dependency.

    Returns:
        Rejected assistant action.

    Edge cases:
        Already completed actions cannot be undone by this endpoint.
    """
    try:
        return await executor.reject(action_id)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error


@router.post("/time-tracking/process", response_model=TimeTrackingProcessResponse)
async def process_time_tracking_request(
    request: TimeTrackingRequest,
    agent: TimeAgent = Depends(get_time_agent),
    assistant_action_tool: AssistantActionTool = Depends(get_assistant_action_tool),
) -> TimeTrackingProcessResponse:
    """Process a natural language time tracking request and create a pending action.

    Parameters:
        request: Natural language time tracking request.
        agent: Time agent dependency.
        assistant_action_tool: Tool for creating pending assistant actions.

    Returns:
        Processing result with optional preview and pending action for the first
        resolved activity. A narrative describing several activities creates a
        pending action for each one, but only the first is returned here —
        use the chat endpoint (`/assistant/conversations/{id}/messages`) to see
        and approve all of them.

    Edge cases:
        Incomplete requests, or requests with no fully resolved activity, return success=False.
    """
    result = await agent.process(request.message)

    resolved = [a for a in result.activities if a.success and not a.needs_clarification]
    if not resolved:
        return TimeTrackingProcessResponse(success=False, answer=result.answer)

    first = resolved[0]
    tool_result: ToolResult = await assistant_action_tool.execute(
        operation="create",
        action_type="save_time_entry",
        title=f"Imputar {first.preview['duration_minutes']} min en ClickUp",
        description=first.answer,
        payload=first.action_payload,
    )

    if not tool_result.success or tool_result.data is None:
        return TimeTrackingProcessResponse(success=False, answer="No se pudo crear la acción pendiente. Inténtalo de nuevo.")

    action = AssistantAction.model_validate(tool_result.data)

    return TimeTrackingProcessResponse(
        success=True,
        answer=result.answer,
        preview=first.preview,
        proposed_action=action,
    )
