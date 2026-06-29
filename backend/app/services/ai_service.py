from app.integrations.openai_client import OpenAIClient
from app.schemas.ai import ReplyDraft, TicketSummary, UserStory
from app.schemas.ticket import Ticket


class AiService:
    """Coordinate AI operations for tickets.

    Parameters:
        openai_client: OpenAI integration client.

    Returns:
        Service wrapping AI transformations.

    Edge cases:
        Validation errors are raised by the integration client.
    """

    def __init__(self, openai_client: OpenAIClient) -> None:
        self._openai_client = openai_client

    @property
    def model_name(self) -> str:
        """Return the AI model name used by the underlying client.

        Parameters:
            None.

        Returns:
            Configured model name.

        Edge cases:
            Mock mode still returns the configured default model for traceability.
        """
        return self._openai_client.model

    async def summarize_ticket(self, ticket: Ticket) -> TicketSummary:
        """Summarize a ticket.

        Parameters:
            ticket: Ticket to summarize.

        Returns:
            Structured ticket summary.

        Edge cases:
            Missing OpenAI key uses mock output.
        """
        return await self._openai_client.summarize_ticket(ticket)

    async def draft_reply(self, ticket: Ticket) -> ReplyDraft:
        """Generate a reply draft for a ticket.

        Parameters:
            ticket: Ticket requiring reply.

        Returns:
            Structured reply draft.

        Edge cases:
            Reply is not sent automatically.
        """
        return await self._openai_client.draft_reply(ticket)

    async def ticket_to_user_story(self, ticket: Ticket) -> UserStory:
        """Convert a ticket into a user story.

        Parameters:
            ticket: Source ticket.

        Returns:
            Structured user story.

        Edge cases:
            Conservative mock output is used without OpenAI key.
        """
        return await self._openai_client.ticket_to_user_story(ticket)
