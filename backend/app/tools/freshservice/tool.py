"""Freshservice tool implementation."""

from typing import Any

from app.integrations.fresh import FreshClient
from app.services.ticket_service import TicketService
from app.tools.base import ToolInterface, ToolParameter, ToolResult
from app.tools.freshservice.adapter import FreshserviceAdapter
from app.tools.freshservice.schemas import (
    GetTicketInput,
    ListTicketsInput,
    ReplyTicketInput,
    SearchTicketsInput,
    UpdateTicketInput,
)


class FreshserviceTool(ToolInterface):
    """Tool exposing Freshservice operations to agents.

    Parameters:
        ticket_service: TicketService for cached reads.
        client: Existing FreshClient instance for writes.

    Returns:
        Freshservice tool instance.
    """

    name = "freshservice"
    description = "Read and update Freshservice tickets."
    parameters = [
        ToolParameter(name="operation", type="string", description="One of: list, get, update, reply, search"),
        ToolParameter(name="ticket_id", type="string", description="Freshservice ticket identifier", required=False),
        ToolParameter(name="body", type="string", description="Reply body or note content", required=False),
        ToolParameter(name="changes", type="object", description="Fields to update", required=False),
        ToolParameter(name="query", type="string", description="Search query", required=False),
        ToolParameter(name="scope", type="string", description="Ticket scope: mine or all", required=False, default="mine"),
    ]

    def __init__(self, ticket_service: TicketService, client: FreshClient) -> None:
        self._adapter = FreshserviceAdapter(ticket_service, client)

    async def execute(self, **kwargs: Any) -> ToolResult:
        """Execute a Freshservice operation.

        Parameters:
            **kwargs: Operation-specific parameters.

        Returns:
            Tool execution result.

        Edge cases:
            Unknown operations return an error result.
        """
        operation = kwargs.get("operation")

        try:
            if operation == "list":
                result = await self._adapter.list_assigned_tickets(ListTicketsInput(scope=kwargs.get("scope", "mine")))
                return ToolResult.ok(data=result, message=f"Listed {len(result.tickets)} tickets from {result.source}")

            if operation == "get":
                ticket_id = self._require(kwargs, "ticket_id")
                result = await self._adapter.get_ticket(GetTicketInput(ticket_id=ticket_id))
                return ToolResult.ok(data=result, message=f"Retrieved ticket {result.ticket.id} from {result.source}")

            if operation == "update":
                ticket_id = self._require(kwargs, "ticket_id")
                changes = kwargs.get("changes", {})
                data = await self._adapter.update_ticket(UpdateTicketInput(ticket_id=ticket_id, changes=changes))
                return ToolResult.ok(data=data, message=f"Updated ticket {ticket_id}")

            if operation == "reply":
                ticket_id = self._require(kwargs, "ticket_id")
                body = self._require(kwargs, "body")
                data = await self._adapter.reply_ticket(ReplyTicketInput(ticket_id=ticket_id, body=body))
                return ToolResult.ok(data=data, message=f"Replied to ticket {ticket_id}")

            if operation == "search":
                query = self._require(kwargs, "query")
                result = await self._adapter.search_tickets(SearchTicketsInput(query=query, limit=kwargs.get("limit", 20)))
                return ToolResult.ok(data=result, message=f"Found {len(result.tickets)} tickets matching '{query}'")

            return ToolResult.error(message=f"Unknown operation '{operation}' for freshservice tool")
        except Exception as exc:  # noqa: BLE001
            return ToolResult.error(message=str(exc))

    @staticmethod
    def _require(kwargs: dict[str, Any], key: str) -> Any:
        if key not in kwargs or kwargs[key] is None:
            raise ValueError(f"Missing required parameter '{key}'")
        return kwargs[key]
