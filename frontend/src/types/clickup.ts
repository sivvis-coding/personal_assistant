import type { UserStory } from './ai';

export interface ClickUpTaskResult {
  id: string;
  url?: string | null;
  source: string;
}

export interface CreateClickUpTaskWorkflowResponse {
  ticket_id: string;
  user_story: UserStory;
  clickup_task: ClickUpTaskResult;
  integration_link_id: string;
  workflow_run_id: string;
}

export interface PrepareClickUpTaskWorkflowResponse {
  ticket_id: string;
  user_story: UserStory;
  draft_id: string;
  workflow_run_id: string;
  requires_approval: boolean;
}

export interface TimeEntry {
  task_id: string;
  task_name: string;
  hours: number;
  date: string;
}

export interface WeekTimeResponse {
  source: string;
  week_start: string;
  week_end: string;
  total_hours: number;
  entries: TimeEntry[];
}
