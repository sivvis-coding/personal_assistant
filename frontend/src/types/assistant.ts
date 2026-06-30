export type TicketRecommendationCategory = 'action_now' | 'backlog_candidate' | 'needs_more_info' | 'ignore_or_monitor' | 'already_in_backlog';
export type AssistantActionType = 'prepare_clickup_task' | 'approve_clickup_task' | 'save_time_entry' | 'reply_freshservice_ticket';
export type AssistantActionStatus = 'proposed' | 'approved' | 'rejected' | 'completed' | 'failed';

export interface TicketRecommendation {
  ticket_id: string;
  subject: string;
  category: TicketRecommendationCategory;
  confidence: number;
  rationale: string;
  suggested_next_action: string;
  missing_information: string[];
}

export interface PrioritizedWorkPlan {
  today_focus: TicketRecommendation[];
  next_actions: TicketRecommendation[];
  backlog_candidates: TicketRecommendation[];
  blocked_items: TicketRecommendation[];
  not_worth_actioning: TicketRecommendation[];
}

export interface AssistantAction {
  id: string;
  action_type: AssistantActionType;
  status: AssistantActionStatus;
  title: string;
  description: string;
  ticket_id?: string | null;
  payload: Record<string, unknown>;
  result?: Record<string, unknown> | null;
  requires_approval: boolean;
}

export interface AssistantConversationCreateResponse {
  conversation_id: string;
}

export interface AssistantMessageResponse {
  conversation_id: string;
  answer: string;
  recommendations: TicketRecommendation[];
  work_plan: PrioritizedWorkPlan;
  proposed_actions: AssistantAction[];
  needs_clarification: boolean;
  clarification_question: string;
}

export interface TimeEntryPreview {
  task_name: string;
  description: string;
  start_datetime: string;
  end_datetime: string;
  client_name: string;
  duration_minutes: number;
}

export interface TimeTrackingProcessResponse {
  success: boolean;
  answer: string;
  preview?: TimeEntryPreview | null;
  proposed_action?: AssistantAction | null;
}

export interface ConversationMessage {
  user_message: string;
  assistant_answer: string;
  created_at: string;
}

export interface ConversationSummaryResponse {
  id: string;
  title: string;
  message_count: number;
  updated_at: string;
}

export interface ConversationDetailResponse {
  id: string;
  title: string;
  messages: ConversationMessage[];
  created_at: string;
  updated_at: string;
}
