"""Adapter from existing FreshClient to the tool boundary.

This module keeps the existing FreshClient untouched while exposing its
capabilities through the ToolInterface contract.
"""

from app.integrations.fresh import FreshClient
from app.services.ticket_service import TicketService
from app.tools.freshservice.schemas import (
    GetTicketInput,
    ListTicketsInput,
    ReplyTicketInput,
    SearchTicketsInput,
    TicketDetailResult,
    TicketListResult,
    UpdateTicketInput,
)


class FreshserviceAdapter:
    """Thin adapter around TicketService and FreshClient.

    Parameters:
        ticket_service: Service for cached ticket reads.
        client: Existing FreshClient instance for write operations.

    Returns:
        Adapter instance.
    """

    def __init__(self, ticket_service: TicketService, client: FreshClient) -> None:
        self._ticket_service = ticket_service
        self._client = client

    async def list_assigned_tickets(self, input_data: ListTicketsInput) -> TicketListResult:
        """List tickets from Freshservice via TicketService cache."""
        response = await self._ticket_service.list_tickets(input_data.scope)
        return TicketListResult(tickets=response.items, source=response.source)

    async def get_ticket(self, input_data: GetTicketInput) -> TicketDetailResult:
        """Get a single ticket from Freshservice via TicketService cache."""
        response = await self._ticket_service.get_ticket(input_data.ticket_id)
        return TicketDetailResult(ticket=response.ticket, source=response.source)

    async def update_ticket(self, input_data: UpdateTicketInput) -> dict[str, object]:
        """Update a Freshservice ticket with a private internal note.

        Internal notes from automated workflows (e.g. ClickUp task link
        notifications) are always posted as private notes so they are never
        visible to the customer requester without human approval.
        """
        note = input_data.changes.get("note")
        if note:
            return await self._client.add_note(input_data.ticket_id, str(note), private=True)
        return {"mock": True, "ticket_id": input_data.ticket_id, "changes": input_data.changes}

    async def reply_ticket(self, input_data: ReplyTicketInput) -> dict[str, object]:
        """Add a public customer-facing reply to a Freshservice ticket.

        SAFETY: This method sends a PUBLIC reply to the customer.
        It must only be called from AssistantActionExecutor after an approved
        reply_freshservice_ticket AssistantAction has passed safety policy
        validation.  Do NOT call this method from agents or event handlers
        directly.
        """
        return await self._client.add_reply(input_data.ticket_id, input_data.body)

    async def search_tickets(self, input_data: SearchTicketsInput) -> TicketListResult:
        """Search tickets by keyword.

        Phase 1 implementation lists assigned tickets and filters client-side.
        A server-side search will be added when Freshservice supports it.
        """
        response = await self._ticket_service.list_tickets("all")
        query_lower = input_data.query.lower()
        filtered = [
            ticket
            for ticket in response.items
            if query_lower in ticket.subject.lower()
            or (ticket.description and query_lower in ticket.description.lower())
        ][: input_data.limit]
        return TicketListResult(tickets=filtered, source=response.source)
