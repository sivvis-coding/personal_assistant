"""Integration links API — ticket ↔ ClickUp task pairs."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.deps import get_clickup_client, get_integration_link_repository, get_ticket_service, require_auth
from app.domain.integration_link.value_objects import RelationType
from app.integrations.clickup import ClickUpClient
from app.repositories.integration_link_repository import IntegrationLinkRepository
from app.services.ticket_service import TicketService

router = APIRouter(prefix="/integration-links", tags=["integration-links"], dependencies=[Depends(require_auth)])


class LinkedTaskItem(BaseModel):
    """One ticket ↔ ClickUp task pair with live status.

    Parameters:
        link_id: MongoDB ID of the integration link.
        ticket_id: Freshservice ticket identifier.
        ticket_subject: Ticket subject (empty when fetch failed).
        ticket_status: Ticket status (empty when fetch failed).
        clickup_task_id: ClickUp task identifier.
        clickup_task_url: ClickUp task URL, may be None.
        clickup_status: Live ClickUp task status (empty when fetch failed or no credentials).
        last_known_clickup_status: Cached ClickUp status from last sync run.
        created_at: ISO timestamp of the link creation.
    """

    link_id: str
    ticket_id: str
    ticket_subject: str = ""
    ticket_status: str = ""
    clickup_task_id: str
    clickup_task_url: str | None = None
    clickup_status: str = ""
    last_known_clickup_status: str | None = None
    created_at: str = ""


@router.get("", response_model=list[LinkedTaskItem])
async def list_linked_tasks(
    integration_link_repository: IntegrationLinkRepository = Depends(get_integration_link_repository),
    ticket_service: TicketService = Depends(get_ticket_service),
    clickup_client: ClickUpClient = Depends(get_clickup_client),
) -> list[LinkedTaskItem]:
    """Return all ticket ↔ ClickUp task pairs with enriched status.

    Parameters:
        integration_link_repository: Repository for integration links.
        ticket_service: Ticket service for fetching Fresh ticket details.
        clickup_client: ClickUp client for fetching live task status.

    Returns:
        List of linked task items sorted by creation date descending.

    Edge cases:
        Ticket or ClickUp fetch failures degrade gracefully — the link is still returned.
        ClickUp status is only fetched when credentials are configured.
    """
    links = await integration_link_repository.find_all_by_relation_type(RelationType.TICKET_TO_TASK)

    items: list[LinkedTaskItem] = []
    for link in links:
        ticket_subject = ""
        ticket_status = ""
        clickup_status = ""

        try:
            ticket_response = await ticket_service.get_ticket(str(link["source_id"]))
            ticket_subject = ticket_response.ticket.subject
            ticket_status = ticket_response.ticket.status
        except Exception:  # noqa: BLE001
            pass

        try:
            task = await clickup_client.get_task(str(link["target_id"]))
            if task is not None:
                clickup_status = task.status
        except Exception:  # noqa: BLE001
            pass

        items.append(
            LinkedTaskItem(
                link_id=str(link.get("id", "")),
                ticket_id=str(link["source_id"]),
                ticket_subject=ticket_subject,
                ticket_status=ticket_status,
                clickup_task_id=str(link["target_id"]),
                clickup_task_url=link.get("target_url"),
                clickup_status=clickup_status,
                last_known_clickup_status=link.get("last_known_clickup_status"),
                created_at=str(link.get("created_at", "")),
            )
        )

    items.sort(key=lambda x: x.created_at, reverse=True)
    return items
