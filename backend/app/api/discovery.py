from pydantic import BaseModel
from fastapi import APIRouter, Depends

from app.api.deps import require_auth
from app.schemas.discovery import (
    ClickUpDiscoveryResponse,
    FreshserviceDiscoveryResponse,
    FreshserviceWorkspacesResponse,
)
from app.services.discovery_service import DiscoveryService

router = APIRouter(prefix="/settings/discover", tags=["discovery"], dependencies=[Depends(require_auth)])


class ClickUpDiscoveryRequest(BaseModel):
    """Request body for ClickUp discovery."""

    api_key: str


class FreshserviceDiscoveryRequest(BaseModel):
    """Request body for Freshservice discovery."""

    base_url: str
    api_key: str


@router.post("/clickup", response_model=ClickUpDiscoveryResponse)
async def discover_clickup(request: ClickUpDiscoveryRequest) -> ClickUpDiscoveryResponse:
    """Discover ClickUp teams and lists.

    Parameters:
        request: Contains the ClickUp API key.

    Returns:
        ClickUp teams and lists.

    Edge cases:
        Invalid API key returns an external service error.
    """
    service = DiscoveryService()
    return await service.discover_clickup(request.api_key)


@router.post("/freshservice", response_model=FreshserviceDiscoveryResponse)
async def discover_freshservice(request: FreshserviceDiscoveryRequest) -> FreshserviceDiscoveryResponse:
    """Discover Freshservice agents.

    Parameters:
        request: Contains Freshservice base URL and API key.

    Returns:
        Freshservice agents.

    Edge cases:
        Invalid credentials return an external service error.
    """
    service = DiscoveryService()
    return await service.discover_freshservice(request.base_url, request.api_key)


@router.post("/freshservice/workspaces", response_model=FreshserviceWorkspacesResponse)
async def discover_freshservice_workspaces(
    request: FreshserviceDiscoveryRequest,
) -> FreshserviceWorkspacesResponse:
    """Discover Freshservice workspaces.

    Parameters:
        request: Contains Freshservice base URL and API key.

    Returns:
        Freshservice workspaces.

    Edge cases:
        Workspaces endpoint may be unavailable on older Freshservice plans.
    """
    service = DiscoveryService()
    return await service.discover_freshservice_workspaces(request.base_url, request.api_key)
