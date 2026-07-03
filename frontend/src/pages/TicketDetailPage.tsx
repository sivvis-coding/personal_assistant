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
  Stack,
  Tooltip,
  Typography,
} from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import PersonIcon from '@mui/icons-material/Person';
import AccessTimeIcon from '@mui/icons-material/AccessTime';
import { getTicket, getTicketConversations } from '../api/tickets';
import type { RequestedItem, Ticket, TicketConversation, TicketConversationsResponse } from '../types/ticket';

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
        <Typography variant="h6" gutterBottom>Ticket no seleccionado</Typography>
        <Button startIcon={<ArrowBackIcon />} onClick={() => navigate('/tickets')}>Volver</Button>
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

  if (error || !ticket) {
    return (
      <Box>
        <Typography color="error" variant="body1" gutterBottom>{error ?? 'No se pudo cargar el ticket.'}</Typography>
        <Button startIcon={<ArrowBackIcon />} onClick={() => navigate('/tickets')} sx={{ mt: 1 }}>Volver</Button>
      </Box>
    );
  }

  const sortedConversations = [...conversations].sort((a, b) => {
    if (!a.created_at) return 1;
    if (!b.created_at) return -1;
    return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
  });

  return (
    <Box sx={{ maxWidth: 900, mx: 'auto' }}>

      {/* ── header ── */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 2, gap: 2 }}>
        <Box sx={{ minWidth: 0 }}>
          <Typography variant="caption" color="text.disabled" sx={{ fontFamily: 'monospace' }}>
            #{ticket.id} · {source}
          </Typography>
          <Typography variant="h5" fontWeight={600} sx={{ mt: 0.5, lineHeight: 1.3 }}>
            {ticket.subject}
          </Typography>
        </Box>
        <Stack direction="row" spacing={1} flexShrink={0} flexWrap="wrap" justifyContent="flex-end">
          {ticket.clickup_url ? (
            <Button size="small" variant="outlined" color="secondary" startIcon={<OpenInNewIcon />}
              href={ticket.clickup_url} target="_blank" rel="noopener noreferrer">
              ClickUp
            </Button>
          ) : null}
          {ticket.url ? (
            <Button size="small" variant="outlined" startIcon={<OpenInNewIcon />}
              href={ticket.url} target="_blank" rel="noopener noreferrer">
              Freshservice
            </Button>
          ) : null}
          <Button size="small" startIcon={<ArrowBackIcon />} onClick={() => navigate('/tickets')}>
            Volver
          </Button>
        </Stack>
      </Box>

      {/* ── metadata row ── */}
      <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" mb={2}>
        <StatusChip status={ticket.status} />
        <PriorityChip priority={ticket.priority} />
        {ticket.sla ? <SlaChip sla={ticket.sla} /> : null}
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, ml: 0.5 }}>
          <PersonIcon sx={{ fontSize: 16, color: 'text.disabled' }} />
          <Typography variant="body2" color="text.secondary">
            {ticket.requester.name}
            {ticket.requester.email ? ` · ${ticket.requester.email}` : ''}
          </Typography>
        </Box>
      </Stack>

      {/* ── description / requested items ── */}
      <Paper variant="outlined" sx={{ p: 2.5, mb: 3 }}>
        {ticket.description ? (
          <>
            <Typography variant="overline" color="text.disabled" display="block" gutterBottom>
              Descripción
            </Typography>
            <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap', lineHeight: 1.7 }}>
              {ticket.description}
            </Typography>
          </>
        ) : null}

        {ticket.requested_items && ticket.requested_items.length > 0 ? (
          <>
            {ticket.description ? <Divider sx={{ my: 2 }} /> : null}
            <Typography variant="overline" color="text.disabled" display="block" gutterBottom>
              Elementos solicitados
            </Typography>
            <Stack spacing={1.5}>
              {ticket.requested_items.map((item, index) => (
                <RequestedItemCard key={item.id ?? index} item={item} index={index} />
              ))}
            </Stack>
          </>
        ) : null}

        {!ticket.description && (!ticket.requested_items || ticket.requested_items.length === 0) ? (
          <Typography variant="body2" color="text.disabled" sx={{ fontStyle: 'italic' }}>
            Sin descripción.
          </Typography>
        ) : null}
      </Paper>

      {/* ── ticket attributes (custom fields) ── */}
      {ticket.custom_fields && Object.keys(ticket.custom_fields).length > 0 ? (
        <TicketAttributesSection customFields={ticket.custom_fields} clickupUrl={ticket.clickup_url} />
      ) : null}

      {/* ── conversation thread ── */}
      <Box>
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 1.5 }}>
          <Typography variant="subtitle1" fontWeight={600}>
            Conversación
            {conversations.length > 0 ? (
              <Typography component="span" variant="body2" color="text.disabled" sx={{ ml: 1 }}>
                {conversations.length} entradas · más reciente primero
              </Typography>
            ) : null}
          </Typography>
          {convsSource ? (
            <Typography variant="caption" color="text.disabled">{convsSource}</Typography>
          ) : null}
        </Box>

        {convsLoading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', mt: 4 }}>
            <CircularProgress size={28} />
          </Box>
        ) : null}

        {!convsLoading && convsError ? (
          <Alert severity="warning">No se pudo cargar el historial desde Freshservice.</Alert>
        ) : null}

        {!convsLoading && !convsError && conversations.length === 0 ? (
          <Typography variant="body2" color="text.secondary">Sin entradas de conversación.</Typography>
        ) : null}

        {!convsLoading && !convsError ? (
          <Stack spacing={1.5}>
            {sortedConversations.map((entry, index) => (
              <ConversationEntry key={entry.id || index} entry={entry} />
            ))}
          </Stack>
        ) : null}
      </Box>

    </Box>
  );
}

