import { create } from 'zustand';
import type { AssistantAction } from '../types/assistant';

/**
 * Represent a single chat message.
 */
export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'error';
  text: string;
  actions: AssistantAction[];
  timestamp: Date;
}

/**
 * Represent a stored conversation for the history list.
 */
export interface ConversationSummary {
  id: string;
  title: string;
  lastMessage: string;
  messageCount: number;
  updatedAt: Date;
}

interface ChatState {
  conversationId: string | null;
  messages: ChatMessage[];
  pendingActions: AssistantAction[];
  awaitingClientConfirmation: boolean;
  candidateClients: string[];
  isLoading: boolean;
  isSubmitting: boolean;
  error: string | null;
  conversations: ConversationSummary[];
  selectedConversationId: string | null;
}

interface ChatActions {
  setConversationId: (id: string | null) => void;
  addMessage: (message: ChatMessage) => void;
  updateMessage: (id: string, updates: Partial<ChatMessage>) => void;
  setMessages: (messages: ChatMessage[]) => void;
  setPendingActions: (actions: AssistantAction[]) => void;
  updatePendingAction: (action: AssistantAction) => void;
  setAwaitingClientConfirmation: (value: boolean, clients?: string[]) => void;
  setLoading: (value: boolean) => void;
  setSubmitting: (value: boolean) => void;
  setError: (error: string | null) => void;
  setConversations: (conversations: ConversationSummary[] | ((current: ConversationSummary[]) => ConversationSummary[])) => void;
  selectConversation: (id: string | null) => void;
  resetChat: () => void;
}

/**
 * Global chat state managed by Zustand.
 *
 * Parameters:
 *   None.
 *
 * Returns:
 *   Hook returning chat state and actions.
 *
 * Edge cases:
 *   resetChat clears the active conversation but keeps the history list.
 */
export const useChatStore = create<ChatState & ChatActions>((set) => ({
  conversationId: null,
  messages: [],
  pendingActions: [],
  awaitingClientConfirmation: false,
  candidateClients: [],
  isLoading: false,
  isSubmitting: false,
  error: null,
  conversations: [],
  selectedConversationId: null,

  setConversationId: (id) => set({ conversationId: id }),
  addMessage: (message) => set((state) => ({ messages: [...state.messages, message] })),
  updateMessage: (id, updates) =>
    set((state) => ({
      messages: state.messages.map((message) => (message.id === id ? { ...message, ...updates } : message)),
    })),
  setMessages: (messages) => set({ messages }),
  setPendingActions: (pendingActions) => set({ pendingActions }),
  updatePendingAction: (action) =>
    set((state) => ({
      pendingActions: state.pendingActions.map((pending) => (pending.id === action.id ? action : pending)),
    })),
  setAwaitingClientConfirmation: (value, clients = []) =>
    set({ awaitingClientConfirmation: value, candidateClients: clients }),
  setLoading: (value) => set({ isLoading: value }),
  setSubmitting: (value) => set({ isSubmitting: value }),
  setError: (error) => set({ error }),
  setConversations: (conversations) =>
    set((state) => ({
      conversations: typeof conversations === 'function' ? conversations(state.conversations) : conversations,
    })),
  selectConversation: (id) => set({ selectedConversationId: id }),
  resetChat: () => {
    window.localStorage.removeItem('ASSISTANT_CONVERSATION_ID');
    set({
      conversationId: null,
      messages: [],
      pendingActions: [],
      awaitingClientConfirmation: false,
      candidateClients: [],
      isSubmitting: false,
      error: null,
      selectedConversationId: null,
    });
  },
}));
