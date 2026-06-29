from app.repositories.ai_draft_repository import AiDraftRepository
from app.repositories.workflow_run_repository import WorkflowRunRepository
from app.schemas.ai import AiDraftDocument, SummaryWorkflowResponse
from app.services.ai_service import AiService
from app.services.ticket_service import TicketService


async def summarize_ticket_workflow(
    ticket_id: str,
    ticket_service: TicketService,
    ai_service: AiService,
    ai_draft_repository: AiDraftRepository,
    workflow_run_repository: WorkflowRunRepository,
) -> SummaryWorkflowResponse:
    """Run the ticket summary workflow.

    Parameters:
        ticket_id: Fresh ticket identifier.
        ticket_service: Service used to retrieve ticket data.
        ai_service: Service used to generate summary.
        ai_draft_repository: Repository used to persist AI draft.
        workflow_run_repository: Repository used to audit workflow execution.

    Returns:
        Summary workflow response.

    Edge cases:
        Any failure is recorded in workflow_runs before being re-raised.
    """
    run_id = await workflow_run_repository.start("ticket_summary", ticket_id, {"ticket_id": ticket_id})
    try:
        ticket_response = await ticket_service.get_ticket(ticket_id)
        summary = await ai_service.summarize_ticket(ticket_response.ticket)
        draft = AiDraftDocument(
            fresh_ticket_id=ticket_id,
            type="summary",
            content=summary.model_dump_json(),
            structured_content=summary.model_dump(),
            model=ai_service.model_name,
            prompt_version="ticket_summary_v1",
        )
        draft_id = await ai_draft_repository.save_draft(draft)
        response = SummaryWorkflowResponse(
            ticket_id=ticket_id,
            type="summary",
            summary=summary,
            draft_id=draft_id,
            workflow_run_id=run_id,
        )
        await workflow_run_repository.finish_success(run_id, response.model_dump())
        return response
    except Exception as error:
        await workflow_run_repository.finish_failure(run_id, str(error))
        raise
