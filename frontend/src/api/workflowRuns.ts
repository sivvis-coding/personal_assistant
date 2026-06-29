import { apiRequest } from './client';
import type { WorkflowRunListResponse } from '../types/workflow';

/**
 * Purpose: Load workflow run history from backend.
 * Parameters: limit caps returned records, freshTicketId optionally filters by ticket.
 * Return value: Promise with workflow run history.
 * Edge cases: Empty history returns an empty items array.
 */
export function listWorkflowRuns(limit = 50, freshTicketId?: string): Promise<WorkflowRunListResponse> {
  const params = new URLSearchParams({ limit: String(limit) });
  if (freshTicketId) {
    params.set('fresh_ticket_id', freshTicketId);
  }
  return apiRequest<WorkflowRunListResponse>(`/workflow-runs?${params.toString()}`);
}
