import { apiRequest } from './client';
import type { LinkedTaskItem } from '../types/links';

export async function getLinkedTasks(): Promise<LinkedTaskItem[]> {
  return apiRequest<LinkedTaskItem[]>('/integration-links');
}

export async function closeLinkedTicket(ticketId: string, replyBody: string): Promise<void> {
  await apiRequest<{ ticket_id: string; success: boolean }>(`/integration-links/${ticketId}/close`, {
    method: 'POST',
    body: JSON.stringify({ reply_body: replyBody }),
  });
}
