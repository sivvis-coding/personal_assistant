from app.assistant.schemas.context import AssistantContext
from app.repositories.integration_link_repository import IntegrationLinkRepository
from app.services.clickup_service import ClickUpService
from app.services.ticket_service import TicketService


class AssistantContextBuilder:
    """Build assistant context from existing application services.

    Parameters:
        ticket_service: Service used to read Fresh tickets.
        clickup_service: Service used to read ClickUp time data.
        integration_link_repository: Repository used to detect existing Fresh-to-ClickUp links.

    Returns:
        Context builder for assistant orchestration.

    Edge cases:
        Existing service mock fallbacks are preserved rather than hidden.
    """

    def __init__(
        self,
        ticket_service: TicketService,
        clickup_service: ClickUpService,
        integration_link_repository: IntegrationLinkRepository,
    ) -> None:
        """Initialize assistant context builder.

        Parameters:
            ticket_service: Service for ticket reads.
            clickup_service: Service for ClickUp time reads.
            integration_link_repository: Repository for Fresh-to-ClickUp links.

        Returns:
            None.

        Edge cases:
            Reads are delegated to existing services to preserve existing fallback behavior.
        """
        self._ticket_service = ticket_service
        self._clickup_service = clickup_service
        self._integration_link_repository = integration_link_repository

    async def build(self) -> AssistantContext:
        """Build the current assistant context snapshot.

        Parameters:
            None.

        Returns:
            Assistant context with tickets, weekly time, and backlog links.

        Edge cases:
            Link lookup is per ticket because the current repository exposes single-link reads only.
        """
        ticket_list = await self._ticket_service.list_tickets(scope="mine")
        week_time = await self._clickup_service.get_week_time_entries()
        existing_backlog_ticket_ids: list[str] = []
        for ticket in ticket_list.items:
            link = await self._integration_link_repository.find_link("fresh", ticket.id, "clickup_task")
            if link is not None:
                existing_backlog_ticket_ids.append(ticket.id)
        return AssistantContext(
            tickets=ticket_list.items,
            ticket_source=ticket_list.source,
            week_time=week_time,
            existing_backlog_ticket_ids=existing_backlog_ticket_ids,
        )
