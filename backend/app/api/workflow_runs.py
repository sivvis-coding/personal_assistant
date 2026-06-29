from fastapi import APIRouter, Depends, Query

from app.api.deps import get_workflow_run_repository, require_auth
from app.repositories.workflow_run_repository import WorkflowRunRepository
from app.schemas.workflow import WorkflowRunItem, WorkflowRunListResponse

router = APIRouter(prefix="/workflow-runs", tags=["workflow-runs"], dependencies=[Depends(require_auth)])


@router.get("", response_model=WorkflowRunListResponse)
async def list_workflow_runs(
    limit: int = Query(default=50, ge=1, le=200),
    fresh_ticket_id: str | None = Query(default=None),
    workflow_run_repository: WorkflowRunRepository = Depends(get_workflow_run_repository),
) -> WorkflowRunListResponse:
    """Return workflow run history ordered by newest first.

    Parameters:
        limit: Maximum number of records to return.
        fresh_ticket_id: Optional ticket ID filter.
        workflow_run_repository: Workflow run repository dependency.

    Returns:
        Workflow run history response.

    Edge cases:
        Empty history returns an empty list with the requested limit.
    """
    runs = await workflow_run_repository.list_runs(limit=limit, fresh_ticket_id=fresh_ticket_id)
    return WorkflowRunListResponse(items=[WorkflowRunItem.model_validate(run) for run in runs], limit=limit)
