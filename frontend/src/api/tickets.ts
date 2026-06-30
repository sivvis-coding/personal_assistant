import { apiRequest } from './client';
import type { DraftReplyWorkflowResponse, SummaryWorkflowResponse, UserStory } from '../types/ai';
import type { CreateClickUpTaskWorkflowResponse, PrepareClickUpTaskWorkflowResponse } from '../types/clickup';
import type { TicketConversationsResponse, TicketDetailResponse, TicketListResponse } from '../types/ticket';

export type TicketListScope = 'mine' | 'all';

/**
 * Purpose: Load tickets from backend.
 * Parameters: scope controls whether assigned tickets or all tickets are loaded.
 * Return value: Promise with ticket list response.
 * Edge cases: Backend may return mock tickets when Fresh credentials are absent.
 */
export interface ListTicketsOptions {
  scope?: TicketListScope;
  includeClosed?: boolean;
}

export function listTickets(options: ListTicketsOptions = {}): Promise<TicketListResponse> {
  const params = new URLSearchParams();
  params.set('scope', options.scope ?? 'mine');
  params.set('include_closed', String(options.includeClosed ?? false));
  return apiRequest<TicketListResponse>(`/tickets?${params.toString()}`);
}

/**
 * Purpose: Load one ticket detail from backend.
 * Parameters: ticketId identifies the Fresh ticket.
 * Return value: Promise with ticket detail response.
 * Edge cases: Backend may return cached or mock ticket data.
 */
export function getTicket(ticketId: string): Promise<TicketDetailResponse> {
  return apiRequest<TicketDetailResponse>(`/tickets/${ticketId}`);
}

/**
 * Purpose: Trigger summary workflow for a ticket.
 * Parameters: ticketId identifies the Fresh ticket.
 * Return value: Promise with persisted summary result.
 * Edge cases: OpenAI mock output is used when API key is absent.
 */
export function summarizeTicket(ticketId: string): Promise<SummaryWorkflowResponse> {
  return apiRequest<SummaryWorkflowResponse>(`/tickets/${ticketId}/summarize`, { method: 'POST' });
}

/**
 * Purpose: Trigger reply draft workflow for a ticket.
 * Parameters: ticketId identifies the Fresh ticket.
 * Return value: Promise with persisted draft reply result.
 * Edge cases: Reply is generated but never sent automatically.
 */
export function draftTicketReply(ticketId: string): Promise<DraftReplyWorkflowResponse> {
  return apiRequest<DraftReplyWorkflowResponse>(`/tickets/${ticketId}/draft-reply`, { method: 'POST' });
}

/**
 * Purpose: Trigger ClickUp task review preparation workflow.
 * Parameters: ticketId identifies the Fresh ticket.
 * Return value: Promise with generated user story and draft ID.
 * Edge cases: This call never creates a real ClickUp task.
 */
export function prepareClickUpTask(ticketId: string): Promise<PrepareClickUpTaskWorkflowResponse> {
  return apiRequest<PrepareClickUpTaskWorkflowResponse>(`/tickets/${ticketId}/prepare-clickup-task`, { method: 'POST' });
}

/**
 * Purpose: Load conversation thread for a ticket.
 * Parameters: ticketId identifies the Fresh ticket.
 * Return value: Promise with ticket conversations response.
 * Edge cases: Returns error=true with empty items when Fresh fails.
 */
export function getTicketConversations(ticketId: string): Promise<TicketConversationsResponse> {
  return apiRequest<TicketConversationsResponse>(`/tickets/${ticketId}/conversations`);
}

/**
 * Purpose: Approve and create a ClickUp task from a reviewed user story.
 * Parameters: ticketId identifies the Fresh ticket, userStory is the approved content.
 * Return value: Promise with task creation result.
 * Edge cases: Backend returns existing task link when one already exists.
 */
export function approveClickUpTask(ticketId: string, userStory: UserStory): Promise<CreateClickUpTaskWorkflowResponse> {
  return apiRequest<CreateClickUpTaskWorkflowResponse>(`/tickets/${ticketId}/approve-clickup-task`, {
    method: 'POST',
    body: JSON.stringify({ user_story: userStory }),
  });
}
