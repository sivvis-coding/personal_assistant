from contextlib import asynccontextmanager
import logging
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import assistant, clickup, discovery, health, metrics, settings, sync, tickets, workflow_runs
from app.core.config import build_settings_from_overrides, get_settings, set_app_settings
from app.core.di.container import Container, bootstrap
from app.db.mongo import MongoManager
from app.repositories.ai_draft_repository import AiDraftRepository
from app.repositories.app_settings_repository import AppSettingsRepository
from app.repositories.assistant_action_repository import AssistantActionRepository
from app.repositories.conversation_repository import ConversationRepository
from app.repositories.integration_link_repository import IntegrationLinkRepository
from app.repositories.ticket_cache_repository import TicketCacheRepository
from app.repositories.workflow_run_repository import WorkflowRunRepository

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s:     %(message)s',
    force=True
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage application startup and shutdown resources.

    Parameters:
        app: FastAPI application instance.

    Returns:
        Async context manager yielding control to FastAPI.

    Edge cases:
        Mongo connection is closed even when startup-created app is stopped.
        The new event-driven architecture is bootstrapped alongside the
        existing API layer.
    """
    settings = get_settings()
    logger.info("Starting application with logging enabled")
    mongo_manager = MongoManager(settings)
    await mongo_manager.connect()
    app.state.mongo_manager = mongo_manager
    await ensure_indexes(mongo_manager)

    try:
        stored_settings = await AppSettingsRepository(mongo_manager.database).get_all()
        if stored_settings:
            merged_settings = build_settings_from_overrides(settings, stored_settings)
            get_settings.cache_clear()
            set_app_settings(merged_settings)
            settings = merged_settings
    except Exception:
        # Database settings are optional; environment values remain authoritative.
        pass

    container = Container()
    container.mongo_manager.override(mongo_manager)
    app.state.container = container
    await bootstrap(container)

    # Expose the three cross-cutting singletons directly on app.state so that
    # deps.py can read them without coupling to the container's Python API.
    app.state.memory_facade = container.memory_facade()
    app.state.llm_provider = container.llm_provider()
    app.state.tool_registry = container.tool_registry()

    try:
        yield
    finally:
        if hasattr(app.state, "container"):
            scheduler = app.state.container.scheduler()
            scheduler.shutdown()
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
    await ConversationRepository(database).ensure_indexes()
    await AssistantActionRepository(database).ensure_indexes()


app = FastAPI(title="Local Personal Assistant", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

app.include_router(health.router)
app.include_router(tickets.router)
app.include_router(clickup.router)
app.include_router(workflow_runs.router)
app.include_router(metrics.router)
app.include_router(settings.router)
app.include_router(discovery.router)
app.include_router(sync.router)
app.include_router(assistant.router)
