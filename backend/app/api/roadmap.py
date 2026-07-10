from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_roadmap_service, require_auth
from app.core.errors import ExternalServiceError
from app.schemas.roadmap import (
    RoadmapResponse,
    RoadmapSummariesResponse,
    SaveRoadmapRequest,
    SummarizeRoadmapRequest,
)
from app.services.roadmap_service import RoadmapService

router = APIRouter(prefix="/roadmap", tags=["roadmap"], dependencies=[Depends(require_auth)])


@router.get("", response_model=RoadmapResponse)
async def get_roadmap(
    roadmap_service: RoadmapService = Depends(get_roadmap_service),
) -> RoadmapResponse:
    """Return the saved roadmap rehydrated with live ClickUp tasks.

    Parameters:
        roadmap_service: Roadmap service dependency.

    Returns:
        Persisted roadmap, or persisted=False when it was never generated.

    Edge cases:
        External failures (ClickUp) surface as HTTP 502.
    """
    try:
        return await roadmap_service.get_persisted()
    except ExternalServiceError as error:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(error)) from error


@router.post("/generate", response_model=RoadmapResponse)
async def generate_roadmap(
    roadmap_service: RoadmapService = Depends(get_roadmap_service),
) -> RoadmapResponse:
    """Regroup all live tasks by theme via the LLM, persist, and return.

    Parameters:
        roadmap_service: Roadmap service dependency.

    Returns:
        Freshly generated and saved roadmap.

    Edge cases:
        Overwrites any manual edits (explicit "regroup with AI" action).
        External failures (ClickUp/OpenAI) surface as HTTP 502.
    """
    try:
        return await roadmap_service.generate()
    except ExternalServiceError as error:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(error)) from error


@router.put("", response_model=RoadmapResponse)
async def save_roadmap(
    request: SaveRoadmapRequest,
    roadmap_service: RoadmapService = Depends(get_roadmap_service),
) -> RoadmapResponse:
    """Persist an edited roadmap structure (drag & drop / group edits).

    Parameters:
        request: Edited group structure from the UI.
        roadmap_service: Roadmap service dependency.

    Returns:
        Rehydrated, saved roadmap.

    Edge cases:
        External failures (ClickUp) surface as HTTP 502.
    """
    try:
        return await roadmap_service.save(request.groups)
    except ExternalServiceError as error:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(error)) from error


@router.post("/summaries", response_model=RoadmapSummariesResponse)
async def summarize_roadmap(
    request: SummarizeRoadmapRequest,
    roadmap_service: RoadmapService = Depends(get_roadmap_service),
) -> RoadmapSummariesResponse:
    """Return an AI summary for each list from its currently-visible tasks.

    Parameters:
        request: Lists with their filtered tasks to summarize.
        roadmap_service: Roadmap service dependency.

    Returns:
        One summary per non-empty list (not persisted; reflects the filter).

    Edge cases:
        External failures (OpenAI) surface as HTTP 502.
    """
    try:
        return await roadmap_service.summarize(request.lists)
    except ExternalServiceError as error:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(error)) from error