// ─── ticket attributes ────────────────────────────────────────────────────────

interface TicketAttributesSectionProps {
  customFields: Record<string, unknown>;
  clickupUrl?: string | null;
}

function TicketAttributesSection({ customFields, clickupUrl }: TicketAttributesSectionProps) {
  const entries = Object.entries(customFields).filter(([key, value]) => {
    if (value === null || value === undefined || value === '') return false;
    // clickup_url is already shown as a button in the header
    if (key === 'clickup_url') return false;
    return true;
  });

  if (entries.length === 0) return null;

  return (
    <Paper variant="outlined" sx={{ p: 2.5, mb: 3 }}>
      <Typography variant="overline" color="text.disabled" display="block" gutterBottom>
        Atributos del ticket
      </Typography>
      <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: 1.5 }}>
        {entries.map(([key, value]) => {
          const str = typeof value === 'boolean' ? (value ? 'Sí' : 'No') : String(value);
          const isLong = str.length > 80 || str.includes('\n');
          return (
            <Box key={key} sx={isLong ? { gridColumn: '1 / -1' } : {}}>
              <Typography variant="caption" color="text.disabled" sx={{ textTransform: 'capitalize', display: 'block', mb: 0.25 }}>
                {key.replace(/_/g, ' ')}
              </Typography>
              <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
                {str}
              </Typography>
            </Box>
          );
        })}
      </Box>
    </Paper>
  );
}

// ─── status / priority / sla chips ───────────────────────────────────────────

const STATUS_COLOR: Record<string, 'default' | 'warning' | 'success' | 'error' | 'info'> = {
  open: 'info',
  pending: 'warning',
  'waiting on customer': 'warning',
  'waiting on third party': 'warning',
  resolved: 'success',
  closed: 'default',
};

const PRIORITY_COLOR: Record<string, 'default' | 'warning' | 'error' | 'info'> = {
  low: 'default',
  medium: 'info',
  high: 'warning',
  urgent: 'error',
};

function StatusChip({ status }: { status: string }) {
  return (
    <Chip
      label={status}
      size="small"
      color={STATUS_COLOR[status] ?? 'default'}
      variant="filled"
      sx={{ textTransform: 'capitalize' }}
    />
  );
}

function PriorityChip({ priority }: { priority: string }) {
  return (
    <Chip
      label={priority}
      size="small"
      color={PRIORITY_COLOR[priority] ?? 'default'}
      variant="outlined"
      sx={{ textTransform: 'capitalize' }}
    />
  );
}

