from fastapi import APIRouter, Depends

from app.api.deps import get_mongo_manager, require_auth
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
