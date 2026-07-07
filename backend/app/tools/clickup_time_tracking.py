import time as time_module
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import httpx
from typing_extensions import NotRequired, TypedDict

from app.core.config import get_settings

LOCAL_TIMEZONE = ZoneInfo("Europe/Madrid")
CLICKUP_CLIENT_FIELD_NAMES = ("client", "cliente", "customer")

# In-memory cache of the client custom field per list, so a chat session does not
# re-fetch it from ClickUp on every message (including speculative, non-time-tracking
# ones). Short TTL keeps it reasonably fresh if the dropdown options change.
_CLIENT_FIELD_CACHE_TTL_SECONDS = 300
_client_field_cache: dict[str, tuple[float, dict[str, Any] | None]] = {}

# In-memory cache of the authenticated ClickUp user id per API key, used to
# self-assign created tasks. A personal token's owner never changes, so a long
# TTL just guards against a stale cache surviving an API key rotation.
_AUTHENTICATED_USER_CACHE_TTL_SECONDS = 3600
_authenticated_user_cache: dict[str, tuple[float, int | None]] = {}


class TimeEntryData(TypedDict):
    """Represent time tracking data requested by an agent.

    Parameters:
        task_name: ClickUp task name to create.
        description: Task and time entry description.
        start_datetime: Local Europe/Madrid start datetime string.
        end_datetime: Local Europe/Madrid end datetime string.
        client_name: Client name previously resolved from available clients.

    Returns:
        Typed dictionary contract for the LangChain tool.

    Edge cases:
        Datetime strings accept multiple common ISO-like formats.
    """

    task_name: str
    description: str
    start_datetime: str
    end_datetime: str
    client_name: str
    approved: NotRequired[bool]


class TimeEntryPreview(TypedDict):
    """Represent a safe preview for a future time entry.

    Parameters:
        task_name: ClickUp task name to create after approval.
        description: Task and time entry description.
        start_datetime: Local Europe/Madrid start datetime string.
        end_datetime: Local Europe/Madrid end datetime string.
        client_name: Client name selected by the user.
        duration_minutes: Calculated duration in minutes.

    Returns:
        Typed dictionary contract for review payloads.

    Edge cases:
        This preview never creates ClickUp tasks or time entries.
    """

    task_name: str
    description: str
    start_datetime: str
    end_datetime: str
    client_name: str
    duration_minutes: int


def parse_datetime_to_utc_ms(datetime_text: str) -> int:
    """Parse a local datetime string into UTC Unix milliseconds.

    Parameters:
        datetime_text: Datetime text in one supported local format.

    Returns:
        Unix timestamp in milliseconds.

    Edge cases:
        Raises ValueError when the input does not match supported formats.
    """
    for datetime_format in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            naive_datetime = datetime.strptime(datetime_text, datetime_format)
            local_datetime = naive_datetime.replace(tzinfo=LOCAL_TIMEZONE)
            return int(local_datetime.timestamp() * 1000)
        except ValueError:
            continue
    raise ValueError(f"Cannot parse datetime: {datetime_text}")


def calculate_duration_minutes(start_ms: int, end_ms: int) -> int:
    """Calculate duration in minutes between two Unix millisecond values.

    Parameters:
        start_ms: Start timestamp in milliseconds.
        end_ms: End timestamp in milliseconds.

    Returns:
        Duration in whole minutes.

    Edge cases:
        Raises ValueError when end is not after start.
    """
    if end_ms <= start_ms:
        raise ValueError("end_datetime must be after start_datetime")
    return (end_ms - start_ms) // 60_000


def build_time_entry_preview(time_entry: TimeEntryData) -> TimeEntryPreview:
    """Build a safe time entry preview without calling ClickUp.

    Parameters:
        time_entry: Requested time entry data.

    Returns:
        Preview payload with calculated duration.

    Edge cases:
        Raises ValueError when datetime parsing or duration validation fails.
    """
    start_ms = parse_datetime_to_utc_ms(time_entry["start_datetime"])
    end_ms = parse_datetime_to_utc_ms(time_entry["end_datetime"])
    duration_minutes = calculate_duration_minutes(start_ms, end_ms)
    return {
        "task_name": time_entry["task_name"],
        "description": time_entry.get("description", ""),
        "start_datetime": time_entry["start_datetime"],
        "end_datetime": time_entry["end_datetime"],
        "client_name": time_entry.get("client_name", ""),
        "duration_minutes": duration_minutes,
    }


def _clickup_headers() -> dict[str, str]:
    """Build ClickUp HTTP headers from configured settings.

    Parameters:
        None.

    Returns:
        Headers required by ClickUp API.

    Edge cases:
        Empty API key is returned as-is; caller validates credentials first.
    """
    settings = get_settings()
    return {
        "accept": "application/json",
        "content-type": "application/json",
        "Authorization": settings.clickup_api_key,
    }


