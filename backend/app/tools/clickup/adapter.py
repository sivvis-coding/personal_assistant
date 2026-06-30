"""Adapter from existing ClickUpClient to the tool boundary."""

from app.integrations.clickup import ClickUpClient
from app.schemas.ai import UserStory
from app.schemas.clickup import ClickUpTaskResult
from app.schemas.ticket import Ticket, TicketRequester
from app.tools.clickup.schemas import (
    CreateTaskInput,
    GetProgressInput,
    ListTasksInput,
    ReadCommentsInput,
    UpdateTaskInput,
)


class ClickUpAdapter:
    """Thin adapter around ClickUpClient.

    Parameters:
        client: Existing ClickUpClient instance.

    Returns:
        Adapter instance.
    """

    def __init__(self, client: ClickUpClient) -> None:
        self._client = client

    async def create_task(self, input_data: CreateTaskInput) -> ClickUpTaskResult:
        """Create a ClickUp task from a ticket."""
        ticket = Ticket(
            id=input_data.ticket_id,
            subject=input_data.title,
            description=input_data.description,
            status="open",
            priority="medium",
            requester=TicketRequester(name="Unknown", email=None),
            raw={},
        )
        user_story = input_data.user_story or UserStory(
            title=input_data.title,
            description=input_data.description or "",
            acceptance_criteria_in_gerkin="",
            constraints="",
            user_story_statement="",
            out_of_scope="",
            requested_by="",
            functional_description="",
        )
        return await self._client.create_task_from_ticket(ticket, user_story)

    async def update_task(self, input_data: UpdateTaskInput) -> dict[str, object]:
        """Update a ClickUp task.

        Phase 1 returns the requested changes as the existing client does not
        implement updates yet.
        """
        return {"task_id": input_data.task_id, "changes": input_data.changes, "source": "mock"}

    async def list_tasks(self, input_data: ListTasksInput) -> dict[str, object]:
        """List ClickUp tasks.

        Phase 1 delegates to the week time entries endpoint as a proxy for
        active work. A dedicated task listing endpoint will be added later.
        """
        week = await self._client.get_week_time_entries()
        return {
            "tasks": [
                {"id": entry.task_id, "name": entry.task_name, "hours": entry.hours, "date": entry.date.isoformat()}
                for entry in week.entries
            ],
            "source": week.source,
        }

    async def get_progress(self, input_data: GetProgressInput) -> dict[str, object]:
        """Get task progress."""
        return {"task_id": input_data.task_id, "progress": "unknown", "source": "mock"}

    async def read_comments(self, input_data: ReadCommentsInput) -> dict[str, object]:
        """Read task comments."""
        return {"task_id": input_data.task_id, "comments": [], "source": "mock"}
