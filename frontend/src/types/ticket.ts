export type TicketStatus =
  | 'open'
  | 'pending'
  | 'resolved'
  | 'closed'
  | 'waiting on customer'
  | 'waiting on third party'
  | 'unknown';

export type TicketPriority = 'low' | 'medium' | 'high' | 'urgent' | 'unknown';

export type SlaStatus = 'ok' | 'at_risk' | 'breached' | 'none';

export type ConversationKind = 'customer_reply' | 'agent_reply' | 'private_note';

export interface SlaHint {
  status: SlaStatus;
  due_at?: string | null;
  minutes_remaining?: number | null;
}

export interface TicketRequester {
  name: string;
  email?: string | null;
}

export interface Ticket {
  id: string;
  subject: string;
  status: TicketStatus;
  priority: TicketPriority;
  requester: TicketRequester;
  description?: string | null;
  url?: string | null;
  raw: Record<string, unknown>;
  sla?: SlaHint | null;
  overdue?: boolean;
}

export interface TicketListResponse {
  items: Ticket[];
  source: string;
  cached: boolean;
}

export interface TicketDetailResponse {
  ticket: Ticket;
  source: string;
}

export interface TicketConversation {
  id: string;
  kind: ConversationKind;
  body_text?: string | null;
  body_html?: string | null;
  from_email?: string | null;
  incoming: boolean;
  private: boolean;
  created_at?: string | null;
  raw: Record<string, unknown>;
}

export interface TicketConversationsResponse {
  items: TicketConversation[];
  source: string;
  error: boolean;
}
