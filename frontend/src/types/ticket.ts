export interface TicketRequester {
  name: string;
  email?: string | null;
}

export interface Ticket {
  id: string;
  subject: string;
  status: string;
  priority: string;
  requester: TicketRequester;
  description?: string | null;
  raw: Record<string, unknown>;
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
