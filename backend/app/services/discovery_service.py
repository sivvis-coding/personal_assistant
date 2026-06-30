import logging
from typing import Any

import httpx

from app.core.errors import ExternalServiceError
from app.schemas.discovery import (
    ClickUpDiscoveryResponse,
    ClickUpList,
    ClickUpTeam,
    FreshserviceAgent,
    FreshserviceDiscoveryResponse,
    FreshserviceWorkspace,
    FreshserviceWorkspacesResponse,
)

logger = logging.getLogger(__name__)


class DiscoveryService:
    """Discover integration IDs from external APIs.

    Parameters:
        None.

    Returns:
        Discovery service instance.

    Edge cases:
        Invalid credentials are propagated as external service errors.
    """

    async def discover_clickup(self, api_key: str) -> ClickUpDiscoveryResponse:
        """List ClickUp teams and lists available for the provided API key.

        Parameters:
            api_key: ClickUp API key.

        Returns:
            ClickUp teams and lists.

        Edge cases:
            Lists are discovered by iterating over all teams, spaces, folders, and paginated list endpoints.
        """
        headers = {"Authorization": api_key}
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                teams_response = await client.get("https://api.clickup.com/api/v2/team", headers=headers)
                teams_response.raise_for_status()
                teams_data = teams_response.json()

                teams: list[ClickUpTeam] = []
                lists: list[ClickUpList] = []

                for team in teams_data.get("teams", []):
                    team_id = str(team.get("id"))
                    team_name = str(team.get("name") or "Unnamed team")
                    teams.append(ClickUpTeam(id=team_id, name=team_name))
                    logger.info("ClickUp team discovered: %s (%s)", team_name, team_id)

                    spaces = await self._get_clickup_spaces(client, headers, team_id)
                    logger.info("ClickUp team %s: %d spaces", team_name, len(spaces))
                    for space in spaces:
                        space_id = str(space.get("id"))
                        space_name = str(space.get("name") or "Unnamed space")

                        space_lists = await self._get_clickup_lists(
                            client, headers, f"space/{space_id}"
                        )
                        logger.info(
                            "ClickUp space %s > %s: %d direct lists",
                            team_name,
                            space_name,
                            len(space_lists),
                        )
                        for list_item in space_lists:
                            lists.append(
                                ClickUpList(
                                    id=str(list_item.get("id")),
                                    name=f"{team_name} > {space_name} > {list_item.get('name')}",
                                )
                            )

                        folders = await self._get_clickup_folders(client, headers, space_id)
                        logger.info(
                            "ClickUp space %s > %s: %d folders", team_name, space_name, len(folders)
                        )
                        for folder in folders:
                            folder_id = str(folder.get("id"))
                            folder_name = str(folder.get("name") or "Unnamed folder")
                            folder_lists = await self._get_clickup_lists(
                                client, headers, f"folder/{folder_id}"
                            )
                            logger.info(
                                "ClickUp folder %s > %s > %s: %d lists",
                                team_name,
                                space_name,
                                folder_name,
                                len(folder_lists),
                            )
                            for list_item in folder_lists:
                                lists.append(
                                    ClickUpList(
                                        id=str(list_item.get("id")),
                                        name=f"{team_name} > {space_name} > {folder_name} > {list_item.get('name')}",
                                    )
                                )

                logger.info("ClickUp discovery complete: %d teams, %d lists", len(teams), len(lists))
                return ClickUpDiscoveryResponse(teams=teams, lists=lists)
        except httpx.HTTPStatusError as error:
            body = error.response.text
            logger.error("ClickUp discovery failed: %s - body: %s", error, body)
            raise ExternalServiceError(f"ClickUp discovery failed: {error} - {body}") from error
        except httpx.HTTPError as error:
            logger.error("ClickUp discovery failed: %s", error)
            raise ExternalServiceError(f"ClickUp discovery failed: {error}") from error

    async def _get_clickup_spaces(
        self, client: httpx.AsyncClient, headers: dict[str, str], team_id: str
    ) -> list[dict[str, Any]]:
        """Fetch non-archived spaces for a ClickUp team."""
        response = await client.get(
            f"https://api.clickup.com/api/v2/team/{team_id}/space",
            headers=headers,
            params={"archived": "false"},
        )
        response.raise_for_status()
        return response.json().get("spaces", [])

    async def _get_clickup_folders(
        self, client: httpx.AsyncClient, headers: dict[str, str], space_id: str
    ) -> list[dict[str, Any]]:
        """Fetch all non-archived folders for a ClickUp space with pagination."""
        return await self._paginate_clickup(client, headers, f"space/{space_id}/folder", "folders")

    async def _get_clickup_lists(
        self, client: httpx.AsyncClient, headers: dict[str, str], resource_path: str
    ) -> list[dict[str, Any]]:
        """Fetch all non-archived lists for a ClickUp resource with pagination."""
        return await self._paginate_clickup(
            client, headers, f"{resource_path}/list", "lists", params={"archived": "false"}
        )

    async def _paginate_clickup(
        self,
        client: httpx.AsyncClient,
        headers: dict[str, str],
        resource_path: str,
        data_key: str,
        params: dict[str, str] | None = None,
    ) -> list[dict[str, Any]]:
        """Paginate through a ClickUp list endpoint.

        Parameters:
            client: Async HTTP client.
            headers: Request headers.
            resource_path: ClickUp API path segment (e.g. "space/{id}/folder").
            data_key: JSON key containing the array of items.
            params: Additional query parameters.

        Returns:
            Aggregated list of items across all pages.
        """
        items: list[dict[str, Any]] = []
        page = 0
        per_page = 100
        base_params = dict(params) if params else {}
        while True:
            page_params = {**base_params, "page": str(page), "per_page": str(per_page)}
            response = await client.get(
                f"https://api.clickup.com/api/v2/{resource_path}",
                headers=headers,
                params=page_params,
            )
            response.raise_for_status()
            page_items = response.json().get(data_key, [])
            if not isinstance(page_items, list):
                break
            items.extend(page_items)
            if len(page_items) < per_page:
                break
            page += 1
        return items

    async def discover_freshservice(self, base_url: str, api_key: str) -> FreshserviceDiscoveryResponse:
        """List Freshservice agents available for the provided credentials.

        Parameters:
            base_url: Freshservice workspace URL.
            api_key: Freshservice API key.

        Returns:
            Freshservice agents.

        Edge cases:
            Pagination is handled for up to 100 agents.
        """
        url = base_url.rstrip('/')
        agents: list[FreshserviceAgent] = []
        page = 1
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                while True:
                    response = await client.get(
                        f"{url}/api/v2/agents",
                        auth=(api_key, "X"),
                        params={"page": page, "per_page": 100},
                    )
                    response.raise_for_status()
                    payload = response.json()
                    items = payload.get("agents", [])
                    if not items:
                        break
                    for agent in items:
                        agents.append(
                            FreshserviceAgent(
                                id=str(agent.get("id")),
                                name=str(agent.get("first_name") or agent.get("name") or "Unknown"),
                                email=agent.get("email"),
                            )
                        )
                    if len(items) < 100:
                        break
                    page += 1

                return FreshserviceDiscoveryResponse(agents=agents)
        except httpx.HTTPStatusError as error:
            body = error.response.text
            logger.error("Freshservice agents discovery failed: %s - body: %s", error, body)
            raise ExternalServiceError(f"Freshservice discovery failed: {error} - {body}") from error
        except httpx.HTTPError as error:
            logger.error("Freshservice agents discovery failed: %s", error)
            raise ExternalServiceError(f"Freshservice discovery failed: {error}") from error

    async def discover_freshservice_workspaces(
        self, base_url: str, api_key: str
    ) -> FreshserviceWorkspacesResponse:
        """List Freshservice workspaces available for the provided credentials.

        Parameters:
            base_url: Freshservice workspace URL.
            api_key: Freshservice API key.

        Returns:
            Freshservice workspaces.

        Edge cases:
            Workspaces that cannot be listed are skipped.
        """
        url = base_url.rstrip('/')
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                response = await client.get(
                    f"{url}/api/v2/workspaces",
                    auth=(api_key, "X"),
                )
                response.raise_for_status()
                payload = response.json()
                workspaces = [
                    FreshserviceWorkspace(
                        id=str(workspace.get("id")),
                        name=str(workspace.get("name") or "Unnamed workspace"),
                    )
                    for workspace in payload.get("workspaces", [])
                ]
                logger.info("Freshservice workspaces discovered: %d", len(workspaces))
                return FreshserviceWorkspacesResponse(workspaces=workspaces)
        except httpx.HTTPStatusError as error:
            body = error.response.text
            logger.error("Freshservice workspaces discovery failed: %s - body: %s", error, body)
            raise ExternalServiceError(
                f"Freshservice workspaces discovery failed: {error} - {body}"
            ) from error
        except httpx.HTTPError as error:
            logger.error("Freshservice workspaces discovery failed: %s", error)
            raise ExternalServiceError(f"Freshservice workspaces discovery failed: {error}") from error
