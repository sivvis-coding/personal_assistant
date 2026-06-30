import { useEffect, useState } from 'react';
import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Box,
  Button,
  Card,
  CardActions,
  CardContent,
  Chip,
  CircularProgress,
  Divider,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import CheckIcon from '@mui/icons-material/Check';
import CloseIcon from '@mui/icons-material/Close';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import { useActionsStore } from '../stores/actionsStore';
import { useChatStore } from '../stores/chatStore';
import {
  approveAssistantAction,
  listPendingAssistantActions,
  rejectAssistantAction,
  updateAssistantActionPayload,
} from '../api/assistant';
import { getTicket, getTicketConversations } from '../api/tickets';
import type { AssistantAction } from '../types/assistant';
import type { Ticket, TicketConversation, TicketDetailResponse } from '../types/ticket';

const actionTypeLabels: Record<string, string> = {
  prepare_clickup_task: 'Preparar tarea ClickUp',
  approve_clickup_task: 'Crear tarea ClickUp',
  save_time_entry: 'Imputar tiempo',
  reply_freshservice_ticket: 'Responder ticket',
  resolve_freshservice_ticket: 'Resolver ticket',
  request_info_freshservice_ticket: 'Pedir información',
  send_ticket_to_backlog: 'Pasar a backlog ClickUp',
};

const conversationKindLabels: Record<string, { label: string; color: 'primary' | 'default' | 'warning' }> = {
  customer_reply: { label: 'Cliente', color: 'primary' },
  agent_reply: { label: 'Agente', color: 'default' },
  private_note: { label: 'Nota interna', color: 'warning' },
};

function formatTimestamp(ts: string | null | undefined): string {
  if (!ts) return '';
  try {
    return new Date(ts).toLocaleString('es-ES', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' });
  } catch {
    return ts;
  }
}

function stripHtml(html: string): string {
  return html
    .replace(/<br\s*\/?>/gi, '\n')
    .replace(/<\/?(p|div|li|h[1-6]|blockquote|tr)[^>]*>/gi, '\n')
    .replace(/<[^>]+>/g, '')
    .replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&nbsp;/g, ' ').replace(/&quot;/g, '"').replace(/&#39;/g, "'")
    .split('\n').map((l) => l.trim()).join('\n')
    .replace(/\n{3,}/g, '\n\n')
    .trim();
}

function getDescription(ticket: Ticket): string {
  if (ticket.description) return ticket.description;
  const raw = ticket.raw;
  const rawDesc = raw.description_text ?? raw.description;
  if (typeof rawDesc === 'string' && rawDesc.trim()) {
    return rawDesc.includes('<') ? stripHtml(rawDesc) : rawDesc;
  }
  return '';
}

function ConversationEntry({ conv }: { conv: TicketConversation }) {
  const kindMeta = conversationKindLabels[conv.kind] ?? { label: conv.kind, color: 'default' as const };
  const text = conv.body_text ?? '';
  return (
    <Box
      sx={{
        border: '1px solid',
        borderColor: 'divider',
        borderRadius: 1,
        p: 1,
        backgroundColor: conv.kind === 'customer_reply' ? 'action.hover' : 'transparent',
      }}
    >
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 0.5 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
          <Chip label={kindMeta.label} size="small" color={kindMeta.color} />
          {conv.from_email ? (
            <Typography variant="caption" color="text.secondary">{conv.from_email}</Typography>
          ) : null}
        </Box>
        <Typography variant="caption" color="text.secondary">{formatTimestamp(conv.created_at)}</Typography>
      </Box>
      <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
        {text.length > 400 ? `${text.slice(0, 400)}…` : text}
      </Typography>
    </Box>
  );
}

function ConversationThread({ conversations }: { conversations: TicketConversation[] }) {
  const [showHistory, setShowHistory] = useState(false);
  const sorted = [...conversations].sort((a, b) => {
    const ta = a.created_at ? new Date(a.created_at).getTime() : 0;
    const tb = b.created_at ? new Date(b.created_at).getTime() : 0;
    return tb - ta;
  });
  const last = sorted[0];
  const previous = sorted.slice(1);

  return (
    <Box>
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 1 }}>
        <Typography variant="caption" color="text.secondary">
          Conversación ({conversations.length} mensaje{conversations.length !== 1 ? 's' : ''})
        </Typography>
        {previous.length > 0 ? (
          <Button size="small" variant="text" sx={{ p: 0, minWidth: 'auto', fontSize: 12 }} onClick={() => setShowHistory((v) => !v)}>
            {showHistory ? 'Ocultar anteriores' : `Ver ${previous.length} anterior${previous.length !== 1 ? 'es' : ''}`}
          </Button>
        ) : null}
      </Box>

      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
        {showHistory
          ? previous.map((conv) => <ConversationEntry key={conv.id} conv={conv} />)
          : null}
        {last ? <ConversationEntry conv={last} /> : null}
      </Box>
    </Box>
  );
}

