import { apiRequest } from './client';
import type {
  AssistantAction,
  AssistantConversationCreateResponse,
  AssistantMessageResponse,
  ConversationDetailResponse,
  ConversationSummaryResponse,
  TimeTrackingProcessResponse,
} from '../types/assistant';

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';

export interface StreamCallbacks {
  onToken: (text: string) => void;
  onDone: (response: AssistantMessageResponse) => void;
  onError: (message: string) => void;
}

/**
 * Stream an assistant message response via SSE.
 *
 * Calls onToken for each incremental text chunk, onDone when the full structured
 * response arrives, and onError on failure.
 */
export async function streamAssistantMessage(
  conversationId: string,
  message: string,
  callbacks: StreamCallbacks,
): Promise<void> {
  const localKey = window.localStorage.getItem('LOCAL_APP_API_KEY') ?? '';
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (localKey) headers['X-Local-App-Key'] = localKey;

  const response = await fetch(
    `${API_BASE_URL}/assistant/conversations/${conversationId}/messages/stream`,
    { method: 'POST', headers, body: JSON.stringify({ message }) },
  );

  if (!response.ok) {
    const payload = await response.json().catch(() => ({ detail: response.statusText }));
    callbacks.onError(String(payload.detail ?? response.statusText));
    return;
  }

  const reader = response.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });

    // SSE events are separated by \n\n
    const parts = buffer.split('\n\n');
    buffer = parts.pop() ?? '';

    for (const part of parts) {
      const line = part.trim();
      if (!line.startsWith('data: ')) continue;
      try {
        const event = JSON.parse(line.slice(6)) as { type: string; text?: string; data?: AssistantMessageResponse; message?: string };
        if (event.type === 'token' && event.text) {
          callbacks.onToken(event.text);
        } else if (event.type === 'done' && event.data) {
          callbacks.onDone(event.data);
        } else if (event.type === 'error') {
          callbacks.onError(event.message ?? 'Error desconocido');
        }
      } catch {
        // Ignore malformed events
      }
    }
  }
}

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
export function createAssistantConversation(targetDate?: string): Promise<AssistantConversationCreateResponse> {
  return apiRequest<AssistantConversationCreateResponse>('/assistant/conversations', {
    method: 'POST',
    body: JSON.stringify(targetDate ? { target_date: targetDate } : {}),
  });
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
 *   A single approval executes the action (backlog creation reviews the generated
 *   user story on the card and creates the ClickUp task on that one approval).
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

export function deleteAssistantConversation(conversationId: string): Promise<void> {
  return apiRequest<void>(`/assistant/conversations/${conversationId}`, { method: 'DELETE' });
}

export interface CreateActionRequest {
  action_type: string;
  title: string;
  description: string;
  ticket_id?: string;
  payload: Record<string, unknown>;
}

export function createAssistantAction(request: CreateActionRequest): Promise<AssistantAction> {
  return apiRequest<AssistantAction>('/assistant/actions', {
    method: 'POST',
    body: JSON.stringify(request),
  });
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
