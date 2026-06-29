from fastapi import APIRouter, Depends

from app.api.deps import get_clickup_service, require_auth
from app.schemas.clickup import WeekTimeResponse
from app.services.clickup_service import ClickUpService

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
