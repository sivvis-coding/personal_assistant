import asyncio
import logging
from typing import Any

import httpx

from app.core.errors import ExternalServiceError
from app.schemas.discovery import (
    ClickUpCustomField,
    ClickUpDiscoveryResponse,
    ClickUpList,
    ClickUpListFieldsResponse,
    ClickUpTeam,
    ClickUpTeamsResponse,
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

    async def discover_clickup_teams(self, api_key: str) -> ClickUpTeamsResponse:
        """Return only ClickUp teams/workspaces — single fast API call.

        Parameters:
            api_key: ClickUp API key.

        Returns:
            Teams response.
        """
        headers = {"Authorization": api_key}
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.get("https://api.clickup.com/api/v2/team", headers=headers)
                response.raise_for_status()
                teams = [
                    ClickUpTeam(id=str(t.get("id")), name=str(t.get("name") or "Unnamed team"))
                    for t in response.json().get("teams", [])
                ]
                return ClickUpTeamsResponse(teams=teams)
        except httpx.HTTPStatusError as error:
            body = error.response.text
            raise ExternalServiceError(f"ClickUp teams discovery failed: {error} - {body}") from error
        except httpx.HTTPError as error:
            raise ExternalServiceError(f"ClickUp teams discovery failed: {error}") from error

    async def discover_clickup_team_lists(self, api_key: str, team_id: str) -> ClickUpDiscoveryResponse:
        """Return lists for a single ClickUp team using parallel fetching.

        Parameters:
            api_key: ClickUp API key.
            team_id: Team/workspace ID to scope the discovery.

        Returns:
            Discovery response with lists from the given team only.
        """
        headers = {"Authorization": api_key}
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                # Fetch team name and spaces concurrently.
                teams_resp, spaces = await asyncio.gather(
                    client.get("https://api.clickup.com/api/v2/team", headers=headers),
                    self._get_clickup_spaces(client, headers, team_id),
                )
                teams_resp.raise_for_status()
                team_name = next(
                    (str(t.get("name") or "Unnamed team") for t in teams_resp.json().get("teams", []) if str(t.get("id")) == team_id),
                    "Unnamed team",
                )

                lists = await self._fetch_team_lists(client, headers, team_name, spaces)
                logger.info("ClickUp team '%s' lists discovery: %d lists", team_name, len(lists))
                return ClickUpDiscoveryResponse(teams=[], lists=lists)
        except httpx.HTTPStatusError as error:
            body = error.response.text
            raise ExternalServiceError(f"ClickUp lists discovery failed: {error} - {body}") from error
        except httpx.HTTPError as error:
            raise ExternalServiceError(f"ClickUp lists discovery failed: {error}") from error

    async def _fetch_team_lists(
        self,
        client: httpx.AsyncClient,
        headers: dict[str, str],
        team_name: str,
        spaces: list[dict[str, Any]],
    ) -> list[ClickUpList]:
        """Fetch all lists for a set of spaces using three parallel rounds."""
        # Round 1: for each space fetch direct lists + folders concurrently.
        space_coros = []
        space_meta: list[tuple[str, str, str]] = []  # (space_id, space_name, task)
        for space in spaces:
            space_id = str(space.get("id"))
            space_name = str(space.get("name") or "Unnamed space")
            space_coros.append(self._get_clickup_lists(client, headers, f"space/{space_id}"))
            space_coros.append(self._get_clickup_folders(client, headers, space_id))
            space_meta.append((space_id, space_name, "lists"))
            space_meta.append((space_id, space_name, "folders"))

        results = await asyncio.gather(*space_coros)

        lists: list[ClickUpList] = []
        folder_coros = []
        folder_meta: list[tuple[str, str, str]] = []  # (space_name, folder_id, folder_name)
        for (_, space_name, task), result in zip(space_meta, results):
            if task == "lists":
                for item in result:
                    lists.append(ClickUpList(
                        id=str(item.get("id")),
                        name=f"{team_name} > {space_name} > {item.get('name')}",
                    ))
            else:
                for folder in result:
                    folder_id = str(folder.get("id"))
                    folder_name = str(folder.get("name") or "Unnamed folder")
                    folder_meta.append((space_name, folder_id, folder_name))
                    folder_coros.append(self._get_clickup_lists(client, headers, f"folder/{folder_id}"))

        # Round 2: fetch all folder lists concurrently.
        if folder_coros:
            folder_results = await asyncio.gather(*folder_coros)
            for (space_name, _fid, folder_name), folder_lists in zip(folder_meta, folder_results):
                for item in folder_lists:
                    lists.append(ClickUpList(
                        id=str(item.get("id")),
                        name=f"{team_name} > {space_name} > {folder_name} > {item.get('name')}",
                    ))

        return lists

    async def discover_clickup(self, api_key: str) -> ClickUpDiscoveryResponse:
        """List all ClickUp teams and lists (all teams, all spaces, parallel fetch).

        Parameters:
            api_key: ClickUp API key.

        Returns:
            ClickUp teams and all lists.
        """
        headers = {"Authorization": api_key}
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                teams_response = await client.get("https://api.clickup.com/api/v2/team", headers=headers)
                teams_response.raise_for_status()
                raw_teams = teams_response.json().get("teams", [])
                teams = [ClickUpTeam(id=str(t.get("id")), name=str(t.get("name") or "Unnamed team")) for t in raw_teams]

                spaces_per_team = await asyncio.gather(
                    *[self._get_clickup_spaces(client, headers, str(t.get("id"))) for t in raw_teams]
                )

                all_lists: list[ClickUpList] = []
                for team, spaces in zip(raw_teams, spaces_per_team):
                    team_name = str(team.get("name") or "Unnamed team")
                    team_lists = await self._fetch_team_lists(client, headers, team_name, spaces)
                    all_lists.extend(team_lists)

                logger.info("ClickUp discovery complete: %d teams, %d lists", len(teams), len(all_lists))
                return ClickUpDiscoveryResponse(teams=teams, lists=all_lists)
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

    async def discover_clickup_list_fields(self, api_key: str, list_id: str) -> ClickUpListFieldsResponse:
        """Return custom fields configured on a specific ClickUp list.

        Parameters:
            api_key: ClickUp API key.
            list_id: ClickUp list identifier.

        Returns:
            List fields response.

        Edge cases:
            Lists with no custom fields return an empty fields array.
        """
        headers = {"Authorization": api_key}
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                response = await client.get(
                    f"https://api.clickup.com/api/v2/list/{list_id}/field",
                    headers=headers,
                )
                response.raise_for_status()
                data = response.json()
                fields = [
                    ClickUpCustomField(
                        id=str(f.get("id", "")),
                        name=str(f.get("name", "")),
                        type_=str(f.get("type", "")),
                    )
                    for f in data.get("fields", [])
                    if f.get("id") and f.get("name")
                ]
                return ClickUpListFieldsResponse(fields=fields)
        except httpx.HTTPStatusError as error:
            body = error.response.text
            logger.error("ClickUp list fields discovery failed: %s - body: %s", error, body)
            raise ExternalServiceError(f"ClickUp list fields discovery failed: {error} - {body}") from error
        except httpx.HTTPError as error:
            logger.error("ClickUp list fields discovery failed: %s", error)
            raise ExternalServiceError(f"ClickUp list fields discovery failed: {error}") from error

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
