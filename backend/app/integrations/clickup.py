from datetime import date, datetime, timedelta, timezone

import httpx

from app.core.config import Settings
from app.core.errors import ExternalServiceError
from app.integrations.clickup_contract import (
    CLICKUP_CUSTOM_FIELD_ACCEPTANCE_CRITERIA_ID,
    CLICKUP_CUSTOM_FIELD_CONSTRAINTS_ID,
    CLICKUP_CUSTOM_FIELD_FUNCTIONAL_DESCRIPTION_ID,
    CLICKUP_CUSTOM_FIELD_OUT_OF_SCOPE_ID,
    CLICKUP_CUSTOM_FIELD_REQUESTED_BY_ID,
    CLICKUP_CUSTOM_FIELD_USER_STORY_STATEMENT_ID,
    CLICKUP_USER_STORY_CUSTOM_ITEM_ID,
)
from app.schemas.ai import UserStory
from app.schemas.clickup import ClickUpTask, ClickUpTaskResult, TimeEntry, WeekTimeResponse
from app.schemas.ticket import Ticket


class ClickUpClient:
    """Client for ClickUp task and time operations.

    Parameters:
        settings: Application settings with ClickUp credentials.

    Returns:
        ClickUp integration client.

    Edge cases:
        Missing credentials switch operations to mock mode.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def create_task_from_ticket(
        self, ticket: Ticket, user_story: UserStory, list_id: str | None = None
    ) -> ClickUpTaskResult:
        """Create a ClickUp task from a ticket and user story.

        Parameters:
            ticket: Source ticket.
            user_story: Generated user story.
            list_id: Target list ID override. Falls back to settings clickup_list_id.

        Returns:
            ClickUp task result.

        Edge cases:
            Missing credentials return a mock task instead of calling ClickUp.
            list_id override takes precedence over the settings default.
        """
        effective_list_id = list_id or self._settings.clickup_list_id
        if not (self._settings.clickup_api_key.strip() and effective_list_id.strip()):
            return ClickUpTaskResult(id=f"mock-clickup-{ticket.id}", url="http://localhost/mock-clickup-task", source="mock")
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                response = await client.post(
                    f"https://api.clickup.com/api/v2/list/{effective_list_id}/task",
                    headers={
                        "accept": "application/json",
                        "content-type": "application/json",
                        "Authorization": self._settings.clickup_api_key,
                    },
                    json=self._build_user_story_task_payload(user_story),
                )
                response.raise_for_status()
                payload = response.json()
                return ClickUpTaskResult(id=str(payload.get("id")), url=payload.get("url"), source="clickup")
        except httpx.HTTPError as error:
            raise ExternalServiceError(f"ClickUp create task failed: {error}") from error

    def _build_user_story_task_payload(self, user_story: UserStory) -> dict:
        """Build the ClickUp task payload for a user story.

        Parameters:
            user_story: Reviewed user story to save in ClickUp.

        Returns:
            ClickUp API payload matching the configured custom fields.

        Edge cases:
            Custom field IDs are internal constants because they are workspace-specific.
        """
        return {
            "name": user_story.title,
            "description": user_story.description,
            "custom_item_id": CLICKUP_USER_STORY_CUSTOM_ITEM_ID,
            "custom_fields": [
                {"id": CLICKUP_CUSTOM_FIELD_CONSTRAINTS_ID, "value": user_story.constraints},
                {"id": CLICKUP_CUSTOM_FIELD_USER_STORY_STATEMENT_ID, "value": user_story.user_story_statement},
                {"id": CLICKUP_CUSTOM_FIELD_OUT_OF_SCOPE_ID, "value": user_story.out_of_scope},
                {"id": CLICKUP_CUSTOM_FIELD_ACCEPTANCE_CRITERIA_ID, "value": user_story.acceptance_criteria_in_gerkin},
                {"id": CLICKUP_CUSTOM_FIELD_REQUESTED_BY_ID, "value": user_story.requested_by},
                {"id": CLICKUP_CUSTOM_FIELD_FUNCTIONAL_DESCRIPTION_ID, "value": user_story.functional_description},
            ],
        }

    async def list_tasks(self) -> list[ClickUpTask]:
        """Return tasks from the configured ClickUp list.

        Parameters:
            None.

        Returns:
            List of ClickUp tasks.

        Edge cases:
            Missing credentials return mock tasks.
        """
        if not self._settings.has_clickup_credentials:
            return [
                ClickUpTask(id="mock-1", name="Mock pending task", status="open"),
                ClickUpTask(id="mock-2", name="Mock in-progress task", status="in progress"),
                ClickUpTask(id="mock-3", name="Mock blocked task", status="blocked"),
            ]
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                response = await client.get(
                    f"https://api.clickup.com/api/v2/list/{self._settings.clickup_list_id}/task",
                    headers={"Authorization": self._settings.clickup_api_key},
                )
                response.raise_for_status()
                return [
                    ClickUpTask(
                        id=str(task.get("id")),
                        name=str(task.get("name") or "Untitled"),
                        status=str(task.get("status", {}).get("status") or "unknown").lower(),
                        url=task.get("url"),
                    )
                    for task in response.json().get("tasks", [])
                ]
        except httpx.HTTPError as error:
            raise ExternalServiceError(f"ClickUp list tasks failed: {error}") from error

    async def get_week_time_entries(self) -> WeekTimeResponse:
        """Return time entries for the current week.

        Parameters:
            None.

        Returns:
            Weekly time response.

        Edge cases:
            ClickUp API differences are isolated here; missing credentials use mock data.
        """
        today = datetime.now(timezone.utc).date()
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)
        if not self._settings.has_clickup_credentials:
            entries = [TimeEntry(task_id="mock-task", task_name="Mock support work", hours=2.5, date=today)]
            return WeekTimeResponse(source="mock", week_start=week_start, week_end=week_end, total_hours=2.5, entries=entries)
        start_ms = int(datetime.combine(week_start, datetime.min.time(), tzinfo=timezone.utc).timestamp() * 1000)
        end_ms = int(datetime.combine(week_end, datetime.max.time(), tzinfo=timezone.utc).timestamp() * 1000)
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                response = await client.get(
                    f"https://api.clickup.com/api/v2/team/{self._settings.clickup_team_id}/time_entries",
                    headers={"Authorization": self._settings.clickup_api_key},
                    params={"start_date": start_ms, "end_date": end_ms},
                )
                response.raise_for_status()
                entries = self._normalize_time_entries(response.json().get("data", []))
                return WeekTimeResponse(
                    source="clickup",
                    week_start=week_start,
                    week_end=week_end,
                    total_hours=sum(entry.hours for entry in entries),
                    entries=entries,
                )
        except httpx.HTTPError as error:
            raise ExternalServiceError(f"ClickUp time entries failed: {error}") from error

    def _normalize_time_entries(self, payloads: list[dict]) -> list[TimeEntry]:
        """Normalize ClickUp time entries into internal schema.

        Parameters:
            payloads: Raw ClickUp time entry payloads.

        Returns:
            Normalized time entries.

        Edge cases:
            Malformed dates fall back to today's date.
        """
        entries: list[TimeEntry] = []
        for payload in payloads:
            task = payload.get("task") or {}
            entry_date = date.today()
            if payload.get("start"):
                entry_date = datetime.fromtimestamp(int(payload["start"]) / 1000, tz=timezone.utc).date()
            entries.append(
                TimeEntry(
                    task_id=str(task.get("id") or "unknown"),
                    task_name=str(task.get("name") or "Unknown task"),
                    hours=float(payload.get("duration") or 0) / 3_600_000,
                    date=entry_date,
                )
            )
        return entries
