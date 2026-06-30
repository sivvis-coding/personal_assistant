from typing import Any

from fastapi import APIRouter, Depends

from app.api.deps import get_mongo_manager, require_auth
from app.core.config import Settings, get_settings
from app.db.mongo import MongoManager

router = APIRouter(tags=["health"], dependencies=[Depends(require_auth)])


@router.get("/health")
async def health(mongo_manager: MongoManager = Depends(get_mongo_manager)) -> dict[str, str]:
    """Return application and MongoDB health status.

    Parameters:
        mongo_manager: Mongo manager dependency.

    Returns:
        Health status dictionary.

    Edge cases:
        Mongo ping failure is propagated as a 500 error by FastAPI.
    """
    await mongo_manager.database.command("ping")
    return {"status": "ok", "mongo": "ok"}


@router.get("/health/config")
async def health_config(settings: Settings = Depends(get_settings)) -> dict[str, Any]:
    """Return non-sensitive integration configuration for debugging.

    Parameters:
        settings: Application settings dependency.

    Returns:
        Configuration summary without API keys or secrets.

    Edge cases:
        Empty values indicate missing configuration.
    """
    return {
        "freshservice": {
            "base_url": settings.fresh_base_url,
            "has_api_key": bool(settings.fresh_api_key.strip()),
            "assigned_agent_id": settings.fresh_assigned_agent_id,
            "assigned_agent_field": settings.fresh_assigned_agent_field,
        },
        "clickup": {
            "has_api_key": bool(settings.clickup_api_key.strip()),
            "team_id": settings.clickup_team_id,
            "list_id": settings.clickup_list_id,
        },
        "openai": {
            "has_api_key": bool(settings.openai_api_key.strip()),
            "model": settings.openai_model,
        },
    }
