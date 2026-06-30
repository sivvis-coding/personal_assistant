"""Sync endpoints for on-demand integration synchronisation."""

from fastapi import APIRouter, Depends

from app.api.deps import get_clickup_status_sync_service, require_auth
from app.services.clickup_status_sync_service import ClickUpStatusSyncService

router = APIRouter(prefix="/sync", tags=["sync"], dependencies=[Depends(require_auth)])


@router.get("/clickup-status")
async def trigger_clickup_status_sync(
    sync_service: ClickUpStatusSyncService = Depends(get_clickup_status_sync_service),
) -> list[dict]:
    """Trigger an immediate ClickUp task status sync.

    Checks every ticket_to_task integration link, compares each ClickUp
    task's current status against the last-known status, and posts a
    private internal note to the linked Freshservice ticket for any link
    where the status changed.

    This endpoint is equivalent to triggering the scheduled sync job
    on demand and is useful for testing or forcing a sync outside the
    15-minute cron window.

    Parameters:
        sync_service: ClickUp status sync service dependency.

    Returns:
        List of per-link sync result dicts, each containing:
        - ticket_id: Freshservice ticket identifier.
        - task_id: ClickUp task identifier.
        - old_status: Previously stored status (or None).
        - new_status: Current ClickUp task status (or None on error).
        - action: One of "noted", "unchanged", "task_not_found", "error".

    Edge cases:
        Per-link errors are included in results with action "error";
        they never cause this endpoint to return a non-200 response.
    """
    return await sync_service.sync_all()
