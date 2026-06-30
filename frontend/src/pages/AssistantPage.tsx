import { useEffect, useRef, useState } from 'react';
import { approveAssistantAction, createAssistantConversation, listPendingAssistantActions, rejectAssistantAction, sendAssistantMessage } from '../api/assistant';
import { AssistantActionCard } from '../components/AssistantActionCard';
import { ErrorState } from '../components/ErrorState';
import { LoadingState } from '../components/LoadingState';
import type { AssistantAction, AssistantMessageResponse } from '../types/assistant';

interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  text: string;
  actions: AssistantAction[];
  timestamp: Date;
}

/**
 * Create a stable identifier for chat messages.
 *
 * Parameters:
 *   prefix: Identifier prefix.
 *   index: Message index.
 *
 * Returns:
 *   Unique string key.
 *
 * Edge cases:
 *   Index collisions are avoided by combining prefix and index.
 */
function messageId(prefix: string, index: number): string {
  return `${prefix}-${index}-${Date.now()}`;
}

/**
 * Render conversational assistant page with inline HITL actions.
 *
 * Parameters:
 *   None.
 *
 * Returns:
 *   JSX assistant page.
 *
 * Edge cases:
 *   Conversation is created lazily on initial page load.
 */
export function AssistantPage() {
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [pendingActions, setPendingActions] = useState<AssistantAction[]>([]);
  const [awaitingClientConfirmation, setAwaitingClientConfirmation] = useState(false);
  const [candidateClients, setCandidateClients] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    Promise.all([createAssistantConversation(), listPendingAssistantActions()])
      .then(([conversation, actions]) => {
        setConversationId(conversation.conversation_id);
        setPendingActions(actions);
      })
      .catch((caught: Error) => setError(caught.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, pendingActions]);

  /**
   * Purpose: Send a chat message to the assistant.
   * Parameters: userText is the message to send.
   * Return value: None.
   * Edge cases: Missing conversation ID blocks submission until initialization finishes.
   */
  async function submitMessage(userText: string = input.trim()): Promise<void> {
    if (!conversationId || !userText) return;

    setInput('');
    setSubmitting(true);
    setError(null);
    setAwaitingClientConfirmation(false);
    setCandidateClients([]);

    const userMessage: ChatMessage = {
      id: messageId('user', messages.length),
      role: 'user',
      text: userText,
      actions: [],
      timestamp: new Date(),
    };
    setMessages((current) => [...current, userMessage]);

    try {
      const response = await sendAssistantMessage(conversationId, userText);
      const assistantMessage: ChatMessage = {
        id: messageId('assistant', messages.length + 1),
        role: 'assistant',
        text: response.answer,
        actions: response.proposed_actions,
        timestamp: new Date(),
      };
      setMessages((current) => [...current, assistantMessage]);
      if (response.needs_clarification) {
        setAwaitingClientConfirmation(true);
        setCandidateClients([]);
      }
      const actions = await listPendingAssistantActions();
      setPendingActions(actions);
    } catch (caught) {
      setError((caught as Error).message);
      const errorMessage: ChatMessage = {
        id: messageId('error', messages.length + 1),
        role: 'assistant',
        text: `Error: ${(caught as Error).message}`,
        actions: [],
        timestamp: new Date(),
      };
      setMessages((current) => [...current, errorMessage]);
    } finally {
      setSubmitting(false);
    }
  }

  /**
   * Purpose: Confirm a client candidate during a clarification turn.
   * Parameters: clientName is the selected client name.
   * Return value: None.
   * Edge cases: Empty candidate names are ignored.
   */
  function handleCandidateClick(clientName: string): void {
    if (!clientName.trim() || submitting) return;
    void submitMessage(clientName.trim());
  }

  /**
   * Purpose: Approve a proposed assistant action and refresh state.
   * Parameters: actionId identifies the assistant action.
   * Return value: None.
   * Edge cases: Prepare actions may add a new pending final-approval action.
   */
  async function approveAction(actionId: string): Promise<void> {
    setSubmitting(true);
    setError(null);
    try {
      const updated = await approveAssistantAction(actionId);
      refreshActionInMessages(actionId, updated);
      setPendingActions(await listPendingAssistantActions());
    } catch (caught) {
      setError((caught as Error).message);
    } finally {
      setSubmitting(false);
    }
  }

  /**
   * Purpose: Reject a proposed assistant action and refresh state.
   * Parameters: actionId identifies the assistant action.
   * Return value: None.
   * Edge cases: Rejection does not undo completed external operations.
   */
  async function rejectAction(actionId: string): Promise<void> {
    setSubmitting(true);
    setError(null);
    try {
      const updated = await rejectAssistantAction(actionId);
      refreshActionInMessages(actionId, updated);
      setPendingActions(await listPendingAssistantActions());
    } catch (caught) {
      setError((caught as Error).message);
    } finally {
      setSubmitting(false);
    }
  }

  /**
   * Purpose: Update an action's state inside the chat history after approval/rejection.
   * Parameters: actionId is the original ID, updated is the server response.
   * Return value: None.
   * Edge cases: If the action is not found in chat history, pending list refresh still updates the UI.
   */
  function refreshActionInMessages(actionId: string, updated: AssistantAction): void {
    setMessages((current) =>
      current.map((message) => ({
        ...message,
        actions: message.actions.map((action) => (action.id === actionId ? updated : action)),
      }))
    );
  }

  if (loading) return <LoadingState message="Loading assistant..." />;
  if (error && messages.length === 0) return <ErrorState message={error} />;

  return (
    <section className="assistant-page">
      <div className="panel assistant-chat">
        <h2>Agente asistente</h2>
        <div className="chat-messages">
          {messages.length === 0 ? (
            <p className="chat-empty">Escribe un mensaje para empezar. Prueba: "Imputa 2h hoy a las 09:00 al cliente Acme por revisión"</p>
          ) : null}
          {messages.map((message) => (
            <div key={message.id} className={`chat-message ${message.role}`}>
              <div className="chat-bubble">
                <p className="chat-text">{message.text}</p>
                {message.actions.length > 0 ? (
                  <div className="chat-actions">
                    <p className="chat-actions-title">Acciones pendientes de revisión:</p>
                    {message.actions.map((action) => (
                      <AssistantActionCard
                        key={action.id}
                        action={action}
                        disabled={submitting}
                        onApprove={approveAction}
                        onReject={rejectAction}
                      />
                    ))}
                  </div>
                ) : null}
              </div>
              <time className="chat-time" dateTime={message.timestamp.toISOString()}>
                {message.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
              </time>
            </div>
          ))}
          {submitting ? (
            <div className="chat-message assistant">
              <div className="chat-bubble loading">
                <span className="typing-indicator">Pensando...</span>
              </div>
            </div>
          ) : null}
          <div ref={messagesEndRef} />
        </div>
        {awaitingClientConfirmation ? (
          <div className="client-clarification">
            <p className="clarification-title">Elige el cliente o escríbelo:</p>
            {candidateClients.length > 0 ? (
              <div className="candidate-buttons">
                {candidateClients.map((client) => (
                  <button
                    key={client}
                    disabled={submitting}
                    type="button"
                    onClick={() => handleCandidateClick(client)}
                  >
                    {client}
                  </button>
                ))}
              </div>
            ) : null}
          </div>
        ) : null}
        <div className="chat-input-bar">
          <input
            className="chat-input"
            disabled={submitting}
            placeholder={awaitingClientConfirmation ? "Escribe el nombre del cliente..." : "Escribe tu solicitud..."}
            type="text"
            value={input}
            onChange={(event) => setInput(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter' && !event.shiftKey) {
                event.preventDefault();
                void submitMessage();
              }
            }}
          />
          <button disabled={submitting || !input.trim()} type="button" onClick={() => void submitMessage()}>
            Enviar
          </button>
        </div>
        {error ? <p className="warning">{error}</p> : null}
      </div>
      <aside className="panel assistant-actions-panel">
        <h2>Acciones pendientes</h2>
        {pendingActions.length === 0 ? <p>No hay acciones pendientes.</p> : null}
        {pendingActions.map((action) => (
          <AssistantActionCard
            key={action.id}
            action={action}
            disabled={submitting}
            onApprove={approveAction}
            onReject={rejectAction}
          />
        ))}
      </aside>
    </section>
  );
}
