export interface TicketSummary {
  title: string;
  problem: string;
  impact: string;
  suggested_next_steps: string[];
  risks: string[];
}

export interface ReplyDraft {
  subject: string;
  body: string;
  tone: string;
  requires_human_review: boolean;
}

export interface UserStory {
  title: string;
  description: string;
  acceptance_criteria_in_gerkin: string;
  constraints: string;
  user_story_statement: string;
  out_of_scope: string;
  requested_by: string;
  functional_description: string;
}

export interface SummaryWorkflowResponse {
  ticket_id: string;
  type: 'summary';
  summary: TicketSummary;
  draft_id: string;
  workflow_run_id: string;
}

export interface DraftReplyWorkflowResponse {
  ticket_id: string;
  type: 'reply';
  draft: ReplyDraft;
  draft_id: string;
  workflow_run_id: string;
}
