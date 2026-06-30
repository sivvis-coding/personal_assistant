/**
 * Represent editable application integration settings.
 */
export interface AppSettings {
  fresh_base_url: string;
  fresh_api_key: string;
  fresh_assigned_agent_id: string;
  fresh_assigned_agent_field: string;
  fresh_workspace_id: string;
  clickup_api_key: string;
  clickup_team_id: string;
  clickup_list_id: string;
  openai_api_key: string;
  openai_model: string;
}