/**
 * Shows ticket subject, description and recent conversations above the action payload editor.
 * Collapses to a single summary line; expands inline so the user never leaves the page.
 */
function TicketContextPanel({ ticketId }: { ticketId: string }) {
  const [ticket, setTicket] = useState<TicketDetailResponse | null>(null);
  const [conversations, setConversations] = useState<TicketConversation[]>([]);
  const [loading, setLoading] = useState(false);
  const [expanded, setExpanded] = useState(true);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      try {
        const [ticketRes, convsRes] = await Promise.all([
          getTicket(ticketId),
          getTicketConversations(ticketId),
        ]);
        if (!cancelled) {
          setTicket(ticketRes);
          setConversations(convsRes.items.slice(-6));
        }
      } catch {
        // panel degrades gracefully
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [ticketId]);

  if (loading) {
    return (
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, py: 1 }}>
        <CircularProgress size={14} />
        <Typography variant="caption" color="text.secondary">Cargando contexto del ticket…</Typography>
      </Box>
    );
  }

  if (!ticket) return null;

  const t = ticket.ticket;
  const description = getDescription(t);
  const publicConversations = conversations.filter((c) => !c.private);

  return (
    <Accordion
      expanded={expanded}
      onChange={(_e, isExpanded) => setExpanded(isExpanded)}
      disableGutters
      elevation={0}
      sx={{ border: '1px solid', borderColor: 'divider', borderRadius: 1, mb: 2, '&:before': { display: 'none' } }}
    >
      <AccordionSummary expandIcon={<ExpandMoreIcon />} sx={{ minHeight: 40, '& .MuiAccordionSummary-content': { my: 0.5 } }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
          <Typography variant="subtitle2" sx={{ fontWeight: 600 }}>
            #{t.id} — {t.subject}
          </Typography>
          <Chip label={t.status} size="small" />
          <Chip label={t.priority} size="small" variant="outlined" />
          {t.requester?.name ? (
            <Tooltip title={t.requester.email ?? ''}>
              <Typography variant="caption" color="text.secondary">{t.requester.name}</Typography>
            </Tooltip>
          ) : null}
        </Box>
      </AccordionSummary>

      <AccordionDetails sx={{ pt: 0 }}>
        {description ? (
          <Box sx={{ mb: 2 }}>
            <Typography variant="caption" color="text.secondary" display="block" sx={{ mb: 0.5 }}>
              Descripción
            </Typography>
            <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
              {description}
            </Typography>
          </Box>
        ) : null}

        {publicConversations.length > 0 ? (
          <ConversationThread conversations={publicConversations} />
        ) : null}
      </AccordionDetails>
    </Accordion>
  );
}

/**
 * Show time entry payload fields as editable inputs.
 */
function TimeEntryFields({
  payload,
  onChange,
}: {
  payload: Record<string, unknown>;
  onChange: (key: string, value: string) => void;
}) {
  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
      <TextField
        label="Tarea"
        size="small"
        fullWidth
        value={String(payload.task_name ?? '')}
        onChange={(e) => onChange('task_name', e.target.value)}
      />
      <TextField
        label="Cliente"
        size="small"
        fullWidth
        value={String(payload.client_name ?? '')}
        onChange={(e) => onChange('client_name', e.target.value)}
      />
      <Box sx={{ display: 'flex', gap: 1 }}>
        <TextField
          label="Inicio"
          size="small"
          fullWidth
          value={String(payload.start_datetime ?? '')}
          onChange={(e) => onChange('start_datetime', e.target.value)}
          helperText="YYYY-MM-DDTHH:MM"
        />
        <TextField
          label="Fin"
          size="small"
          fullWidth
          value={String(payload.end_datetime ?? '')}
          onChange={(e) => onChange('end_datetime', e.target.value)}
          helperText="YYYY-MM-DDTHH:MM"
        />
      </Box>
      <TextField
        label="Descripción"
        size="small"
        fullWidth
        multiline
        rows={2}
        value={String(payload.description ?? '')}
        onChange={(e) => onChange('description', e.target.value)}
      />
    </Box>
  );
}

