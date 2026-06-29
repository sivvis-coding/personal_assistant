from app.integrations.clickup import ClickUpClient
from app.repositories.ai_draft_repository import AiDraftRepository
from app.repositories.integration_link_repository import IntegrationLinkRepository
from app.repositories.workflow_run_repository import WorkflowRunRepository
from app.schemas.ai import AiDraftDocument
from app.schemas.ai import UserStory
from app.schemas.clickup import ClickUpTaskResult, CreateClickUpTaskWorkflowResponse, PrepareClickUpTaskWorkflowResponse
from app.schemas.integration import IntegrationLinkDocument
from app.services.ai_service import AiService
from app.services.ticket_service import TicketService


async def prepare_clickup_task_from_ticket_workflow(
    ticket_id: str,
    ticket_service: TicketService,
    ai_service: AiService,
    ai_draft_repository: AiDraftRepository,
    workflow_run_repository: WorkflowRunRepository,
) -> PrepareClickUpTaskWorkflowResponse:
    """Prepare a ClickUp task proposal without creating a real task.

    Parameters:
        ticket_id: Fresh ticket identifier.
        ticket_service: Service used to retrieve ticket data.
        ai_service: Service used to generate user story.
        ai_draft_repository: Repository used to persist generated user story.
        workflow_run_repository: Repository used to audit workflow execution.

    Returns:
        ClickUp task preparation response.

    Edge cases:
        This workflow never calls ClickUp, even when credentials are configured.
    """
    run_id = await workflow_run_repository.start("prepare_clickup_task", ticket_id, {"ticket_id": ticket_id})
    try:
        ticket_response = await ticket_service.get_ticket(ticket_id)
        user_story = await ai_service.ticket_to_user_story(ticket_response.ticket)
        draft_id = await ai_draft_repository.save_draft(
            AiDraftDocument(
                fresh_ticket_id=ticket_id,
                type="user_story",
                content=user_story.to_markdown(),
                structured_content=user_story.model_dump(),
                model=ai_service.model_name,
                prompt_version="ticket_user_story_v1",
            )
        )

        response = PrepareClickUpTaskWorkflowResponse(
            ticket_id=ticket_id,
            user_story=user_story,
            draft_id=draft_id,
            workflow_run_id=run_id,
            requires_approval=True,
        )
        await workflow_run_repository.finish_success(run_id, response.model_dump())
        return response
    except Exception as error:
        await workflow_run_repository.finish_failure(run_id, str(error))
        raise


async def approve_clickup_task_from_ticket_workflow(
    ticket_id: str,
    approved_user_story: UserStory,
    ticket_service: TicketService,
    clickup_client: ClickUpClient,
    integration_link_repository: IntegrationLinkRepository,
    workflow_run_repository: WorkflowRunRepository,
) -> CreateClickUpTaskWorkflowResponse:
    """Create a ClickUp task after explicit user approval.

    Parameters:
        ticket_id: Fresh ticket identifier.
        approved_user_story: Reviewed user story from the frontend.
        ticket_service: Service used to retrieve ticket data.
        clickup_client: Client used to create ClickUp task.
        integration_link_repository: Repository used to persist Fresh-to-ClickUp relation.
        workflow_run_repository: Repository used to audit workflow execution.

    Returns:
        ClickUp task creation response.

    Edge cases:
        Existing integration link prevents duplicate ClickUp task creation.
    """
    run_id = await workflow_run_repository.start(
        "approve_clickup_task",
        ticket_id,
        {"ticket_id": ticket_id, "approved_user_story": approved_user_story.model_dump()},
    )
    try:
        ticket_response = await ticket_service.get_ticket(ticket_id)

        existing_link = await integration_link_repository.find_link("fresh", ticket_id, "created_clickup_task")
        if existing_link:
            clickup_task = ClickUpTaskResult(
                id=str(existing_link["target_id"]),
                url=existing_link.get("target_url"),
                source="cache",
            )
            link_id = str(existing_link["id"])
        else:
            clickup_task = await clickup_client.create_task_from_ticket(ticket_response.ticket, approved_user_story)
            link_id = await integration_link_repository.save_link(
                IntegrationLinkDocument(
                    source_system="fresh",
                    source_id=ticket_id,
                    target_system="clickup",
                    target_id=clickup_task.id,
                    target_url=clickup_task.url,
                    relation_type="created_clickup_task",
                )
            )

        response = CreateClickUpTaskWorkflowResponse(
            ticket_id=ticket_id,
            user_story=approved_user_story,
            clickup_task=clickup_task,
            integration_link_id=link_id,
            workflow_run_id=run_id,
        )
        await workflow_run_repository.finish_success(run_id, response.model_dump())
        return response
    except Exception as error:
        await workflow_run_repository.finish_failure(run_id, str(error))
        raise
