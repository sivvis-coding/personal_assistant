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

export interface ClickUpTeamsResponse {
  teams: ClickUpTeam[];
}

export interface ClickUpCustomField {
  id: string;
  name: string;
  type_: string;
}

export interface ClickUpListFieldsResponse {
  fields: ClickUpCustomField[];
}

export interface ClickUpFieldSuggestion {
  field_id: string;
  description: string;
}

export interface ClickUpSuggestResponse {
  routing_description: string;
  field_descriptions: ClickUpFieldSuggestion[];
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
