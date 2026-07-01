from app.assistant.schemas.context import AssistantContext
from app.core.memory.interface import UserMemory
from app.domain.integration_link.value_objects import RelationType
from app.repositories.integration_link_repository import IntegrationLinkRepository
from app.services.clickup_service import ClickUpService
from app.services.settings_service import SettingsService
from app.services.ticket_service import TicketService


class AssistantContextBuilder:
    """Build assistant context from existing application services.

    Parameters:
        ticket_service: Service used to read Fresh tickets.
        clickup_service: Service used to read ClickUp time data.
        integration_link_repository: Repository used to detect existing Fresh-to-ClickUp links.
        settings_service: Service used to read editable settings (clickup_lists, agent_system_prompt).
        user_prefs: Optional user preferences store; loaded when present.

    Returns:
        Context builder for assistant orchestration.

    Edge cases:
        Existing service mock fallbacks are preserved rather than hidden.
        Settings failures are swallowed so the assistant can still respond without list config.
        user_prefs failures are swallowed so the assistant can still respond without preferences.
    """

    def __init__(
        self,
        ticket_service: TicketService,
        clickup_service: ClickUpService,
        integration_link_repository: IntegrationLinkRepository,
        settings_service: SettingsService,
        user_prefs: UserMemory | None = None,
    ) -> None:
        self._ticket_service = ticket_service
        self._clickup_service = clickup_service
        self._integration_link_repository = integration_link_repository
        self._settings_service = settings_service
        self._user_prefs = user_prefs

    async def build(self) -> AssistantContext:
        """Build the current assistant context snapshot.

        Parameters:
            None.

        Returns:
            Assistant context with tickets, weekly time, backlog links, list config, and user preferences.

        Edge cases:
            Link lookup is per ticket because the current repository exposes single-link reads only.
        """
        ticket_list = await self._ticket_service.list_tickets(scope="mine")
        week_time = await self._clickup_service.get_week_time_entries()
        existing_backlog_ticket_ids: list[str] = []
        for ticket in ticket_list.items:
            link = await self._integration_link_repository.find_link("fresh", ticket.id, RelationType.TICKET_TO_TASK)
            if link is not None:
                existing_backlog_ticket_ids.append(ticket.id)

        try:
            app_settings = await self._settings_service.get_settings()
            clickup_lists = app_settings.clickup_lists
            agent_system_prompt = app_settings.agent_system_prompt
        except Exception:  # noqa: BLE001
            clickup_lists = []
            agent_system_prompt = ""

        user_preferences: dict = {}
        if self._user_prefs is not None:
            try:
                user_preferences = await self._user_prefs.get_all()
            except Exception:  # noqa: BLE001
                pass

        return AssistantContext(
            tickets=ticket_list.items,
            ticket_source=ticket_list.source,
            week_time=week_time,
            existing_backlog_ticket_ids=existing_backlog_ticket_ids,
            clickup_lists=clickup_lists,
            agent_system_prompt=agent_system_prompt,
            user_preferences=user_preferences,
        )
