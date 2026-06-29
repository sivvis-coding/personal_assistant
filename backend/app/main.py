from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import clickup, health, tickets, workflow_runs
from app.core.config import get_settings
from app.db.mongo import MongoManager
from app.repositories.ai_draft_repository import AiDraftRepository
from app.repositories.app_settings_repository import AppSettingsRepository
from app.repositories.integration_link_repository import IntegrationLinkRepository
from app.repositories.ticket_cache_repository import TicketCacheRepository
from app.repositories.workflow_run_repository import WorkflowRunRepository


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage application startup and shutdown resources.

    Parameters:
        app: FastAPI application instance.

    Returns:
        Async context manager yielding control to FastAPI.

    Edge cases:
        Mongo connection is closed even when startup-created app is stopped.
    """
    settings = get_settings()
    mongo_manager = MongoManager(settings)
    await mongo_manager.connect()
    app.state.mongo_manager = mongo_manager
    await ensure_indexes(mongo_manager)
    try:
        yield
    finally:
        await mongo_manager.close()


async def ensure_indexes(mongo_manager: MongoManager) -> None:
    """Create MongoDB indexes for all repositories.

    Parameters:
        mongo_manager: Connected Mongo manager.

    Returns:
        None.

    Edge cases:
        Index creation is idempotent.
    """
    database = mongo_manager.database
    await TicketCacheRepository(database).ensure_indexes()
    await AiDraftRepository(database).ensure_indexes()
    await WorkflowRunRepository(database).ensure_indexes()
    await IntegrationLinkRepository(database).ensure_indexes()
    await AppSettingsRepository(database).ensure_indexes()


app = FastAPI(title="Local Personal Assistant", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(tickets.router)
app.include_router(clickup.router)
app.include_router(workflow_runs.router)