def _get_authenticated_user_id() -> int | None:
    """Return the ClickUp user id that owns the configured API key.

    Used to self-assign tasks created for daily hour imputation, since a
    personal access token always belongs to exactly one user.

    Parameters:
        None.

    Returns:
        The authenticated user's ClickUp id, or None if credentials are
        missing or the lookup fails.

    Edge cases:
        Cached per API key for an hour; failures are not cached so a
        transient error does not block assignment for the rest of the hour.
    """
    settings = get_settings()
    api_key = settings.clickup_api_key
    if not api_key:
        return None

    cached = _authenticated_user_cache.get(api_key)
    if cached is not None and time_module.monotonic() - cached[0] < _AUTHENTICATED_USER_CACHE_TTL_SECONDS:
        return cached[1]

    try:
        response = httpx.get("https://api.clickup.com/api/v2/user", headers=_clickup_headers(), timeout=20)
        response.raise_for_status()
        user_id = response.json().get("user", {}).get("id")
    except httpx.HTTPError:
        return None

    _authenticated_user_cache[api_key] = (time_module.monotonic(), user_id)
    return user_id


def _find_client_field(list_id: str) -> dict[str, Any] | None:
    """Find the ClickUp custom field that represents client/customer.

    Parameters:
        list_id: ClickUp list identifier.

    Returns:
        Custom field payload or None.

    Edge cases:
        Field matching is based on normalized field names because IDs are list-specific.
        Cached per list_id for a few minutes to avoid refetching on every chat message.
    """
    cached = _client_field_cache.get(list_id)
    if cached is not None and time_module.monotonic() - cached[0] < _CLIENT_FIELD_CACHE_TTL_SECONDS:
        return cached[1]

    response = httpx.get(f"https://api.clickup.com/api/v2/list/{list_id}/field", headers=_clickup_headers(), timeout=20)
    response.raise_for_status()
    fields = response.json().get("fields", [])
    field = next(
        (f for f in fields if str(f.get("name", "")).strip().lower() in CLICKUP_CLIENT_FIELD_NAMES),
        None,
    )
    _client_field_cache[list_id] = (time_module.monotonic(), field)
    return field


def _resolve_client_custom_fields(list_id: str, client_name: str) -> list[dict[str, Any]] | None:
    """Resolve client name into ClickUp custom field payload.

    Parameters:
        list_id: ClickUp list identifier.
        client_name: Client display name.

    Returns:
        ClickUp custom_fields payload or None.

    Edge cases:
        Dropdown and label fields require exact name match ignoring case and surrounding whitespace.
    """
    if not client_name:
        return None
    field = _find_client_field(list_id)
    if not field:
        return None

    field_id = field["id"]
    field_type = field.get("type", "")
    if field_type in ("drop_down", "labels"):
        options = field.get("type_config", {}).get("options", [])
        for option in options:
            if option["name"].strip().lower() == client_name.strip().lower():
                return [{"id": field_id, "value": option["orderindex"]}]
        return None
    return [{"id": field_id, "value": client_name}]


def _get_closed_status(list_id: str) -> str | None:
    """Return a closed/done status for a ClickUp list.

    Parameters:
        list_id: ClickUp list identifier.

    Returns:
        Closed status name or None.

    Edge cases:
        Falls back to None when the list does not expose a closed status.
    """
    response = httpx.get(f"https://api.clickup.com/api/v2/list/{list_id}", headers=_clickup_headers(), timeout=20)
    response.raise_for_status()
    statuses = response.json().get("statuses", [])
    for status in statuses:
        if status.get("type") == "closed":
            return status.get("status")
    for status in statuses:
        if str(status.get("status", "")).lower() in ("done", "closed", "complete", "completed"):
            return status.get("status")
    return None


def _create_clickup_task(
    list_id: str,
    name: str,
    description: str,
    custom_fields: list[dict[str, Any]] | None,
    status: str | None,
    start_date_ms: int,
    due_date_ms: int,
    assignee_id: int | None = None,
) -> dict[str, Any]:
    """Create a ClickUp task used as the time tracking container.

    Parameters:
        list_id: ClickUp list identifier.
        name: Task name.
        description: Task description.
        custom_fields: Optional ClickUp custom fields.
        status: Optional closed status name.
        start_date_ms: Task start timestamp in milliseconds.
        due_date_ms: Task due timestamp in milliseconds.
        assignee_id: Optional ClickUp user id to self-assign the task to.

    Returns:
        ClickUp task response payload.

    Edge cases:
        Status is omitted when no closed status can be resolved.
        Assignee is omitted when the authenticated user could not be resolved.
    """
    payload: dict[str, Any] = {
        "name": name,
        "description": description,
        "start_date": start_date_ms,
        "due_date": due_date_ms,
    }
    if custom_fields:
        payload["custom_fields"] = custom_fields
    if status:
        payload["status"] = status
    if assignee_id is not None:
        payload["assignees"] = [assignee_id]

    response = httpx.post(f"https://api.clickup.com/api/v2/list/{list_id}/task", headers=_clickup_headers(), json=payload, timeout=20)
    response.raise_for_status()
    return response.json()


