import calendar
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
from app.schemas.clickup import ClickUpTask, ClickUpTaskResult, DayTimeSummary, MonthTimeResponse, TimeEntry, WeekTimeResponse
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

    async def create_task(self, user_story: UserStory, list_id: str | None = None) -> ClickUpTaskResult:
        """Create a standalone ClickUp task from a user story, with no source ticket.

        Parameters:
            user_story: Generated user story.
            list_id: Target list ID override. Falls back to settings clickup_list_id.

        Returns:
            ClickUp task result.

        Edge cases:
            Missing credentials return a mock task instead of calling ClickUp.
        """
        effective_list_id = list_id or self._settings.clickup_list_id
        if not (self._settings.clickup_api_key.strip() and effective_list_id.strip()):
            return ClickUpTaskResult(id="mock-clickup-standalone", url="http://localhost/mock-clickup-task", source="mock")
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

    async def get_task(self, task_id: str) -> ClickUpTask | None:
        """Return a single ClickUp task by ID.

        Parameters:
            task_id: ClickUp task identifier.

        Returns:
            ClickUp task or None when credentials are missing or the task is not found.

        Edge cases:
            Returns None instead of raising when the task cannot be fetched.
        """
        if not self._settings.clickup_api_key.strip():
            return None
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(
                    f"https://api.clickup.com/api/v2/task/{task_id}",
                    headers={"Authorization": self._settings.clickup_api_key},
                )
                response.raise_for_status()
                payload = response.json()
                return ClickUpTask(
                    id=str(payload.get("id")),
                    name=str(payload.get("name") or "Untitled"),
                    status=str(payload.get("status", {}).get("status") or "unknown").lower(),
                    url=payload.get("url"),
                )
        except httpx.HTTPError:
            return None

    async def list_tasks(self) -> list[ClickUpTask]:
        """Return all tasks from the single configured ClickUp list (legacy).

        Parameters:
            None.

        Returns:
            List of ClickUp tasks from ``settings.clickup_list_id``.

        Edge cases:
            Kept for the status-sync service; the roadmap uses list_tasks_for
            per configured list instead.
        """
        return await self.list_tasks_for(self._settings.clickup_list_id)

    async def list_tasks_for(self, list_id: str, list_name: str | None = None) -> list[ClickUpTask]:
        """Return all tasks from a specific ClickUp list, tagged with the list.

        Parameters:
            list_id: ClickUp list ID to fetch.
            list_name: Optional display name to tag each task with.

        Returns:
            List of ClickUp tasks across every page of the given list.

        Edge cases:
            Missing credentials return mock tasks tagged with the given list.
            The list endpoint paginates at 100 tasks per page, so every page is
            fetched until ClickUp reports the last one.
        """
        if not self._settings.has_clickup_credentials:
            suffix = list_id or "default"
            return [
                ClickUpTask(id=f"{suffix}-1", name="Mock pending task", status="pending", list_id=list_id, list_name=list_name),
                ClickUpTask(id=f"{suffix}-2", name="Mock ready-to-define task", status="ready to define", list_id=list_id, list_name=list_name),
                ClickUpTask(id=f"{suffix}-3", name="Mock in-progress task", status="in progress", list_id=list_id, list_name=list_name),
                ClickUpTask(id=f"{suffix}-4", name="Mock done task", status="done", list_id=list_id, list_name=list_name),
            ]
        tasks: list[ClickUpTask] = []
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                page = 0
                while True:
                    response = await client.get(
                        f"https://api.clickup.com/api/v2/list/{list_id}/task",
                        headers={"Authorization": self._settings.clickup_api_key},
                        params={"page": page},
                    )
                    response.raise_for_status()
                    payload = response.json()
                    page_tasks = payload.get("tasks", [])
                    tasks.extend(
                        ClickUpTask(
                            id=str(task.get("id")),
                            name=str(task.get("name") or "Untitled"),
                            status=str(task.get("status", {}).get("status") or "unknown").lower(),
                            url=task.get("url"),
                            description=(task.get("text_content") or task.get("description") or None),
                            list_id=list_id,
                            list_name=list_name,
                        )
                        for task in page_tasks
                    )
                    if payload.get("last_page", True) or not page_tasks:
                        break
                    page += 1
            return tasks
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

        entries = await self._fetch_time_entries(week_start, week_end)
        return WeekTimeResponse(
            source="clickup",
            week_start=week_start,
            week_end=week_end,
            total_hours=sum(entry.hours for entry in entries),
            entries=entries,
        )

    async def get_month_time_entries(self, year: int, month: int) -> MonthTimeResponse:
        """Return time entries for a calendar month, one summary per day.

        Parameters:
            year: Calendar year.
            month: Calendar month (1-12).

        Returns:
            Monthly time response with every day of the month represented,
            including days with no logged time.

        Edge cases:
            Missing credentials return a small mock so the calendar still renders locally.
        """
        days_in_month = calendar.monthrange(year, month)[1]
        month_start = date(year, month, 1)
        month_end = date(year, month, days_in_month)

        if not self._settings.has_clickup_credentials:
            mock_entry = TimeEntry(task_id="mock-task", task_name="Mock support work", hours=2.5, date=month_start)
            days = [
                DayTimeSummary(
                    date=month_start,
                    total_hours=mock_entry.hours,
                    entries=[mock_entry],
                )
            ] + [
                DayTimeSummary(date=month_start + timedelta(days=offset), total_hours=0, entries=[])
                for offset in range(1, days_in_month)
            ]
            return MonthTimeResponse(source="mock", year=year, month=month, total_hours=mock_entry.hours, days=days)

        entries = await self._fetch_time_entries(month_start, month_end)
        entries_by_day: dict[date, list[TimeEntry]] = {}
        for entry in entries:
            entries_by_day.setdefault(entry.date, []).append(entry)

        days = [
            DayTimeSummary(
                date=month_start + timedelta(days=offset),
                total_hours=sum(e.hours for e in entries_by_day.get(month_start + timedelta(days=offset), [])),
                entries=entries_by_day.get(month_start + timedelta(days=offset), []),
            )
            for offset in range(days_in_month)
        ]
        return MonthTimeResponse(
            source="clickup",
            year=year,
            month=month,
            total_hours=sum(entry.hours for entry in entries),
            days=days,
        )

    async def _fetch_time_entries(self, start: date, end: date) -> list[TimeEntry]:
        """Fetch and normalize ClickUp time entries within an inclusive date range.

        Parameters:
            start: First day to include.
            end: Last day to include.

        Returns:
            Normalized time entries within the range.

        Edge cases:
            Assumes ClickUp credentials are already confirmed present by the caller.
        """
        start_ms = int(datetime.combine(start, datetime.min.time(), tzinfo=timezone.utc).timestamp() * 1000)
        end_ms = int(datetime.combine(end, datetime.max.time(), tzinfo=timezone.utc).timestamp() * 1000)
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                response = await client.get(
                    f"https://api.clickup.com/api/v2/team/{self._settings.clickup_team_id}/time_entries",
                    headers={"Authorization": self._settings.clickup_api_key},
                    params={"start_date": start_ms, "end_date": end_ms},
                )
                response.raise_for_status()
                return self._normalize_time_entries(response.json().get("data", []))
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
