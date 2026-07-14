"""Insights endpoints: Freshservice history archive + knowledge base."""

import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse

from app.api.deps import (
    get_fresh_archive_repository,
    get_fresh_archive_service,
    get_insights_export_service,
    get_knowledge_service,
    get_operation_lock_repository,
    require_auth,
)
from app.core.errors import ExternalServiceError
from app.repositories.fresh_ticket_archive_repository import FreshTicketArchiveRepository
from app.repositories.operation_lock_repository import OperationLockRepository
from app.schemas.insights import (
    ArchivedTicket,
    ArchivedTicketsResponse,
    BackfillRequest,
    GenerateKnowledgeRequest,
    HarvestStatus,
    KnowledgeResponse,
    WorkspacesResponse,
)
from app.services.fresh_archive_service import FreshArchiveService
from app.services.insights_export_service import InsightsExportService
from app.services.knowledge_service import KnowledgeService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/insights", tags=["insights"], dependencies=[Depends(require_auth)])

# A single lock serializes the heavy operations (backfill/sync/generate); overlapping
# runs previously corrupted harvest state and produced partial-snapshot knowledge.
INSIGHTS_LOCK = "insights"
# Longer than the slowest operation; also the staleness TTL that auto-frees a lock
# left behind by a killed process (e.g. dev hot-reload).
LOCK_TTL_SECONDS = 7200


async def _run_and_release(coro_factory, lock: OperationLockRepository) -> None:
    """Run a guarded background operation and always release the lock afterwards."""
    try:
        await coro_factory()
    except Exception:  # noqa: BLE001 — background task; log and still release the lock
        logger.exception("Insights background operation failed")
    finally:
        await lock.release(INSIGHTS_LOCK)


@router.get("/status", response_model=HarvestStatus)
async def get_status(
    service: FreshArchiveService = Depends(get_fresh_archive_service),
) -> HarvestStatus:
    """Return per-workspace harvest progress and archive counts.

    Edge cases:
        External failures surface as HTTP 502.
    """
    try:
        return await service.status()
    except ExternalServiceError as error:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(error)) from error


@router.get("/workspaces", response_model=WorkspacesResponse)
async def get_workspaces(
    service: FreshArchiveService = Depends(get_fresh_archive_service),
) -> WorkspacesResponse:
    """List workspaces available in Freshservice and those already configured."""
    try:
        return await service.workspaces_overview()
    except ExternalServiceError as error:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(error)) from error


@router.post("/workspaces/import", response_model=WorkspacesResponse)
async def import_workspaces(
    service: FreshArchiveService = Depends(get_fresh_archive_service),
) -> WorkspacesResponse:
    """Discover workspaces from Freshservice and save them into the config."""
    try:
        return await service.import_workspaces()
    except ExternalServiceError as error:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(error)) from error


@router.post("/backfill", response_model=HarvestStatus)
async def trigger_backfill(
    request: BackfillRequest,
    background_tasks: BackgroundTasks,
    service: FreshArchiveService = Depends(get_fresh_archive_service),
    lock: OperationLockRepository = Depends(get_operation_lock_repository),
) -> HarvestStatus:
    """Kick off a resumable historic backfill in the background.

    Returns the current status immediately; the UI refreshes on demand to see
    progress. The one-shot backfill can be long, so it runs detached.

    Edge cases:
        Rejected with HTTP 409 when another Insights operation is already running.
    """
    if not await lock.try_acquire(INSIGHTS_LOCK, LOCK_TTL_SECONDS):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Ya hay una operación de Insights en curso.")
    background_tasks.add_task(
        _run_and_release, lambda: service.backfill(request.workspace_id, request.since_months), lock
    )
    return await service.status()


@router.post("/sync", response_model=HarvestStatus)
async def trigger_sync(
    background_tasks: BackgroundTasks,
    service: FreshArchiveService = Depends(get_fresh_archive_service),
    lock: OperationLockRepository = Depends(get_operation_lock_repository),
) -> HarvestStatus:
    """Kick off an incremental sync in the background and return current status.

    Edge cases:
        Rejected with HTTP 409 when another Insights operation is already running.
    """
    if not await lock.try_acquire(INSIGHTS_LOCK, LOCK_TTL_SECONDS):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Ya hay una operación de Insights en curso.")
    background_tasks.add_task(_run_and_release, lambda: service.sync_incremental(), lock)
    return await service.status()


@router.get("/tickets", response_model=ArchivedTicketsResponse)
async def list_tickets(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    archive_repository: FreshTicketArchiveRepository = Depends(get_fresh_archive_repository),
) -> ArchivedTicketsResponse:
    """Return a page of archived tickets with their per-ticket signature ficha."""
    items, total = await archive_repository.list_paginated(skip, limit)
    return ArchivedTicketsResponse(
        items=[ArchivedTicket.model_validate(item) for item in items],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.post("/knowledge/generate", response_model=KnowledgeResponse)
async def generate_knowledge(
    request: GenerateKnowledgeRequest,
    background_tasks: BackgroundTasks,
    service: KnowledgeService = Depends(get_knowledge_service),
    lock: OperationLockRepository = Depends(get_operation_lock_repository),
) -> KnowledgeResponse:
    """Kick off knowledge-base generation in the background; return current KB.

    Edge cases:
        Signature summarization + clustering can be long, so it runs detached
        and the UI refreshes to pick up the new knowledge base.
        Rejected with HTTP 409 when another Insights operation is already running.
    """
    if not await lock.try_acquire(INSIGHTS_LOCK, LOCK_TTL_SECONDS):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Ya hay una operación de Insights en curso.")
    background_tasks.add_task(_run_and_release, lambda: service.generate(request.statuses), lock)
    return await service.get_persisted()


@router.get("/knowledge", response_model=KnowledgeResponse)
async def get_knowledge(
    service: KnowledgeService = Depends(get_knowledge_service),
) -> KnowledgeResponse:
    """Return the persisted knowledge base (themes + recurring-bug ranking)."""
    try:
        return await service.get_persisted()
    except ExternalServiceError as error:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(error)) from error


@router.get("/export")
async def export_insights(
    include: str = Query("themes"),
    workspace_id: str | None = Query(None),
    export_service: InsightsExportService = Depends(get_insights_export_service),
) -> StreamingResponse:
    """Stream the knowledge base + ticket archive as newline-delimited JSON.

    One line = one ExportRecord (plain-text content + metadata), meant for
    ingestion into an external RAG search index (e.g. Azure AI Search).

    Parameters:
        include: Comma-separated subset of "themes"/"bottlenecks"/"automation"/
            "metrics"/"tickets". Defaults to "themes" only — themes carry the
            symptom → resolution knowledge a support RAG needs; the rest are
            opt-in for other use cases (process improvement, ticket lookup).
        workspace_id: Optional filter to a single department/workspace.

    Edge cases:
        Read-only — does not take the Insights operation lock.
    """
    included = {part.strip() for part in include.split(",") if part.strip()}
    return StreamingResponse(
        export_service.stream(included, workspace_id),
        media_type="application/x-ndjson",
        headers={"Content-Disposition": 'attachment; filename="insights_export.jsonl"'},
    )
