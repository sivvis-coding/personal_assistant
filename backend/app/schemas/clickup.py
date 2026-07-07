from datetime import date

from pydantic import BaseModel, Field

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


class ClickUpTask(BaseModel):
    """Represent a ClickUp task for listing.

    Parameters:
        id: ClickUp task ID.
        name: Task name.
        status: Task status name.
        url: Task URL.

    Returns:
        ClickUp task value object.

    Edge cases:
        Missing status is reported as 'unknown'.
    """

    id: str
    name: str
    status: str = "unknown"
    url: str | None = None


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


class DayTimeSummary(BaseModel):
    """Represent one calendar day's logged time.

    Parameters:
        date: The calendar day.
        total_hours: Sum of entry hours logged that day.
        entries: Individual time entries logged that day.

    Returns:
        Day time summary value object.

    Edge cases:
        Days with no logged time have total_hours=0 and an empty entries list.
    """

    date: date
    total_hours: float
    entries: list[TimeEntry] = Field(default_factory=list)


class MonthTimeResponse(BaseModel):
    """Represent a full month's ClickUp time, one summary per calendar day.

    Parameters:
        source: clickup or mock.
        year: Calendar year.
        month: Calendar month (1-12).
        total_hours: Sum of all entry hours in the month.
        days: One DayTimeSummary per day in the month, in order, including
            days with no logged time.

    Returns:
        Monthly time report suitable for a calendar view.

    Edge cases:
        Future days within the month are included with total_hours=0, same as
        past days with no entries — the frontend decides how to distinguish them.
    """

    source: str
    year: int
    month: int
    total_hours: float
    days: list[DayTimeSummary]


class PersonalListClientsResponse(BaseModel):
    """Represent the valid client options for the personal ClickUp list.

    Parameters:
        clients: Exact client values configured on the "Cliente" dropdown/label
            field, so the frontend can offer a selector instead of free text.

    Returns:
        Client options response.

    Edge cases:
        Empty when no personal list is configured, the field is missing, or
        the field allows free text instead of fixed options.
    """

    clients: list[str] = Field(default_factory=list)
