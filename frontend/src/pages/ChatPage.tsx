import { useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box,
  Button,
  Chip,
  CircularProgress,
  Divider,
  IconButton,
  Paper,
  TextField,
  Typography,
} from '@mui/material';
import SendIcon from '@mui/icons-material/Send';
import HistoryIcon from '@mui/icons-material/History';
import { useChatStore } from '../stores/chatStore';
import { createAssistantConversation, listPendingAssistantActions, sendAssistantMessage } from '../api/assistant';
import { useActionsStore } from '../stores/actionsStore';

/**
 * Generate a stable message identifier.
 */
function messageId(prefix: string, index: number): string {
  return `${prefix}-${index}-${Date.now()}`;
}

/**
 * Generate a conversation title from the first user message.
 */
function generateTitle(text: string): string {
  const trimmed = text.trim();
  return trimmed.length > 40 ? `${trimmed.slice(0, 40)}...` : trimmed;
}

/**
 * Render the chat page with message history and inline actions.
 *
 * Parameters:
 *   None.
 *
 * Returns:
 *   JSX chat page.
 *
 * Edge cases:
 *   Conversation is created lazily when the user sends the first message.
 */
export function ChatPage() {
  const navigate = useNavigate();
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const {
    conversationId,
    messages,
    isLoading,
    isSubmitting,
    error,
    awaitingClientConfirmation,
    candidateClients,
    setConversationId,
    addMessage,
    setMessages,
    setSubmitting,
    setError,
    setAwaitingClientConfirmation,
    setConversations,
    resetChat,
  } = useChatStore();

  const { setPendingActions } = useActionsStore();

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  useEffect(() => {
    const storedId = window.localStorage.getItem('ASSISTANT_CONVERSATION_ID');
    if (storedId && !conversationId) {
      setConversationId(storedId);
    }
  }, [conversationId, setConversationId]);

  useEffect(() => {
    if (conversationId) {
      window.localStorage.setItem('ASSISTANT_CONVERSATION_ID', conversationId);
    }
  }, [conversationId]);

  useEffect(() => {
    async function loadActions() {
      try {
        const actions = await listPendingAssistantActions();
        setPendingActions(actions);
      } catch (caught) {
        setError((caught as Error).message);
      }
    }
    void loadActions();
  }, [setPendingActions, setError]);

  /**
   * Send a message to the assistant.
   */
  async function submitMessage(text: string): Promise<void> {
    if (!text.trim()) return;

    setSubmitting(true);
    setError(null);
    setAwaitingClientConfirmation(false);

    const userMessage = {
      id: messageId('user', messages.length),
      role: 'user' as const,
      text: text.trim(),
      actions: [],
      timestamp: new Date(),
    };
    addMessage(userMessage);

    try {
      let activeConversationId = conversationId;

      if (!activeConversationId) {
        const conversation = await createAssistantConversation();
        activeConversationId = conversation.conversation_id;
        setConversationId(activeConversationId);
        window.localStorage.setItem('ASSISTANT_CONVERSATION_ID', activeConversationId);
      }

      const response = await sendAssistantMessage(activeConversationId, text.trim());
      const assistantMessage = {
        id: messageId('assistant', messages.length + 1),
        role: 'assistant' as const,
        text: response.answer,
        actions: response.proposed_actions,
        timestamp: new Date(),
      };
      addMessage(assistantMessage);

      if (response.needs_clarification) {
        setAwaitingClientConfirmation(true);
      }

      const actions = await listPendingAssistantActions();
      setPendingActions(actions);

      setConversations((current) => {
        if (current.some((conversation) => conversation.id === activeConversationId)) return current;
        return [
          {
            id: activeConversationId!,
            title: generateTitle(text),
            lastMessage: response.answer,
            messageCount: 2,
            updatedAt: new Date(),
          },
          ...current,
        ];
      });
    } catch (caught) {
      setError((caught as Error).message);
      addMessage({
        id: messageId('error', messages.length + 1),
        role: 'error',
        text: `Error: ${(caught as Error).message}`,
        actions: [],
        timestamp: new Date(),
      });
    } finally {
      setSubmitting(false);
    }
  }

  if (isLoading && messages.length === 0) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '60vh' }}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: 'calc(100vh - 120px)' }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Typography variant="body2" color="text.secondary">
          {conversationId ? `Conversación ${conversationId.slice(-6)}` : 'Nueva conversación'}
        </Typography>
        <Box sx={{ display: 'flex', gap: 1 }}>
          <Button
            variant="outlined"
            size="small"
            onClick={() => resetChat()}
          >
            Nueva conversación
          </Button>
          <Button
            variant="outlined"
            size="small"
            startIcon={<HistoryIcon />}
            onClick={() => navigate('/assistant/history')}
          >
            Historial
          </Button>
        </Box>
      </Box>

      <Paper
        sx={{
          flexGrow: 1,
          overflow: 'auto',
          p: 2,
          mb: 2,
          display: 'flex',
          flexDirection: 'column',
          gap: 2,
        }}
      >
        {messages.length === 0 ? (
          <Box sx={{ textAlign: 'center', mt: 8, color: 'text.secondary' }}>
            <Typography variant="h6" gutterBottom>
              ¿Qué necesitas hacer hoy?
            </Typography>
            <Typography>
              Prueba: "Imputa 2h hoy a las 09:00 al cliente Acme por revisión"
            </Typography>
          </Box>
        ) : null}
        {messages.map((message) => (
          <Box
            key={message.id}
            sx={{
              alignSelf: message.role === 'user' ? 'flex-end' : 'flex-start',
              maxWidth: '80%',
              bgcolor: message.role === 'user' ? 'primary.light' : 'grey.100',
              color: message.role === 'user' ? 'primary.contrastText' : 'text.primary',
              borderRadius: 2,
              p: 2,
            }}
          >
            <Typography variant="body1" sx={{ whiteSpace: 'pre-wrap' }}>
              {message.text}
            </Typography>
            {message.actions.length > 0 ? (
              <Box sx={{ mt: 2 }}>
                <Typography variant="caption" color="text.secondary">
                  Acciones propuestas:
                </Typography>
                {message.actions.map((action) => (
                  <Paper key={action.id} variant="outlined" sx={{ p: 1, mt: 1 }}>
                    <Typography variant="subtitle2">{action.title}</Typography>
                    <Typography variant="body2" color="text.secondary">
                      {action.description}
                    </Typography>
                  </Paper>
                ))}
              </Box>
            ) : null}
            <Typography variant="caption" sx={{ display: 'block', mt: 1, opacity: 0.7 }}>
              {message.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
            </Typography>
          </Box>
        ))}
        {isSubmitting ? (
          <Box sx={{ alignSelf: 'flex-start', bgcolor: 'grey.100', borderRadius: 2, p: 2 }}>
            <CircularProgress size={20} sx={{ mr: 1 }} />
            <Typography variant="body2" component="span">
              Pensando...
            </Typography>
          </Box>
        ) : null}
        <div ref={messagesEndRef} />
      </Paper>

      {awaitingClientConfirmation && candidateClients.length > 0 ? (
        <Box sx={{ mb: 2 }}>
          <Typography variant="body2" color="text.secondary" gutterBottom>
            Elige el cliente:
          </Typography>
          <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
            {candidateClients.map((client) => (
              <Chip
                key={client}
                label={client}
                onClick={() => void submitMessage(client)}
                clickable
                color="primary"
              />
            ))}
          </Box>
        </Box>
      ) : null}

      <Box sx={{ display: 'flex', gap: 1 }}>
        <TextField
          fullWidth
          placeholder={awaitingClientConfirmation ? 'Escribe el nombre del cliente...' : 'Escribe tu solicitud...'}
          disabled={isSubmitting}
          onKeyDown={(event) => {
            if (event.key === 'Enter' && !event.shiftKey) {
              event.preventDefault();
              const target = event.target as HTMLInputElement;
              void submitMessage(target.value);
              target.value = '';
            }
          }}
        />
        <IconButton
          color="primary"
          disabled={isSubmitting}
          onClick={(event) => {
            const input = event.currentTarget.previousElementSibling?.querySelector('input');
            if (input) {
              void submitMessage(input.value);
              input.value = '';
            }
          }}
        >
          <SendIcon />
        </IconButton>
      </Box>

      {error ? (
        <Typography color="error" sx={{ mt: 1 }}>
          {error}
        </Typography>
      ) : null}
    </Box>
  );
}
