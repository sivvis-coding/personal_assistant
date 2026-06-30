from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import (
    get_ai_draft_repository,
    get_ai_service,
    get_clickup_client,
    get_integration_link_repository,
    get_settings,
    get_ticket_service,
    get_ticket_to_clickup_tool,
    get_workflow_run_repository,
    require_auth,
)
from app.core.config import Settings
from app.integrations.clickup import ClickUpClient
from app.integrations.fresh import FreshClient
from app.repositories.ai_draft_repository import AiDraftRepository
from app.repositories.integration_link_repository import IntegrationLinkRepository
from app.repositories.workflow_run_repository import WorkflowRunRepository
from app.schemas.ai import DraftReplyWorkflowResponse, SummaryWorkflowResponse
from app.schemas.clickup import ApproveClickUpTaskRequest, CreateClickUpTaskWorkflowResponse, PrepareClickUpTaskWorkflowResponse
from app.schemas.ticket import TicketConversationsResponse, TicketDetailResponse, TicketListResponse
from app.services.ai_service import AiService
from app.services.ticket_service import TicketService
from app.tools.ticket_to_clickup.tool import TicketToClickUpTool
from app.workflows.draft_reply import draft_reply_workflow
from app.workflows.ticket_summary import summarize_ticket_workflow

router = APIRouter(prefix="/tickets", tags=["tickets"], dependencies=[Depends(require_auth)])


@router.get("", response_model=TicketListResponse)
async def list_tickets(
    scope: Literal["mine", "all"] = Query(default="mine"),
    include_closed: bool = Query(default=False),
    ticket_service: TicketService = Depends(get_ticket_service),
) -> TicketListResponse:
    """List tickets from Fresh or mock source and cache them.

    Parameters:
        scope: Ticket visibility scope. Defaults to tickets assigned to configured Fresh agent.
        include_closed: Whether to include closed tickets. Defaults to false.
        ticket_service: Ticket service dependency.

    Returns:
        Ticket list response.

    Edge cases:
        Missing Fresh credentials return mock tickets.
    """
    return await ticket_service.list_tickets(scope, include_closed=include_closed)


