export interface ClickUpCustomFieldConfig {
  field_id: string;
  field_name: string;
  description: string;
}

export interface ClickUpListConfig {
  id: string;
  name: string;
  description: string;
  custom_fields: ClickUpCustomFieldConfig[];
}

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
  clickup_lists: ClickUpListConfig[];
  agent_system_prompt: string;
  openai_api_key: string;
  openai_model: string;
}
