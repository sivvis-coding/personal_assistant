from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

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
from app.assistant.schemas.actions import AssistantAction
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
        Processing result with optional preview and pending action.

    Edge cases:
        Incomplete requests return success=False and no pending action.
    """
    result = await agent.process(request.message)

    if not result.success:
        return TimeTrackingProcessResponse(success=False, answer=result.answer)

    if result.preview is None or "duration_minutes" not in result.preview:
        return TimeTrackingProcessResponse(
            success=False,
            answer="No se pudo generar la vista previa del registro de tiempo.",
        )

    tool_result: ToolResult = await assistant_action_tool.execute(
        operation="create",
        action_type="save_time_entry",
        title=f"Imputar {result.preview['duration_minutes']} min en ClickUp",
        description=result.answer,
        payload=result.action_payload,
    )

    if not tool_result.success or tool_result.data is None:
        return TimeTrackingProcessResponse(success=False, answer="No se pudo crear la acción pendiente. Inténtalo de nuevo.")

    action = AssistantAction.model_validate(tool_result.data)

    return TimeTrackingProcessResponse(
        success=True,
        answer=result.answer,
        preview=result.preview,
        proposed_action=action,
    )
