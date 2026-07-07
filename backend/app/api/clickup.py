from datetime import date

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_clickup_service, get_clickup_time_tool, get_settings_service, require_auth
from app.schemas.clickup import MonthTimeResponse, PersonalListClientsResponse, WeekTimeResponse
from app.services.clickup_service import ClickUpService
from app.services.settings_service import SettingsService
from app.tools.clickup_time.tool import ClickUpTimeTool

router = APIRouter(prefix="/clickup", tags=["clickup"], dependencies=[Depends(require_auth)])


@router.get("/week-time", response_model=WeekTimeResponse)
async def get_week_time(clickup_service: ClickUpService = Depends(get_clickup_service)) -> WeekTimeResponse:
    """Return ClickUp hours reported in the current week.

    Parameters:
        clickup_service: ClickUp service dependency.

    Returns:
        Weekly time report.

    Edge cases:
        Missing ClickUp credentials return mock data.
    """
    return await clickup_service.get_week_time_entries()


@router.get("/month-time", response_model=MonthTimeResponse)
async def get_month_time(
    year: int = Query(default_factory=lambda: date.today().year),
    month: int = Query(default_factory=lambda: date.today().month, ge=1, le=12),
    clickup_service: ClickUpService = Depends(get_clickup_service),
) -> MonthTimeResponse:
    """Return ClickUp hours reported for a calendar month, one summary per day.

    Parameters:
        year: Calendar year, defaults to the current year.
        month: Calendar month (1-12), defaults to the current month.
        clickup_service: ClickUp service dependency.

    Returns:
        Monthly time report suitable for a calendar view.

    Edge cases:
        Missing ClickUp credentials return mock data.
    """
    return await clickup_service.get_month_time_entries(year, month)


@router.get("/personal-list-clients", response_model=PersonalListClientsResponse)
async def get_personal_list_clients(
    settings_service: SettingsService = Depends(get_settings_service),
    clickup_time_tool: ClickUpTimeTool = Depends(get_clickup_time_tool),
) -> PersonalListClientsResponse:
    """Return the valid client options configured on the personal ClickUp list.

    Lets the frontend offer a selector instead of free text when reviewing or
    correcting the client on a save_time_entry action.

    Parameters:
        settings_service: Settings service dependency.
        clickup_time_tool: ClickUp time tool dependency.

    Returns:
        Client options response.

    Edge cases:
        Empty list when no personal list is configured, the field is missing,
        or the field allows free text instead of fixed options — the frontend
        falls back to a plain text field in that case.
    """
    app_settings = await settings_service.get_settings()
    list_id = app_settings.clickup_personal_list_id
    if not list_id:
        return PersonalListClientsResponse(clients=[])

    result = await clickup_time_tool.execute(operation="get_clients", list_id=list_id)
    if not result.success or result.data is None:
        return PersonalListClientsResponse(clients=[])
    return PersonalListClientsResponse(clients=result.data.get("clients", []))
