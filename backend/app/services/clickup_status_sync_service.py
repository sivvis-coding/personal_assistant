"""ClickUp task status synchronisation service.

Polls all ticket_to_task integration links, compares each ClickUp task's
current status against the last-known status stored in the link document,
and posts a private internal note to the linked Freshservice ticket when a
change is detected.
"""

import logging

from app.domain.integration_link.value_objects import RelationType
from app.integrations.clickup import ClickUpClient
from app.repositories.integration_link_repository import IntegrationLinkRepository
from app.tools.freshservice.adapter import FreshserviceAdapter
from app.tools.freshservice.schemas import UpdateTicketInput

logger = logging.getLogger(__name__)


class ClickUpStatusSyncService:
    """Check ClickUp task statuses and notify Freshservice on changes.

    For each ``ticket_to_task`` integration link this service fetches the
    current ClickUp task status, compares it to the previously stored status,
    and — when a change is detected — posts a private internal note to the
    linked Freshservice ticket.  The new status is then persisted so the same
    change is never reported twice.

    Private notes are used intentionally: they are internal-only and therefore
    do NOT require HITL approval.

    Parameters:
        integration_link_repository: Repository for integration link documents.
        clickup_client: ClickUp API client used to fetch current task statuses.
        freshservice_adapter: Freshservice adapter used to post private notes.

    Returns:
        Service instance.

    Edge cases:
        Per-link failures are caught and recorded; they never abort the full
        run.  The service returns a summary list describing the outcome for
        each processed link.
    """

    def __init__(
        self,
        integration_link_repository: IntegrationLinkRepository,
        clickup_client: ClickUpClient,
        freshservice_adapter: FreshserviceAdapter,
    ) -> None:
        self._integration_link_repository = integration_link_repository
        self._clickup_client = clickup_client
        self._freshservice_adapter = freshservice_adapter

    async def sync_all(self) -> list[dict[str, object]]:
        """Sync ClickUp task statuses for all ticket_to_task links.

        Fetches the full task list once per run, then iterates over all stored
        integration links.  When a task's status differs from what was last
        recorded, a private Freshservice note is posted and the stored status
        is updated.

        Parameters:
            None.

        Returns:
            List of per-link result dicts, each containing:
            - ticket_id: Freshservice ticket identifier.
            - task_id: ClickUp task identifier.
            - old_status: Previously stored status (or None).
            - new_status: Status returned by ClickUp (or None on error).
            - action: One of "noted", "unchanged", "task_not_found", "error".

        Edge cases:
            If ClickUp returns no tasks (e.g. credentials missing) the service
            returns mock-mode results with action "unchanged".
        """
        results: list[dict[str, object]] = []

        links = await self._integration_link_repository.find_all_by_relation_type(
            RelationType.TICKET_TO_TASK
        )
        if not links:
            logger.info("clickup_status_sync: no ticket_to_task links found")
            return results

        # Fetch all tasks once and index by task ID to avoid N+1 API calls.
        try:
            tasks = await self._clickup_client.list_tasks()
        except Exception as exc:  # noqa: BLE001
            logger.exception("clickup_status_sync: failed to fetch tasks from ClickUp", exc_info=exc)
            for link in links:
                results.append({
                    "ticket_id": link.get("source_id"),
                    "task_id": link.get("target_id"),
                    "old_status": link.get("last_known_clickup_status"),
                    "new_status": None,
                    "action": "error",
                    "error": str(exc),
                })
            return results

        task_index = {task.id: task for task in tasks}

        for link in links:
            link_id = link.get("id")
            ticket_id = link.get("source_id")
            task_id = link.get("target_id")
            old_status = link.get("last_known_clickup_status")

            if not link_id or not ticket_id or not task_id:
                logger.warning(
                    "clickup_status_sync: skipping malformed link",
                    extra={"link": link},
                )
                continue

            result: dict[str, object] = {
                "ticket_id": ticket_id,
                "task_id": task_id,
                "old_status": old_status,
                "new_status": None,
                "action": "unchanged",
            }

            try:
                task = task_index.get(task_id)
                if task is None:
                    logger.warning(
                        "clickup_status_sync: task not found in ClickUp list",
                        extra={"task_id": task_id, "ticket_id": ticket_id},
                    )
                    result["action"] = "task_not_found"
                    results.append(result)
                    continue

                new_status = task.status
                result["new_status"] = new_status

                if new_status == old_status:
                    results.append(result)
                    continue

                # Status changed — post a private note and update the stored status.
                note_text = (
                    f"ClickUp task \"{task.name}\" moved to \"{new_status}\""
                )
                await self._freshservice_adapter.update_ticket(
                    UpdateTicketInput(ticket_id=ticket_id, changes={"note": note_text})
                )
                await self._integration_link_repository.update_link_status(link_id, new_status)

                result["action"] = "noted"
                logger.info(
                    "clickup_status_sync: status change noted",
                    extra={
                        "ticket_id": ticket_id,
                        "task_id": task_id,
                        "old_status": old_status,
                        "new_status": new_status,
                    },
                )

            except Exception as exc:  # noqa: BLE001
                logger.exception(
                    "clickup_status_sync: error processing link",
                    extra={"ticket_id": ticket_id, "task_id": task_id},
                    exc_info=exc,
                )
                result["action"] = "error"
                result["error"] = str(exc)

            results.append(result)

        return results
