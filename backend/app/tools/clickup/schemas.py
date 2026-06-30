"""Input/output schemas for the ClickUp tool."""

from dataclasses import dataclass

from app.schemas.ai import UserStory
from app.schemas.clickup import ClickUpTaskResult, WeekTimeResponse


@dataclass(frozen=True)
class CreateTaskInput:
    """Input for create_task operation."""

    ticket_id: str
    title: str
    description: str | None = None
    user_story: UserStory | None = None


@dataclass(frozen=True)
class UpdateTaskInput:
    """Input for update_task operation."""

    task_id: str
    changes: dict[str, object]


@dataclass(frozen=True)
class ListTasksInput:
    """Input for list_tasks operation."""

    list_id: str | None = None
    status: str | None = None


@dataclass(frozen=True)
class GetProgressInput:
    """Input for get_progress operation."""

    task_id: str


@dataclass(frozen=True)
class ReadCommentsInput:
    """Input for read_comments operation."""

    task_id: str
