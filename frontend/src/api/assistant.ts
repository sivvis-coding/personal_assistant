import { apiRequest } from './client';
import type {
  AssistantAction,
  AssistantConversationCreateResponse,
  AssistantMessageResponse,
  ConversationDetailResponse,
  ConversationSummaryResponse,
  TimeTrackingProcessResponse,
} from '../types/assistant';

/**
 * Create an assistant conversation.
 *
 * Parameters:
 *   None.
 *
 * Returns:
 *   Created conversation response.
 *
 * Edge cases:
 *   Backend authentication can reject the request when local key is required.
 */
export function createAssistantConversation(): Promise<AssistantConversationCreateResponse> {
  return apiRequest<AssistantConversationCreateResponse>('/assistant/conversations', { method: 'POST' });
}

/**
 * List all conversation summaries ordered by most recent.
 *
 * Parameters:
 *   None.
 *
 * Returns:
 *   List of conversation summaries.
 *
 * Edge cases:
 *   Empty response when no conversations exist.
 */
export function listAssistantConversations(): Promise<ConversationSummaryResponse[]> {
  return apiRequest<ConversationSummaryResponse[]>('/assistant/conversations');
}

/**
 * Get a complete conversation with all messages.
 *
 * Parameters:
 *   conversationId: Conversation identifier.
 *
 * Returns:
 *   Complete conversation with messages.
 *
 * Edge cases:
 *   404 when conversation does not exist.
 */
export function getAssistantConversation(conversationId: string): Promise<ConversationDetailResponse> {
  return apiRequest<ConversationDetailResponse>(`/assistant/conversations/${conversationId}`);
}

/**
 * Send a message to the assistant.
 *
 * Parameters:
 *   conversationId: Existing assistant conversation ID.
 *   message: User message text.
 *
 * Returns:
 *   Assistant response with work plan and actions.
 *
 * Edge cases:
 *   Empty messages are rejected by the backend schema.
 */
export function sendAssistantMessage(conversationId: string, message: string): Promise<AssistantMessageResponse> {
  return apiRequest<AssistantMessageResponse>(`/assistant/conversations/${conversationId}/messages`, {
    method: 'POST',
    body: JSON.stringify({ message }),
  });
}

/**
 * Load assistant actions waiting for approval.
 *
 * Parameters:
 *   None.
 *
 * Returns:
 *   Pending assistant actions.
 *
 * Edge cases:
 *   Empty response means no review is needed.
 */
export function listPendingAssistantActions(): Promise<AssistantAction[]> {
  return apiRequest<AssistantAction[]>('/assistant/actions/pending');
}

/**
 * Update the payload of a pending action before approval.
 *
 * Parameters:
 *   actionId: Assistant action ID.
 *   payload: New payload values to persist.
 *
 * Returns:
 *   Updated assistant action.
 *
 * Edge cases:
 *   Only proposed actions can be updated; completed/rejected return 400.
 */
export function updateAssistantActionPayload(actionId: string, payload: Record<string, unknown>): Promise<AssistantAction> {
  return apiRequest<AssistantAction>(`/assistant/actions/${actionId}`, {
    method: 'PATCH',
    body: JSON.stringify({ payload }),
  });
}

/**
 * Approve one assistant action.
 *
 * Parameters:
 *   actionId: Assistant action ID.
 *
 * Returns:
 *   Updated assistant action.
 *
 * Edge cases:
 *   Preparing backlog creates a second approval action before external task creation.
 */
export function approveAssistantAction(actionId: string): Promise<AssistantAction> {
  return apiRequest<AssistantAction>(`/assistant/actions/${actionId}/approve`, { method: 'POST' });
}

/**
 * Reject one assistant action.
 *
 * Parameters:
 *   actionId: Assistant action ID.
 *
 * Returns:
 *   Updated assistant action.
 *
 * Edge cases:
 *   Completed actions cannot be undone by rejection.
 */
export function rejectAssistantAction(actionId: string): Promise<AssistantAction> {
  return apiRequest<AssistantAction>(`/assistant/actions/${actionId}/reject`, { method: 'POST' });
}

/**
 * Process a natural language time tracking request.
 *
 * Parameters:
 *   message: User message text.
 *
 * Returns:
 *   Time tracking processing result with optional preview and pending action.
 *
 * Edge cases:
 *   Success=false means the agent needs more information before creating a pending action.
 */
export function processTimeTrackingRequest(message: string): Promise<TimeTrackingProcessResponse> {
  return apiRequest<TimeTrackingProcessResponse>('/assistant/time-tracking/process', {
    method: 'POST',
    body: JSON.stringify({ message }),
  });
}