/**
 * Show the reply body as an editable textarea.
 */
function ReplyFields({
  payload,
  helperText,
  onChange,
}: {
  payload: Record<string, unknown>;
  helperText?: string;
  onChange: (key: string, value: string) => void;
}) {
  return (
    <TextField
      label="Respuesta al cliente"
      size="small"
      fullWidth
      multiline
      rows={6}
      value={String(payload.body ?? '')}
      onChange={(e) => onChange('body', e.target.value)}
      helperText={helperText ?? 'Texto que se enviará públicamente al cliente en Freshservice.'}
    />
  );
}

/**
 * Show the user story as an editable textarea.
 */
function UserStoryFields({
  payload,
  onChange,
}: {
  payload: Record<string, unknown>;
  onChange: (key: string, value: string) => void;
}) {
  const story = payload.user_story;
  const storyText = typeof story === 'object' && story !== null ? JSON.stringify(story, null, 2) : String(story ?? '');
  return (
    <TextField
      label="User story generada"
      size="small"
      fullWidth
      multiline
      rows={8}
      value={storyText}
      onChange={(e) => {
        try {
          onChange('user_story', JSON.parse(e.target.value));
        } catch {
          onChange('user_story', e.target.value);
        }
      }}
      helperText="Revisa y ajusta antes de crear la tarea en ClickUp."
      inputProps={{ style: { fontFamily: 'monospace', fontSize: 12 } }}
    />
  );
}

/**
 * Render the editable payload section for one action, keyed by type.
 */
function ActionPayloadEditor({
  action,
  payload,
  onFieldChange,
}: {
  action: AssistantAction;
  payload: Record<string, unknown>;
  onFieldChange: (key: string, value: unknown) => void;
}) {
  function handleChange(key: string, value: unknown) {
    onFieldChange(key, value);
  }

  if (action.action_type === 'save_time_entry') {
    return (
      <TimeEntryFields
        payload={payload}
        onChange={(k, v) => handleChange(k, v)}
      />
    );
  }

  if (
    action.action_type === 'reply_freshservice_ticket' ||
    action.action_type === 'request_info_freshservice_ticket' ||
    action.action_type === 'send_ticket_to_backlog'
  ) {
    const helperText =
      action.action_type === 'send_ticket_to_backlog'
        ? 'Mensaje que se enviará al cliente. El enlace a la tarea de ClickUp se añadirá al final automáticamente.'
        : action.action_type === 'request_info_freshservice_ticket'
          ? 'Mensaje público al cliente. El ticket pasará a "esperando respuesta de tercero".'
          : 'Texto que se enviará públicamente al cliente en Freshservice.';
    return (
      <ReplyFields
        payload={payload}
        helperText={helperText}
        onChange={(k, v) => handleChange(k, v)}
      />
    );
  }

  if (action.action_type === 'approve_clickup_task') {
    return (
      <UserStoryFields
        payload={payload}
        onChange={(k, v) => handleChange(k, v)}
      />
    );
  }

  return null;
}

