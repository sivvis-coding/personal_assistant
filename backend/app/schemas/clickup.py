from datetime import date

from pydantic import BaseModel

from app.schemas.ai import UserStory


class ClickUpTaskResult(BaseModel):
    """Represent ClickUp task creation result.

    Parameters:
        id: ClickUp task ID.
        url: ClickUp task URL.
        source: clickup or mock.

    Returns:
        Task creation result.

    Edge cases:
        Mock task IDs are prefixed to avoid confusion.
    """

    id: str
    url: str | None = None
    source: str


class CreateClickUpTaskWorkflowResponse(BaseModel):
    """Represent create ClickUp task workflow response.

    Parameters:
        ticket_id: Fresh ticket ID.
        user_story: Generated user story.
        clickup_task: Task creation result.
        integration_link_id: Stored integration link ID.
        workflow_run_id: Workflow run ID.

    Returns:
        ClickUp workflow response for frontend.

    Edge cases:
        Existing integration link may be returned instead of creating duplicate task.
    """

    ticket_id: str
    user_story: UserStory
    clickup_task: ClickUpTaskResult
    integration_link_id: str
    workflow_run_id: str


class PrepareClickUpTaskWorkflowResponse(BaseModel):
    """Represent ClickUp task review preparation response.

    Parameters:
        ticket_id: Fresh ticket ID.
        user_story: Generated user story ready for review.
        draft_id: Stored AI draft ID.
        workflow_run_id: Workflow run ID.
        requires_approval: Whether explicit approval is required before task creation.

    Returns:
        Review payload for the frontend.

    Edge cases:
        This response never means a ClickUp task was created.
    """

    ticket_id: str
    user_story: UserStory
    draft_id: str
    workflow_run_id: str
    requires_approval: bool = True


class ApproveClickUpTaskRequest(BaseModel):
    """Represent explicit approval request for ClickUp task creation.

    Parameters:
        user_story: Reviewed and optionally edited user story.

    Returns:
        Validated approval request.

    Edge cases:
        Approval is explicit because creating a ClickUp task affects external state.
    """

    user_story: UserStory


class TimeEntry(BaseModel):
    """Represent a ClickUp time entry.

    Parameters:
        task_id: Related ClickUp task ID.
        task_name: Related task name.
        hours: Reported hours.
        date: Entry date.

    Returns:
        Time entry value object.

    Edge cases:
        Entries without task are labeled as unknown.
    """

    task_id: str
    task_name: str
    hours: float
    date: date


class WeekTimeResponse(BaseModel):
    """Represent weekly ClickUp time response.

    Parameters:
        source: clickup or mock.
        week_start: First day of week.
        week_end: Last day of week.
        total_hours: Sum of entry hours.
        entries: Time entries.

    Returns:
        Weekly time report.

    Edge cases:
        Empty entries return total_hours as zero.
    """

    source: str
    week_start: date
    week_end: date
    total_hours: float
    entries: list[TimeEntry]
