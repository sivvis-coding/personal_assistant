export interface ClickUpTeam {
  id: string;
  name: string;
}

export interface ClickUpList {
  id: string;
  name: string;
}

export interface ClickUpDiscoveryResponse {
  teams: ClickUpTeam[];
  lists: ClickUpList[];
}

export interface FreshserviceAgent {
  id: string;
  name: string;
  email?: string | null;
}

export interface FreshserviceWorkspace {
  id: string;
  name: string;
}

export interface FreshserviceDiscoveryResponse {
  agents: FreshserviceAgent[];
}

export interface FreshserviceWorkspacesResponse {
  workspaces: FreshserviceWorkspace[];
}
