from fastapi import Depends, Request

from app.core.config import Settings, get_settings
from app.core.security import get_local_app_key_header, require_local_app_key
from app.db.mongo import MongoManager
from app.integrations.clickup import ClickUpClient
from app.integrations.fresh import FreshClient
from app.integrations.openai_client import OpenAIClient
from app.repositories.ai_draft_repository import AiDraftRepository
from app.repositories.integration_link_repository import IntegrationLinkRepository
from app.repositories.ticket_cache_repository import TicketCacheRepository
from app.repositories.workflow_run_repository import WorkflowRunRepository
from app.services.ai_service import AiService
from app.services.clickup_service import ClickUpService
from app.services.ticket_service import TicketService


async def require_auth(
    settings: Settings = Depends(get_settings),
    provided_key: str | None = Depends(get_local_app_key_header),
) -> None:
    """FastAPI dependency that enforces local header authentication.

    Parameters:
        settings: Application settings.
        provided_key: Value of X-Local-App-Key header.

    Returns:
        None when request is authorized.

    Edge cases:
        Empty LOCAL_APP_API_KEY disables authentication.
    """
    require_local_app_key(settings, provided_key)


def get_mongo_manager(request: Request) -> MongoManager:
    """Return Mongo manager stored in FastAPI application state.

    Parameters:
        request: FastAPI request.

    Returns:
        Mongo manager.

    Edge cases:
        Missing state means app lifespan was not initialized.
    """
    return request.app.state.mongo_manager


def get_ticket_service(
    mongo_manager: MongoManager = Depends(get_mongo_manager), settings: Settings = Depends(get_settings)
) -> TicketService:
    """Create ticket service dependency.

    Parameters:
        mongo_manager: Mongo manager dependency.
        settings: Application settings.

    Returns:
        Ticket service.

    Edge cases:
        Dependencies are lightweight and created per request.
    """
    return TicketService(FreshClient(settings), TicketCacheRepository(mongo_manager.database))


def get_ai_service(settings: Settings = Depends(get_settings)) -> AiService:
    """Create AI service dependency.

    Parameters:
        settings: Application settings.

    Returns:
        AI service.

    Edge cases:
        Missing OpenAI key creates mock-capable client.
    """
    return AiService(OpenAIClient(settings))


def get_clickup_client(settings: Settings = Depends(get_settings)) -> ClickUpClient:
    """Create ClickUp client dependency.

    Parameters:
        settings: Application settings.

    Returns:
        ClickUp client.

    Edge cases:
        Missing credentials create mock-capable client.
    """
    return ClickUpClient(settings)


def get_clickup_service(clickup_client: ClickUpClient = Depends(get_clickup_client)) -> ClickUpService:
    """Create ClickUp service dependency.

    Parameters:
        clickup_client: ClickUp client dependency.

    Returns:
        ClickUp service.

    Edge cases:
        None.
    """
    return ClickUpService(clickup_client)


def get_ai_draft_repository(mongo_manager: MongoManager = Depends(get_mongo_manager)) -> AiDraftRepository:
    """Create AI draft repository dependency.

    Parameters:
        mongo_manager: Mongo manager dependency.

    Returns:
        AI draft repository.

    Edge cases:
        None.
    """
    return AiDraftRepository(mongo_manager.database)


def get_workflow_run_repository(mongo_manager: MongoManager = Depends(get_mongo_manager)) -> WorkflowRunRepository:
    """Create workflow run repository dependency.

    Parameters:
        mongo_manager: Mongo manager dependency.

    Returns:
        Workflow run repository.

    Edge cases:
        None.
    """
    return WorkflowRunRepository(mongo_manager.database)


def get_integration_link_repository(mongo_manager: MongoManager = Depends(get_mongo_manager)) -> IntegrationLinkRepository:
    """Create integration link repository dependency.

    Parameters:
        mongo_manager: Mongo manager dependency.

    Returns:
        Integration link repository.

    Edge cases:
        None.
    """
    return IntegrationLinkRepository(mongo_manager.database)