def _create_clickup_time_entry(team_id: str, task_id: str, start_ms: int, end_ms: int, description: str) -> dict[str, Any]:
    """Create a ClickUp time entry for an existing task.

    Parameters:
        team_id: ClickUp workspace/team identifier.
        task_id: ClickUp task identifier.
        start_ms: Start timestamp in milliseconds.
        end_ms: End timestamp in milliseconds.
        description: Time entry description.

    Returns:
        ClickUp time entry response payload.

    Edge cases:
        Duration is sent in milliseconds as expected by ClickUp.
    """
    payload = {
        "tid": task_id,
        "start": start_ms,
        "duration": end_ms - start_ms,
        "description": description,
    }
    response = httpx.post(f"https://api.clickup.com/api/v2/team/{team_id}/time_entries", headers=_clickup_headers(), json=payload, timeout=20)
    response.raise_for_status()
    return response.json()


def get_clickup_client_names(list_id: str) -> list[str]:
    """Return available ClickUp client names for the given list.

    Parameters:
        list_id: ClickUp list identifier to read the client field from.

    Returns:
        List of client names. Empty list when credentials are missing, the field
        is not found, or the field allows free text.

    Edge cases:
        Missing credentials or list_id return an empty list so callers can fall back gracefully.
    """
    settings = get_settings()
    if not settings.clickup_api_key or not list_id:
        return []

    try:
        field = _find_client_field(list_id)
    except httpx.HTTPError:
        return []

    if not field:
        return []

    field_type = field.get("type", "")
    if field_type in ("drop_down", "labels"):
        options = field.get("type_config", {}).get("options", [])
        return [option["name"] for option in options]
    return []


def save_time_entry(time_entry: TimeEntryData, list_id: str) -> str:
    """Create a ClickUp task and register a time entry.

    Parameters:
        time_entry: Time entry payload validated by the agent/tool caller.
        list_id: ClickUp list identifier to create the task in (e.g. the user's
            personal list configured for daily hour imputation).

    Returns:
        Human-readable success or error message.

    Edge cases:
        Requires approved=true to avoid accidental agent-created time entries.
        If task creation succeeds but time entry creation fails, the task ID is returned for manual repair.
    """
    if not time_entry.get("approved", False):
        return "ERROR: Explicit approval is required. Ask the user to confirm, then call save_time_entry with approved=true."

    settings = get_settings()
    if not settings.clickup_api_key or not settings.clickup_team_id or not list_id:
        return "ERROR: ClickUp API key, team ID, or list ID is not configured."

    try:
        start_ms = parse_datetime_to_utc_ms(time_entry["start_datetime"])
        end_ms = parse_datetime_to_utc_ms(time_entry["end_datetime"])
        duration_minutes = calculate_duration_minutes(start_ms, end_ms)
    except ValueError as error:
        return f"ERROR: {error}"

    client_name = time_entry.get("client_name", "")
    try:
        custom_fields = _resolve_client_custom_fields(list_id, client_name)
    except httpx.HTTPError as error:
        return f"ERROR: Could not resolve ClickUp client field: {error}"

    if client_name and not custom_fields:
        return f"ERROR: Could not resolve client '{client_name}'."

    try:
        closed_status = _get_closed_status(list_id)
        assignee_id = _get_authenticated_user_id()
        task = _create_clickup_task(
            list_id=list_id,
            name=time_entry["task_name"],
            description=time_entry.get("description", ""),
            custom_fields=custom_fields,
            status=closed_status,
            start_date_ms=start_ms,
            due_date_ms=end_ms,
            assignee_id=assignee_id,
        )
    except httpx.HTTPError as error:
        return f"ERROR creating ClickUp task: {error}"

    task_id = str(task["id"])
    task_url = task.get("url", "")

    try:
        _create_clickup_time_entry(
            team_id=settings.clickup_team_id,
            task_id=task_id,
            start_ms=start_ms,
            end_ms=end_ms,
            description=time_entry.get("description", ""),
        )
    except httpx.HTTPError as error:
        return f"Task created (ID: {task_id}) but ERROR registering time entry: {error}"

    hours, minutes = divmod(duration_minutes, 60)
    client_line = f"- Cliente: {client_name}\n" if client_name else ""
    return (
        "✅ Tarea creada e imputación registrada correctamente.\n"
        f"- Tarea: {time_entry['task_name']} (ID: {task_id})\n"
        f"- Duración: {hours}h {minutes}m\n"
        f"{client_line}"
        f"- URL: {task_url}"
    )
