from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.time import utc_now
from app.repositories.base import BaseRepository
from app.schemas.workflow import WorkflowRunDocument


class WorkflowRunRepository(BaseRepository):
    """Persist workflow execution audit records.

    Parameters:
        database: MongoDB database instance.

    Returns:
        Repository for `workflow_runs`.

    Edge cases:
        Failed workflows still get a finished_at timestamp.
    """

    def __init__(self, database: AsyncIOMotorDatabase) -> None:
        super().__init__(database, "workflow_runs")

    async def ensure_indexes(self) -> None:
        """Create workflow run indexes.

        Parameters:
            None.

        Returns:
            None.

        Edge cases:
            Safe to run multiple times.
        """
        await self.collection.create_index([("workflow_name", 1), ("fresh_ticket_id", 1), ("started_at", -1)])
        await self.collection.create_index("status")

    async def start(self, workflow_name: str, fresh_ticket_id: str | None, input_payload: dict) -> str:
        """Create a running workflow record.

        Parameters:
            workflow_name: Workflow identifier.
            fresh_ticket_id: Related Fresh ticket ID.
            input_payload: Workflow input data.

        Returns:
            Workflow run ID.

        Edge cases:
            fresh_ticket_id may be None for non-ticket workflows.
        """
        run = WorkflowRunDocument(
            workflow_name=workflow_name,
            fresh_ticket_id=fresh_ticket_id,
            status="running",
            input=input_payload,
            started_at=utc_now(),
        )
        return await self.insert_document(run.model_dump(), source="local_assistant")

    async def finish_success(self, run_id: str, output: dict) -> None:
        """Mark a workflow run as successful.

        Parameters:
            run_id: Workflow run ID.
            output: Workflow output data.

        Returns:
            None.

        Edge cases:
            Missing run ID results in no matched document.
        """
        await self.update_document(run_id, {"status": "success", "output": output, "error": None, "finished_at": utc_now()})

    async def finish_failure(self, run_id: str, error: str) -> None:
        """Mark a workflow run as failed.

        Parameters:
            run_id: Workflow run ID.
            error: Human-readable error message.

        Returns:
            None.

        Edge cases:
            Error text is stored for audit, not exposed verbatim to external systems.
        """
        await self.update_document(run_id, {"status": "failed", "error": error, "finished_at": utc_now()})

    async def list_runs(self, limit: int = 50, fresh_ticket_id: str | None = None) -> list[dict[str, Any]]:
        """List workflow runs ordered by newest first.

        Parameters:
            limit: Maximum number of workflow runs to return.
            fresh_ticket_id: Optional Fresh ticket ID filter.

        Returns:
            Serialized workflow run documents.

        Edge cases:
            Limit is clamped by the API layer; repository accepts already validated values.
        """
        query: dict[str, Any] = {}
        if fresh_ticket_id is not None:
            query["fresh_ticket_id"] = str(fresh_ticket_id)
        cursor = self.collection.find(query).sort("started_at", -1).limit(limit)
        items: list[dict[str, Any]] = []
        async for document in cursor:
            serialized = self.serialize(document)
            if serialized is not None:
                items.append(serialized)
        return items
