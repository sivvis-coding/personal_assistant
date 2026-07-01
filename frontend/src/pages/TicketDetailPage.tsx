import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  Divider,
  Paper,
  Typography,
} from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import { getTicket, getTicketConversations } from '../api/tickets';
import type { Ticket, TicketConversation, TicketConversationsResponse } from '../types/ticket';

/**
 * Render ticket detail page with description and conversation thread.
 *
 * Parameters:
 *   None.
 *
 * Returns:
 *   JSX detail page.
 *
 * Edge cases:
 *   Invalid ticket IDs render a not found message.
 *   Conversation errors show a warning but do not block the ticket detail.
 */
export function TicketDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [ticket, setTicket] = useState<Ticket | null>(null);
  const [source, setSource] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [conversations, setConversations] = useState<TicketConversation[]>([]);
  const [convsSource, setConvsSource] = useState('');
  const [convsLoading, setConvsLoading] = useState(true);
  const [convsError, setConvsError] = useState(false);

  useEffect(() => {
    if (!id) {
      setIsLoading(false);
      setConvsLoading(false);
      return;
    }
    setIsLoading(true);
    setError(null);
    getTicket(id)
      .then((response) => {
        setTicket(response.ticket);
        setSource(response.source);
      })
      .catch((caught: Error) => setError(caught.message))
      .finally(() => setIsLoading(false));

    setConvsLoading(true);
    setConvsError(false);
    getTicketConversations(id)
      .then((response: TicketConversationsResponse) => {
        setConversations(response.items);
        setConvsSource(response.source);
        setConvsError(response.error);
      })
      .catch(() => {
        setConversations([]);
        setConvsError(true);
      })
      .finally(() => setConvsLoading(false));
  }, [id]);

  if (!id) {
    return (
      <Box>
        <Typography variant="h4" gutterBottom>
          Ticket no seleccionado
        </Typography>
        <Button startIcon={<ArrowBackIcon />} onClick={() => navigate('/tickets')}>
          Volver al listado
        </Button>
      </Box>
    );
  }

  if (isLoading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', mt: 8 }}>
        <CircularProgress />
      </Box>
    );
  }

  if (error) {
    return (
      <Box>
        <Typography color="error" variant="h6">
          {error}
        </Typography>
        <Button startIcon={<ArrowBackIcon />} onClick={() => navigate('/tickets')} sx={{ mt: 2 }}>
          Volver
        </Button>
      </Box>
    );
  }

  if (!ticket) {
    return (
      <Box>
        <Typography variant="h6">No se pudo cargar el ticket.</Typography>
      </Box>
    );
  }

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h4">Ticket {ticket.id}</Typography>
        <Box sx={{ display: 'flex', gap: 1 }}>
          {ticket.clickup_url ? (
            <Button
              variant="outlined"
              color="secondary"
              startIcon={<OpenInNewIcon />}
              href={ticket.clickup_url}
              target="_blank"
              rel="noopener noreferrer"
            >
              Ver en ClickUp
            </Button>
          ) : null}
          {ticket.url ? (
            <Button
              variant="outlined"
              startIcon={<OpenInNewIcon />}
              href={ticket.url}
              target="_blank"
              rel="noopener noreferrer"
            >
              Abrir en Freshservice
            </Button>
          ) : null}
          <Button startIcon={<ArrowBackIcon />} onClick={() => navigate('/tickets')}>
            Volver
          </Button>
        </Box>
      </Box>

      <Paper sx={{ p: 3 }}>
        <Typography variant="h5" gutterBottom>
          {ticket.subject}
        </Typography>
        <Typography variant="body1" color="text.secondary" gutterBottom>
          Estado: {ticket.status} · Prioridad: {ticket.priority} · Fuente: {source}
        </Typography>
        <Typography variant="body1" sx={{ mt: 2, whiteSpace: 'pre-wrap' }}>
          {ticket.description || 'Sin descripción.'}
        </Typography>
      </Paper>

      <Box sx={{ mt: 4 }}>
        <Typography variant="h6" gutterBottom>
          Conversación
        </Typography>

        {convsLoading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', mt: 4 }}>
            <CircularProgress size={28} />
          </Box>
        ) : null}

        {!convsLoading && convsError ? (
          <Alert severity="warning" sx={{ mb: 2 }}>
            No se pudo cargar el historial de conversación desde Freshservice.
          </Alert>
        ) : null}

        {!convsLoading && !convsError && conversations.length === 0 ? (
          <Typography color="text.secondary">Sin entradas de conversación.</Typography>
        ) : null}

        {!convsLoading
          ? conversations.map((entry, index) => (
              <ConversationEntry key={entry.id || index} entry={entry} />
            ))
          : null}

        {!convsLoading && convsSource ? (
          <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
            Fuente: {convsSource}
          </Typography>
        ) : null}
      </Box>
    </Box>
  );
}

interface ConversationEntryProps {
  entry: TicketConversation;
}

/**
 * Render a single conversation entry with kind-based visual distinction.
 *
 * Parameters:
 *   entry: Conversation entry to render.
 *
 * Returns:
 *   JSX conversation entry.
 *
 * Edge cases:
 *   body_text is rendered as plain text — dangerouslySetInnerHTML is never used.
 *   private_note entries use a muted background and display a "Nota interna" badge.
 *   agent_reply entries are right-aligned.
 *   customer_reply entries are left-aligned.
 */
function ConversationEntry({ entry }: ConversationEntryProps) {
  const isPrivateNote = entry.kind === 'private_note';
  const isAgentReply = entry.kind === 'agent_reply';

  const alignSelf = isAgentReply ? 'flex-end' : 'flex-start';
  const maxWidth = '75%';

  const backgroundColor = isPrivateNote
    ? 'action.hover'
    : isAgentReply
    ? 'primary.light'
    : 'background.paper';

  const kindLabel: Record<string, string> = {
    customer_reply: 'Cliente',
    agent_reply: 'Agente',
    private_note: 'Nota interna',
  };

  const kindColor: Record<string, 'default' | 'primary' | 'warning'> = {
    customer_reply: 'default',
    agent_reply: 'primary',
    private_note: 'warning',
  };

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: alignSelf, mb: 2, maxWidth }}>
      <Paper
        variant="outlined"
        sx={{
          p: 2,
          width: '100%',
          bgcolor: backgroundColor,
          borderStyle: isPrivateNote ? 'dashed' : 'solid',
        }}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1, flexWrap: 'wrap' }}>
          <Chip
            label={kindLabel[entry.kind]}
            color={kindColor[entry.kind]}
            size="small"
            variant={isPrivateNote ? 'outlined' : 'filled'}
          />
          {entry.from_email ? (
            <Typography variant="caption" color="text.secondary">
              {entry.from_email}
            </Typography>
          ) : null}
          {entry.created_at ? (
            <Typography variant="caption" color="text.secondary" sx={{ ml: 'auto' }}>
              {new Date(entry.created_at).toLocaleString()}
            </Typography>
          ) : null}
        </Box>
        <Divider sx={{ mb: 1 }} />
        <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap' }}>
          {entry.body_text || '(sin contenido)'}
        </Typography>
      </Paper>
    </Box>
  );
}
