// Types mirroring backend app/schemas/insights.py (snake_case, matching the API JSON).

export interface TicketSignature {
  problem: string;
  category: string;
  root_cause: string;
  resolution: string;
  product_area: string;
  tags: string[];
}

export interface TicketRef {
  workspace_id: string;
  ticket_id: string;
  subject: string;
}

export interface ArchivedTicket {
  workspace_id: string;
  ticket_id: string;
  subject: string;
  status: string;
  priority: string;
  created_at_fresh: string | null;
  updated_at_fresh: string | null;
  signature: TicketSignature | null;
}

export interface ArchivedTicketsResponse {
  items: ArchivedTicket[];
  total: number;
  skip: number;
  limit: number;
}

export interface WorkspaceHarvestStatus {
  workspace_id: string;
  name: string;
  backfill_done: boolean;
  backfill_since: string | null;
  last_incremental_at: string | null;
  in_progress: boolean;
  fetched: number;
  upserted: number;
  convos: number;
  archived_count: number;
  last_error: string | null;
}

export interface HarvestStatus {
  workspaces: WorkspaceHarvestStatus[];
  total_archived: number;
}

export interface KnowledgeTheme {
  title: string;
  summary: string;
  symptoms: string;
  root_causes: string;
  resolution_steps: string;
  frequency: number;
  workspaces: string[];
  ticket_refs: TicketRef[];
}

export interface RecurringIssue {
  label: string;
  count: number;
  ticket_refs: TicketRef[];
}

export interface CategoryMetric {
  category: string;
  volume: number;
  avg_resolution_hours: number | null;
  reopen_rate: number | null;
}

export interface Bottleneck {
  title: string;
  description: string;
  severity: string;
  category: string;
  ticket_refs: TicketRef[];
}

export interface AutomationOpportunity {
  title: string;
  description: string;
  rationale: string;
  category: string;
  ticket_refs: TicketRef[];
}

export interface DepartmentKnowledge {
  workspace_id: string;
  name: string;
  total_tickets: number;
  themes: KnowledgeTheme[];
  recurring: RecurringIssue[];
  bottlenecks: Bottleneck[];
  automation: AutomationOpportunity[];
  metrics: CategoryMetric[];
}

export interface KnowledgeResponse {
  departments: DepartmentKnowledge[];
  model: string;
  generated_at: string | null;
  persisted: boolean;
}

export interface WorkspaceOption {
  workspace_id: string;
  name: string;
}

export interface WorkspacesResponse {
  available: WorkspaceOption[];
  configured: WorkspaceOption[];
}
