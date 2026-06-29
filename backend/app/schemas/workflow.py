from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel

WorkflowStatus = Literal["running", "success", "failed"]


class WorkflowRunDocument(BaseModel):
    """Represent a workflow execution record.

    Parameters:
        workflow_name: Workflow identifier.
        fresh_ticket_id: Related Fresh ticket ID.
        status: Execution status.
        input: Workflow input payload.
        output: Workflow output payload.
        error: Error details if failed.
        started_at: Start timestamp.
        finished_at: Finish timestamp.

    Returns:
        Mongo-ready workflow run payload.

    Edge cases:
        output and error are optional while workflow is running.
    """

    workflow_name: str
    fresh_ticket_id: str | None = None
    status: WorkflowStatus
    input: dict[str, Any]
    output: dict[str, Any] | None = None
    error: str | None = None
    started_at: datetime
    finished_at: datetime | None = None


class WorkflowRunItem(BaseModel):
    """Represent a workflow run returned by the API.

    Parameters:
        id: Mongo document ID.
        workflow_name: Workflow identifier.
        fresh_ticket_id: Related Fresh ticket ID.
        status: Workflow status.
        input: Workflow input payload.
        output: Workflow output payload.
        error: Error details if failed.
        started_at: Start timestamp.
        finished_at: Finish timestamp.
        created_at: Document creation timestamp.
        updated_at: Document update timestamp.
        source: Document source.

    Returns:
        Workflow run list item.

    Edge cases:
        output, error, and finished_at may be null for running workflows.
    """

    id: str
    workflow_name: str
    fresh_ticket_id: str | None = None
    status: WorkflowStatus
    input: dict[str, Any]
    output: dict[str, Any] | None = None
    error: str | None = None
    started_at: datetime
    finished_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    source: str


class WorkflowRunListResponse(BaseModel):
    """Represent paginated workflow run history.

    Parameters:
        items: Workflow run records.
        limit: Maximum number of returned records.

    Returns:
        Workflow run history response.

    Edge cases:
        Empty history returns an empty list.
    """

    items: list[WorkflowRunItem]
    limit: int
