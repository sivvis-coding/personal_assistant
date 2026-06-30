from pydantic import BaseModel


class DashboardMetrics(BaseModel):
    """Represent aggregated dashboard metrics.

    Parameters:
        tickets: Ticket counts (open, overdue, pending development, assigned to me).
        tasks: ClickUp task counts (pending, in progress, in sprint, blocked).
        time: Time tracking hours (today, week, month).
        actions: Pending assistant action counts.

    Returns:
        Dashboard metrics response.

    Edge cases:
        Some values may be zero when external integrations are unavailable.
    """

    tickets: dict[str, int]
    tasks: dict[str, int]
    time: dict[str, float]
    actions: dict[str, int]
