from app.repositories.ai_draft_repository import AiDraftRepository
from app.repositories.workflow_run_repository import WorkflowRunRepository
from app.schemas.ai import AiDraftDocument, DraftReplyWorkflowResponse
from app.services.ai_service import AiService
from app.services.ticket_service import TicketService


async def draft_reply_workflow(
    ticket_id: str,
    ticket_service: TicketService,
    ai_service: AiService,
    ai_draft_repository: AiDraftRepository,
    workflow_run_repository: WorkflowRunRepository,
) -> DraftReplyWorkflowResponse:
    """Run the reply draft workflow.

    Parameters:
        ticket_id: Fresh ticket identifier.
        ticket_service: Service used to retrieve ticket data.
        ai_service: Service used to generate reply draft.
        ai_draft_repository: Repository used to persist AI draft.
        workflow_run_repository: Repository used to audit workflow execution.

    Returns:
        Draft reply workflow response.

    Edge cases:
        Draft is saved but never sent to Fresh automatically.
    """
    run_id = await workflow_run_repository.start("draft_reply", ticket_id, {"ticket_id": ticket_id})
    try:
        ticket_response = await ticket_service.get_ticket(ticket_id)
        reply = await ai_service.draft_reply(ticket_response.ticket)
        draft = AiDraftDocument(
            fresh_ticket_id=ticket_id,
            type="reply",
            content=reply.body,
            structured_content=reply.model_dump(),
            model=ai_service.model_name,
            prompt_version="draft_reply_v1",
        )
        draft_id = await ai_draft_repository.save_draft(draft)
        response = DraftReplyWorkflowResponse(
            ticket_id=ticket_id,
            type="reply",
            draft=reply,
            draft_id=draft_id,
            workflow_run_id=run_id,
        )
        await workflow_run_repository.finish_success(run_id, response.model_dump())
        return response
    except Exception as error:
        await workflow_run_repository.finish_failure(run_id, str(error))
        raise
