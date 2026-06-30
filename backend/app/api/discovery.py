from pydantic import BaseModel
from fastapi import APIRouter, Depends

from app.api.deps import require_auth
from app.schemas.discovery import (
    ClickUpDiscoveryResponse,
    ClickUpListFieldsResponse,
    ClickUpTeamsResponse,
    FreshserviceDiscoveryResponse,
    FreshserviceWorkspacesResponse,
)
from app.services.discovery_service import DiscoveryService

router = APIRouter(prefix="/settings/discover", tags=["discovery"], dependencies=[Depends(require_auth)])


class ClickUpDiscoveryRequest(BaseModel):
    """Request body for ClickUp discovery."""

    api_key: str


class ClickUpTeamListsRequest(BaseModel):
    """Request body for fetching lists scoped to a single ClickUp team."""

    api_key: str
    team_id: str


class ClickUpListFieldsRequest(BaseModel):
    """Request body for ClickUp list field discovery."""

    api_key: str
    list_id: str


class FreshserviceDiscoveryRequest(BaseModel):
    """Request body for Freshservice discovery."""

    base_url: str
    api_key: str


@router.post("/clickup/teams", response_model=ClickUpTeamsResponse)
async def discover_clickup_teams(request: ClickUpDiscoveryRequest) -> ClickUpTeamsResponse:
    """Discover ClickUp teams/workspaces only — single fast API call.

    Parameters:
        request: Contains the ClickUp API key.

    Returns:
        ClickUp teams.
    """
    service = DiscoveryService()
    return await service.discover_clickup_teams(request.api_key)


@router.post("/clickup/lists", response_model=ClickUpDiscoveryResponse)
async def discover_clickup_team_lists(request: ClickUpTeamListsRequest) -> ClickUpDiscoveryResponse:
    """Discover ClickUp lists for a specific team/workspace.

    Parameters:
        request: Contains the ClickUp API key and team ID.

    Returns:
        ClickUp lists for the given team.
    """
    service = DiscoveryService()
    return await service.discover_clickup_team_lists(request.api_key, request.team_id)


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


@router.post("/clickup/fields", response_model=ClickUpListFieldsResponse)
async def discover_clickup_list_fields(request: ClickUpListFieldsRequest) -> ClickUpListFieldsResponse:
    """Discover custom fields configured on a specific ClickUp list.

    Parameters:
        request: Contains the ClickUp API key and list ID.

    Returns:
        Custom fields for the list.

    Edge cases:
        Lists with no custom fields return an empty fields array.
    """
    service = DiscoveryService()
    return await service.discover_clickup_list_fields(request.api_key, request.list_id)


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
