import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box,
  Button,
  Card,
  CardActionArea,
  CardContent,
  CircularProgress,
  Typography,
} from '@mui/material';
import ChatIcon from '@mui/icons-material/Chat';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import { useChatStore } from '../stores/chatStore';
import { listAssistantConversations } from '../api/assistant';

/**
 * Render the conversation history list page.
 *
 * Loads conversations from the backend on mount.
 *
 * Parameters:
 *   None.
 *
 * Returns:
 *   JSX history page.
 *
 * Edge cases:
 *   Conversations without a title use the first message or "Sin título".
 *   Loading state shown while fetching.
 *   Error state shown when fetch fails.
 */
export function ConversationHistoryPage() {
  const navigate = useNavigate();
  const conversations = useChatStore((state) => state.conversations);
  const setConversations = useChatStore((state) => state.setConversations);
  const isLoading = useChatStore((state) => state.isLoading);
  const setLoading = useChatStore((state) => state.setLoading);
  const error = useChatStore((state) => state.error);
  const setError = useChatStore((state) => state.setError);

  useEffect(() => {
    async function loadConversations() {
      setLoading(true);
      setError(null);
      try {
        const data = await listAssistantConversations();
        setConversations(
          data.map((c) => ({
            id: c.id,
            title: c.title,
            lastMessage: '', // Not available in summary, will be blank
            messageCount: c.message_count,
            updatedAt: new Date(c.updated_at),
          }))
        );
      } catch (caught) {
        setError((caught as Error).message);
      } finally {
        setLoading(false);
      }
    }
    void loadConversations();
  }, [setConversations, setLoading, setError]);

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h4">Historial de conversaciones</Typography>
        <Button startIcon={<ArrowBackIcon />} onClick={() => navigate('/assistant')}>
          Volver al chat
        </Button>
      </Box>

      {isLoading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
          <CircularProgress />
        </Box>
      ) : error ? (
        <Typography color="error">{error}</Typography>
      ) : conversations.length === 0 ? (
        <Typography color="text.secondary">Aún no hay conversaciones guardadas.</Typography>
      ) : (
        conversations.map((conversation) => (
          <Card key={conversation.id} sx={{ mb: 2 }}>
            <CardActionArea onClick={() => navigate(`/assistant/history/${conversation.id}`)}>
              <CardContent>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                  <ChatIcon color="action" />
                  <Box sx={{ flexGrow: 1 }}>
                    <Typography variant="h6">{conversation.title || 'Sin título'}</Typography>
                    <Typography variant="body2" color="text.secondary">
                      {conversation.lastMessage || `${conversation.messageCount} mensajes`}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      {conversation.messageCount} mensajes · {conversation.updatedAt.toLocaleString()}
                    </Typography>
                  </Box>
                </Box>
              </CardContent>
            </CardActionArea>
          </Card>
        ))
      )}
    </Box>
  );
}