function SlaChip({ sla }: { sla: NonNullable<Ticket['sla']> }) {
  const color = sla.status === 'breached' ? 'error' : sla.status === 'at_risk' ? 'warning' : 'default';
  const label = sla.status === 'breached'
    ? 'SLA vencido'
    : sla.status === 'at_risk'
    ? 'SLA en riesgo'
    : sla.status === 'ok' && sla.minutes_remaining != null
    ? `SLA: ${sla.minutes_remaining < 60 ? `${sla.minutes_remaining}m` : `${Math.round(sla.minutes_remaining / 60)}h`}`
    : null;

  if (!label) return null;
  return (
    <Tooltip title={sla.due_at ? `Vence: ${new Date(sla.due_at).toLocaleString()}` : ''}>
      <Chip icon={<AccessTimeIcon />} label={label} size="small" color={color} variant="outlined" />
    </Tooltip>
  );
}

// ─── requested item card ──────────────────────────────────────────────────────

interface RequestedItemCardProps {
  item: RequestedItem;
  index: number;
}

function RequestedItemCard({ item, index }: RequestedItemCardProps) {
  const fields = item.custom_fields ?? {};
  const fieldEntries = Object.entries(fields).filter(([, v]) => v !== null && v !== undefined && v !== '');

  const itemLabel = item.service_item_name
    ?? item.name
    ?? (item.item_id ? `Artículo #${item.item_id}` : `Elemento ${index + 1}`);

  return (
    <Paper variant="outlined" sx={{ p: 2, borderColor: 'primary.light', borderLeftWidth: 3 }}>
      {/* header */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap', mb: fieldEntries.length > 0 ? 1.5 : 0 }}>
        <Typography variant="subtitle2" fontWeight={600} sx={{ flexGrow: 1 }}>
          {itemLabel}
        </Typography>
        {item.quantity != null ? (
          <Typography variant="caption" color="text.secondary" sx={{ whiteSpace: 'nowrap' }}>
            Cantidad: {item.quantity}
          </Typography>
        ) : null}
        {item.fulfillment_status ? (
          <Chip label={item.fulfillment_status} size="small" variant="outlined" sx={{ height: 20, fontSize: 11, textTransform: 'capitalize' }} />
        ) : null}
      </Box>

      {/* fields: short values side-by-side, long values full-width */}
      {fieldEntries.length > 0 ? (
        <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: 1.5 }}>
          {fieldEntries.map(([key, value]) => {
            const str = typeof value === 'boolean' ? (value ? 'Sí' : 'No') : String(value);
            const isLong = str.length > 80 || str.includes('\n');
            return (
              <Box key={key} sx={isLong ? { gridColumn: '1 / -1' } : {}}>
                <Typography variant="caption" color="text.disabled" sx={{ textTransform: 'capitalize', display: 'block', mb: 0.25 }}>
                  {key.replace(/_/g, ' ')}
                </Typography>
                <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word', lineHeight: 1.5 }}>
                  {str}
                </Typography>
              </Box>
            );
          })}
        </Box>
      ) : (
        <Typography variant="caption" color="text.disabled">Sin campos adicionales.</Typography>
      )}
    </Paper>
  );
}

// ─── conversation entry ───────────────────────────────────────────────────────

interface ConversationEntryProps {
  entry: TicketConversation;
}

function ConversationEntry({ entry }: ConversationEntryProps) {
  const isPrivate = entry.kind === 'private_note';
  const isAgent = entry.kind === 'agent_reply';

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
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: isAgent ? 'flex-end' : 'flex-start',
      }}
    >
      <Box sx={{ maxWidth: '78%', width: '100%' }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5, flexDirection: isAgent ? 'row-reverse' : 'row' }}>
          <Chip
            label={kindLabel[entry.kind] ?? entry.kind}
            color={kindColor[entry.kind] ?? 'default'}
            size="small"
            variant={isPrivate ? 'outlined' : 'filled'}
          />
          {entry.from_email ? (
            <Typography variant="caption" color="text.secondary">{entry.from_email}</Typography>
          ) : null}
          {entry.created_at ? (
            <Typography variant="caption" color="text.disabled">
              {new Date(entry.created_at).toLocaleString('es-ES', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })}
            </Typography>
          ) : null}
        </Box>
        <Paper
          variant="outlined"
          sx={{
            p: 1.5,
            bgcolor: isPrivate ? 'action.hover' : isAgent ? 'primary.50' : 'background.paper',
            borderStyle: isPrivate ? 'dashed' : 'solid',
            borderColor: isAgent ? 'primary.light' : undefined,
          }}
        >
          <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap', lineHeight: 1.6 }}>
            {entry.body_text || '(sin contenido)'}
          </Typography>
        </Paper>
      </Box>
    </Box>
  );
}
