export type WorkflowState = 'idle' | 'loading' | 'success' | 'error';

export type WorkflowRunStatus = 'running' | 'success' | 'failed';

export interface WorkflowRunItem {
  id: string;
  workflow_name: string;
  fresh_ticket_id?: string | null;
  status: WorkflowRunStatus;
  input: Record<string, unknown>;
  output?: Record<string, unknown> | null;
  error?: string | null;
  started_at: string;
  finished_at?: string | null;
  created_at: string;
  updated_at: string;
  source: string;
}

export interface WorkflowRunListResponse {
  items: WorkflowRunItem[];
  limit: number;
}
