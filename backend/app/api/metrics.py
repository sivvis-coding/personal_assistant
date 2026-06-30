from fastapi import APIRouter, Depends

from app.api.deps import (
    get_assistant_action_repository,
    get_clickup_service,
    get_ticket_service,
    require_auth,
)
from app.repositories.assistant_action_repository import AssistantActionRepository
from app.schemas.metrics import DashboardMetrics
from app.services.clickup_service import ClickUpService
from app.services.metrics_service import MetricsService
from app.services.ticket_service import TicketService

router = APIRouter(prefix="/metrics", tags=["metrics"], dependencies=[Depends(require_auth)])


@router.get("", response_model=DashboardMetrics)
async def get_dashboard_metrics(
    ticket_service: TicketService = Depends(get_ticket_service),
    clickup_service: ClickUpService = Depends(get_clickup_service),
    action_repository: AssistantActionRepository = Depends(get_assistant_action_repository),
) -> DashboardMetrics:
    """Return aggregated dashboard metrics.

    Parameters:
        ticket_service: Ticket service dependency.
        clickup_service: ClickUp service dependency.
        action_repository: Assistant action repository dependency.

    Returns:
        Dashboard metrics.

    Edge cases:
        Missing external credentials return zeros or mock-derived counts.
    """
    service = MetricsService(ticket_service, clickup_service, action_repository)
    return await service.get_dashboard_metrics()