export function ActionsPage() {
  const { pendingActions, isLoading, error, setPendingActions, setLoading, setError, removeAction } = useActionsStore();
  const { updatePendingAction: updateChatPendingAction } = useChatStore();

  const [editedPayloads, setEditedPayloads] = useState<Record<string, Record<string, unknown>>>({});
  const [submitting, setSubmitting] = useState<string | null>(null);

  useEffect(() => {
    async function loadActions() {
      setLoading(true);
      try {
        const actions = await listPendingAssistantActions();
        setPendingActions(actions);
      } catch (caught) {
        setError((caught as Error).message);
      } finally {
        setLoading(false);
      }
    }
    void loadActions();
  }, [setPendingActions, setLoading, setError]);

  function handleFieldChange(actionId: string, originalPayload: Record<string, unknown>, key: string, value: unknown) {
    setEditedPayloads((prev) => ({
      ...prev,
      [actionId]: { ...(prev[actionId] ?? originalPayload), [key]: value },
    }));
  }

  function getEffectivePayload(action: AssistantAction): Record<string, unknown> {
    return editedPayloads[action.id] ?? action.payload;
  }

  function hasEdits(action: AssistantAction): boolean {
    return action.id in editedPayloads;
  }

  async function handleApprove(action: AssistantAction): Promise<void> {
    setSubmitting(action.id);
    try {
      if (hasEdits(action)) {
        await updateAssistantActionPayload(action.id, editedPayloads[action.id]);
        setEditedPayloads((prev) => {
          const next = { ...prev };
          delete next[action.id];
          return next;
        });
      }
      const updated = await approveAssistantAction(action.id);
      removeAction(action.id);
      updateChatPendingAction(updated);
      setPendingActions(await listPendingAssistantActions());
    } catch (caught) {
      setError((caught as Error).message);
    } finally {
      setSubmitting(null);
    }
  }

  async function handleReject(actionId: string): Promise<void> {
    setSubmitting(actionId);
    try {
      const updated = await rejectAssistantAction(actionId);
      removeAction(actionId);
      updateChatPendingAction(updated);
      setPendingActions(await listPendingAssistantActions());
    } catch (caught) {
      setError((caught as Error).message);
    } finally {
      setSubmitting(null);
    }
  }

  if (isLoading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', mt: 8 }}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box>
      <Typography variant="h4" gutterBottom>
        Acciones pendientes
      </Typography>

      {error ? (
        <Typography color="error" sx={{ mb: 2 }}>
          {error}
        </Typography>
      ) : null}

      {pendingActions.length === 0 ? (
        <Typography color="text.secondary">No hay acciones pendientes.</Typography>
      ) : (
        pendingActions.map((action) => {
          const busy = submitting === action.id;
          const effectivePayload = getEffectivePayload(action);
          const edited = hasEdits(action);
          const showTicketContext =
            action.ticket_id != null &&
            (action.action_type === 'reply_freshservice_ticket' ||
              action.action_type === 'request_info_freshservice_ticket' ||
              action.action_type === 'send_ticket_to_backlog' ||
              action.action_type === 'prepare_clickup_task' ||
              action.action_type === 'resolve_freshservice_ticket');

          return (
            <Card key={action.id} sx={{ mb: 2 }}>
              <CardContent>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 1 }}>
                  <Typography variant="h6">{action.title}</Typography>
                  <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
                    {edited ? (
                      <Chip label="Editado" size="small" color="warning" variant="outlined" />
                    ) : null}
                    <Chip label={actionTypeLabels[action.action_type] ?? action.action_type} size="small" />
                  </Box>
                </Box>

                <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                  {action.description}
                </Typography>

                {showTicketContext ? (
                  <TicketContextPanel ticketId={action.ticket_id!} />
                ) : null}

                <Divider sx={{ mb: 2 }} />

                <ActionPayloadEditor
                  action={action}
                  payload={effectivePayload}
                  onFieldChange={(key, value) =>
                    handleFieldChange(action.id, action.payload, key, value)
                  }
                />
              </CardContent>

              <CardActions sx={{ justifyContent: 'flex-end', gap: 1 }}>
                <Button
                  size="small"
                  color="error"
                  startIcon={<CloseIcon />}
                  disabled={busy}
                  onClick={() => void handleReject(action.id)}
                >
                  Rechazar
                </Button>
                <Button
                  size="small"
                  color="success"
                  variant={edited ? 'contained' : 'outlined'}
                  startIcon={busy ? <CircularProgress size={14} /> : <CheckIcon />}
                  disabled={busy}
                  onClick={() => void handleApprove(action)}
                >
                  {edited ? 'Guardar y aprobar' : 'Aprobar'}
                </Button>
              </CardActions>
            </Card>
          );
        })
      )}
    </Box>
  );
}
