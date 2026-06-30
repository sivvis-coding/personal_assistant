import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Box,
  Button,
  CircularProgress,
  Paper,
  Typography,
} from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import ChatIcon from '@mui/icons-material/Chat';
import { useChatStore } from '../stores/chatStore';
import { getAssistantConversation } from '../api/assistant';
import type { ConversationDetailResponse, ConversationMessage } from '../types/assistant';

/**
 * Render a read-only historical conversation with full message history.
 *
 * Loads messages from the backend on mount.
 *
 * Parameters:
 *   None.
 *
 * Returns:
 *   JSX conversation detail page.
 *
 * Edge cases:
 *   Unknown conversation IDs show a not found message.
 *   Loading state shown while fetching.
 *   Error state shown when fetch fails.
 */
export function ConversationDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const conversations = useChatStore((state) => state.conversations);
  const conversation = conversations.find((item) => item.id === id);
  const { setConversationId, setMessages } = useChatStore();

  const [detail, setDetail] = useState<ConversationDetailResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;

    async function loadConversation() {
      setIsLoading(true);
      setError(null);
      try {
        const data = await getAssistantConversation(id as string);
        setDetail(data);
      } catch (caught) {
        setError((caught as Error).message);
      } finally {
        setIsLoading(false);
      }
    }
    void loadConversation();
  }, [id]);

  if (!id) {
    return (
      <Box>
        <Typography variant="h4" gutterBottom>
          Conversación no encontrada
        </Typography>
        <Button startIcon={<ArrowBackIcon />} onClick={() => navigate('/assistant/history')}>
          Volver al historial
        </Button>
      </Box>
    );
  }

  if (!detail && !isLoading && !error) {
    return (
      <Box>
        <Typography variant="h4" gutterBottom>
          Conversación no encontrada
        </Typography>
        <Button startIcon={<ArrowBackIcon />} onClick={() => navigate('/assistant/history')}>
          Volver al historial
        </Button>
      </Box>
    );
  }

  const title = detail?.title || conversation?.title || 'Sin título';

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h4">{title}</Typography>
        <Box sx={{ display: 'flex', gap: 1 }}>
          <Button
            variant="contained"
            startIcon={<ChatIcon />}
            onClick={() => {
              if (id) {
                window.localStorage.setItem('ASSISTANT_CONVERSATION_ID', id);
                setConversationId(id);
                setMessages([]);
              }
              navigate('/assistant');
            }}
          >
            Continuar
          </Button>
          <Button startIcon={<ArrowBackIcon />} onClick={() => navigate('/assistant/history')}>
            Volver
          </Button>
        </Box>
      </Box>

      {isLoading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
          <CircularProgress />
        </Box>
      ) : error ? (
        <Paper sx={{ p: 3, bgcolor: 'error.light', color: 'error.contrastText' }}>
          <Typography variant="body1">Error: {error}</Typography>
        </Paper>
      ) : detail ? (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          {detail.messages.map((msg: ConversationMessage, index: number) => (
            <Box key={index} sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
              {/* User message */}
              <Paper
                sx={{
                  alignSelf: 'flex-end',
                  maxWidth: '80%',
                  bgcolor: 'primary.light',
                  color: 'primary.contrastText',
                  borderRadius: 2,
                  p: 2,
                }}
              >
                <Typography variant="body1" sx={{ whiteSpace: 'pre-wrap' }}>
                  {msg.user_message}
                </Typography>
                <Typography variant="caption" sx={{ display: 'block', mt: 1, opacity: 0.7 }}>
                  {new Date(msg.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                </Typography>
              </Paper>
              {/* Assistant message */}
              <Paper
                sx={{
                  alignSelf: 'flex-start',
                  maxWidth: '80%',
                  bgcolor: 'grey.100',
                  color: 'text.primary',
                  borderRadius: 2,
                  p: 2,
                }}
              >
                <Typography variant="body1" sx={{ whiteSpace: 'pre-wrap' }}>
                  {msg.assistant_answer}
                </Typography>
                <Typography variant="caption" sx={{ display: 'block', mt: 1, opacity: 0.7 }}>
                  {new Date(msg.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                </Typography>
              </Paper>
            </Box>
          ))}
        </Box>
      ) : (
        <Paper sx={{ p: 4, textAlign: 'center', color: 'text.secondary' }}>
          <Typography variant="body1">Cargando conversación...</Typography>
        </Paper>
      )}

      {detail && (
        <Typography variant="caption" display="block" sx={{ mt: 3, color: 'text.secondary' }}>
          ID: {detail.id} · Creada: {new Date(detail.created_at).toLocaleString()}
        </Typography>
      )}
    </Box>
  );
}
