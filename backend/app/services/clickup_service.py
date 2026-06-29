from app.integrations.clickup import ClickUpClient
from app.schemas.clickup import WeekTimeResponse


class ClickUpService:
    """Coordinate ClickUp read-only service operations.

    Parameters:
        clickup_client: ClickUp integration client.

    Returns:
        Service for ClickUp operations.

    Edge cases:
        External errors are handled by API layer as HTTP errors.
    """

    def __init__(self, clickup_client: ClickUpClient) -> None:
        self._clickup_client = clickup_client

    async def get_week_time_entries(self) -> WeekTimeResponse:
        """Return current week time entries.

        Parameters:
            None.

        Returns:
            Weekly time report.

        Edge cases:
            Mock data is returned when ClickUp credentials are missing.
        """
        return await self._clickup_client.get_week_time_entries()
