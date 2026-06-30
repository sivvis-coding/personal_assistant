from pydantic import BaseModel


class ClickUpCustomField(BaseModel):
    """Represent a ClickUp custom field returned by the discovery API.

    Parameters:
        id: Field UUID.
        name: Field display name.
        type_: Field type (text, number, dropdown, etc.).
    """

    id: str
    name: str
    type_: str = ""


class ClickUpListFieldsResponse(BaseModel):
    """Contain discovered custom fields for a ClickUp list.

    Parameters:
        fields: Custom fields defined on the list.
    """

    fields: list[ClickUpCustomField]


class ClickUpTeam(BaseModel):
    """Represent a ClickUp team/workspace.

    Parameters:
        id: Team identifier.
        name: Team display name.

    Returns:
        ClickUp team value object.
    """

    id: str
    name: str


class ClickUpList(BaseModel):
    """Represent a ClickUp task list.

    Parameters:
        id: List identifier.
        name: List display name.

    Returns:
        ClickUp list value object.
    """

    id: str
    name: str


class ClickUpDiscoveryResponse(BaseModel):
    """Represent ClickUp discoverable resources.

    Parameters:
        teams: Available teams/workspaces.
        lists: Available task lists (may require a selected team).

    Returns:
        ClickUp discovery response.
    """

    teams: list[ClickUpTeam]
    lists: list[ClickUpList]


class FreshserviceAgent(BaseModel):
    """Represent a Freshservice agent/user.

    Parameters:
        id: Agent identifier.
        name: Agent display name.
        email: Agent email.

    Returns:
        Freshservice agent value object.
    """

    id: str
    name: str
    email: str | None = None


class FreshserviceWorkspace(BaseModel):
    """Represent a Freshservice workspace.

    Parameters:
        id: Workspace identifier.
        name: Workspace display name.

    Returns:
        Freshservice workspace value object.
    """

    id: str
    name: str


class FreshserviceDiscoveryResponse(BaseModel):
    """Represent Freshservice discoverable resources.

    Parameters:
        agents: Available agents for assignment filtering.

    Returns:
        Freshservice discovery response.
    """

    agents: list[FreshserviceAgent]


class FreshserviceWorkspacesResponse(BaseModel):
    """Represent Freshservice workspace discovery response.

    Parameters:
        workspaces: Available workspaces.

    Returns:
        Freshservice workspaces discovery response.
    """

    workspaces: list[FreshserviceWorkspace]