@router.get("/debug/freshservice")
async def debug_freshservice(
    scope: Literal["mine", "all"] = Query(default="mine"),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Return Freshservice configuration and the request that would be executed.

    Parameters:
        scope: Ticket visibility scope.
        settings: Application settings.

    Returns:
        Debug information without secrets.

    Edge cases:
        Missing credentials are reported explicitly.
    """
    client = FreshClient(settings)
    path, params = client._build_ticket_list_request(scope)
    return {
        "has_fresh_credentials": settings.has_fresh_credentials,
        "fresh_base_url": settings.fresh_base_url,
        "fresh_assigned_agent_id": settings.fresh_assigned_agent_id,
        "fresh_assigned_agent_field": settings.fresh_assigned_agent_field,
        "fresh_workspace_id": settings.fresh_workspace_id,
        "scope": scope,
        "request": {
            "method": "GET",
            "url": f"{settings.fresh_base_url.rstrip('/')}{path}",
            "params": params,
        },
    }


@router.get("/{ticket_id}", response_model=TicketDetailResponse)
async def get_ticket(ticket_id: str, ticket_service: TicketService = Depends(get_ticket_service)) -> TicketDetailResponse:
    """Get ticket detail from Fresh, cache, or mock fallback.

    Parameters:
        ticket_id: Fresh ticket identifier.
        ticket_service: Ticket service dependency.

    Returns:
        Ticket detail response.

    Edge cases:
        Cache is used when Fresh fails.
    """
    return await ticket_service.get_ticket(ticket_id)


@router.get("/{ticket_id}/conversations", response_model=TicketConversationsResponse)
async def get_ticket_conversations(
    ticket_id: str, ticket_service: TicketService = Depends(get_ticket_service)
) -> TicketConversationsResponse:
    """Fetch conversation thread for a ticket.

    Parameters:
        ticket_id: Fresh ticket identifier.
        ticket_service: Ticket service dependency.

    Returns:
        Ticket conversations response.

    Edge cases:
        Returns 200 with items=[] and error=True when Fresh fails.
    """
    return await ticket_service.get_conversations(ticket_id)


@router.post("/{ticket_id}/summarize", response_model=SummaryWorkflowResponse)
async def summarize_ticket(
    ticket_id: str,
    ticket_service: TicketService = Depends(get_ticket_service),
    ai_service: AiService = Depends(get_ai_service),
    ai_draft_repository: AiDraftRepository = Depends(get_ai_draft_repository),
    workflow_run_repository: WorkflowRunRepository = Depends(get_workflow_run_repository),
) -> SummaryWorkflowResponse:
    """Generate and persist a ticket summary.

    Parameters:
        ticket_id: Fresh ticket identifier.
        ticket_service: Ticket service dependency.
        ai_service: AI service dependency.
        ai_draft_repository: AI draft repository dependency.
        workflow_run_repository: Workflow run repository dependency.

    Returns:
        Summary workflow response.

    Edge cases:
        Workflow failures are audited before returning HTTP 500.
    """
    try:
        return await summarize_ticket_workflow(ticket_id, ticket_service, ai_service, ai_draft_repository, workflow_run_repository)
    except Exception as error:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(error)) from error


@router.post("/{ticket_id}/draft-reply", response_model=DraftReplyWorkflowResponse)
async def draft_reply(
    ticket_id: str,
    ticket_service: TicketService = Depends(get_ticket_service),
    ai_service: AiService = Depends(get_ai_service),
    ai_draft_repository: AiDraftRepository = Depends(get_ai_draft_repository),
    workflow_run_repository: WorkflowRunRepository = Depends(get_workflow_run_repository),
) -> DraftReplyWorkflowResponse:
    """Generate and persist a customer reply draft.

    Parameters:
        ticket_id: Fresh ticket identifier.
        ticket_service: Ticket service dependency.
        ai_service: AI service dependency.
        ai_draft_repository: AI draft repository dependency.
        workflow_run_repository: Workflow run repository dependency.

    Returns:
        Draft reply response.

    Edge cases:
        Reply is not sent automatically.
    """
    try:
        return await draft_reply_workflow(ticket_id, ticket_service, ai_service, ai_draft_repository, workflow_run_repository)
    except Exception as error:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(error)) from error


@router.post("/{ticket_id}/prepare-clickup-task", response_model=PrepareClickUpTaskWorkflowResponse)
async def prepare_clickup_task(
    ticket_id: str,
    ticket_to_clickup_tool: TicketToClickUpTool = Depends(get_ticket_to_clickup_tool),
) -> PrepareClickUpTaskWorkflowResponse:
    """Prepare a ClickUp task proposal for human review.

    Parameters:
        ticket_id: Fresh ticket identifier.
        ticket_to_clickup_tool: Tool used to prepare the ClickUp task proposal.

    Returns:
        ClickUp task review response.

    Edge cases:
        This endpoint never creates a ClickUp task.
    """
    try:
        result = await ticket_to_clickup_tool.execute(operation="prepare", ticket_id=ticket_id)
        if not result.success:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=result.message)
        return PrepareClickUpTaskWorkflowResponse.model_validate(result.data)
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(error)) from error


@router.post("/{ticket_id}/approve-clickup-task", response_model=CreateClickUpTaskWorkflowResponse)
async def approve_clickup_task(
    ticket_id: str,
    request: ApproveClickUpTaskRequest,
    ticket_to_clickup_tool: TicketToClickUpTool = Depends(get_ticket_to_clickup_tool),
) -> CreateClickUpTaskWorkflowResponse:
    """Create a ClickUp task only after explicit human approval.

    Parameters:
        ticket_id: Fresh ticket identifier.
        request: Approval request containing reviewed user story.
        ticket_to_clickup_tool: Tool used to create the ClickUp task.

    Returns:
        ClickUp task creation response.

    Edge cases:
        Existing integration link prevents duplicate task creation.
    """
    try:
        result = await ticket_to_clickup_tool.execute(
            operation="approve",
            ticket_id=ticket_id,
            user_story=request.user_story.model_dump(),
        )
        if not result.success:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=result.message)
        return CreateClickUpTaskWorkflowResponse.model_validate(result.data)
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(error)) from error
