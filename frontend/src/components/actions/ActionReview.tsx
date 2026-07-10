import { useEffect, useState } from 'react';
import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Autocomplete,
  Box,
  Button,
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
import { approveAssistantAction, rejectAssistantAction, updateAssistantActionPayload } from '../../api/assistant';
import { getPersonalListClients } from '../../api/clickup';
import { getTicket, getTicketConversations } from '../../api/tickets';
import type { AssistantAction } from '../../types/assistant';
import type { Ticket, TicketConversation, TicketDetailResponse } from '../../types/ticket';

export const ACTION_TYPE_LABELS: Record<string, string> = {
  prepare_clickup_us: 'Crear US ClickUp',
  save_time_entry: 'Imputar tiempo',
  reply_freshservice_ticket: 'Responder ticket',
  resolve_freshservice_ticket: 'Resolver ticket',
  request_info_freshservice_ticket: 'Pedir información',
  send_ticket_to_backlog: 'Pasar a backlog ClickUp',
  link_existing_clickup_task: 'Vincular tarea ClickUp existente',
};

export const STATUS_COLORS: Record<string, 'default' | 'success' | 'error' | 'warning'> = {
  proposed: 'default',
  approved: 'success',
  completed: 'success',
  rejected: 'error',
  failed: 'error',
};

// Action types that carry a Freshservice ticket worth showing as context.
export const TICKET_CONTEXT_TYPES = new Set([
  'reply_freshservice_ticket',
  'request_info_freshservice_ticket',
  'send_ticket_to_backlog',
  'resolve_freshservice_ticket',
  'link_existing_clickup_task',
]);

// ─── helpers ────────────────────────────────────────────────────────────────

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

// ─── ticket context ───────────────────────────────────────────────────────────

function ConversationEntry({ conv }: { conv: TicketConversation }) {
  const kindMeta = {
    customer_reply: { label: 'Cliente', color: 'primary' as const },
    agent_reply: { label: 'Agente', color: 'default' as const },
    private_note: { label: 'Nota interna', color: 'warning' as const },
  }[conv.kind] ?? { label: conv.kind, color: 'default' as const };

  const text = conv.body_text ?? '';
  return (
    <Box sx={{ border: '1px solid', borderColor: 'divider', borderRadius: 1, p: 1, bgcolor: conv.kind === 'customer_reply' ? 'action.hover' : 'transparent' }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 0.5 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
          <Chip label={kindMeta.label} size="small" color={kindMeta.color} />
          {conv.from_email ? <Typography variant="caption" color="text.secondary">{conv.from_email}</Typography> : null}
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
        {showHistory ? previous.map((conv) => <ConversationEntry key={conv.id} conv={conv} />) : null}
        {last ? <ConversationEntry conv={last} /> : null}
      </Box>
    </Box>
  );
}

function TicketContextPanel({ ticketId }: { ticketId: string }) {
  const [ticket, setTicket] = useState<TicketDetailResponse | null>(null);
  const [conversations, setConversations] = useState<TicketConversation[]>([]);
  const [loading, setLoading] = useState(false);
  // Collapsed by default: the editor is the focus of the review; the reviewer
  // expands the ticket context only when they need it.
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      try {
        const [ticketRes, convsRes] = await Promise.all([getTicket(ticketId), getTicketConversations(ticketId)]);
        if (!cancelled) {
          setTicket(ticketRes);
          setConversations(convsRes.items.slice(-6));
        }
      } catch { /* degrades gracefully */ } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void load();
    return () => { cancelled = true; };
  }, [ticketId]);

  const t = ticket?.ticket;
  const description = t ? getDescription(t) : '';
  const publicConvs = conversations.filter((c) => !c.private);

  return (
    <Accordion expanded={expanded} onChange={(_e, v) => setExpanded(v)} disableGutters elevation={0}
      sx={{ border: '1px solid', borderColor: 'divider', borderRadius: 1, '&:before': { display: 'none' } }}>
      <AccordionSummary expandIcon={<ExpandMoreIcon />} sx={{ minHeight: 44, '& .MuiAccordionSummary-content': { my: 0.75 } }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
          {loading && !t ? (
            <>
              <CircularProgress size={14} />
              <Typography variant="caption" color="text.secondary">Cargando contexto del ticket…</Typography>
            </>
          ) : t ? (
            <>
              <Typography variant="subtitle2" sx={{ fontWeight: 600 }}>#{t.id} — {t.subject}</Typography>
              <Chip label={t.status} size="small" />
              <Chip label={t.priority} size="small" variant="outlined" />
              {t.requester?.name ? (
                <Tooltip title={t.requester.email ?? ''}><Typography variant="caption" color="text.secondary">{t.requester.name}</Typography></Tooltip>
              ) : null}
            </>
          ) : (
            <Typography variant="caption" color="text.secondary">Contexto del ticket</Typography>
          )}
        </Box>
      </AccordionSummary>
      <AccordionDetails sx={{ pt: 0 }}>
        {description ? (
          <Box sx={{ mb: 2 }}>
            <Typography variant="caption" color="text.secondary" display="block" sx={{ mb: 0.5 }}>Descripción</Typography>
            <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>{description}</Typography>
          </Box>
        ) : null}
        {publicConvs.length > 0 ? <ConversationThread conversations={publicConvs} /> : null}
      </AccordionDetails>
    </Accordion>
  );
}

// ─── payload editors ─────────────────────────────────────────────────────────

function ClientField({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  const [options, setOptions] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    getPersonalListClients()
      .then((response) => {
        if (!cancelled) setOptions(response.clients);
      })
      .catch(() => null)
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // No fixed options configured (or still loading/failed): fall back to plain
  // free text instead of an empty, useless dropdown.
  if (!loading && options.length === 0) {
    return (
      <TextField
        label="Cliente"
        size="small"
        fullWidth
        value={value}
        onChange={(e) => onChange(e.target.value)}
      />
    );
  }

  return (
    <Autocomplete
      freeSolo
      size="small"
      loading={loading}
      options={options}
      value={value}
      onChange={(_, newValue) => onChange(newValue ?? '')}
      onInputChange={(_, newValue) => onChange(newValue)}
      renderInput={(params) => (
        <TextField
          {...params}
          label="Cliente"
          helperText="Selecciona de la lista de ClickUp o escribe para buscar"
          InputProps={{
            ...params.InputProps,
            endAdornment: (
              <>
                {loading ? <CircularProgress size={16} /> : null}
                {params.InputProps.endAdornment}
              </>
            ),
          }}
        />
      )}
    />
  );
}

function TimeEntryFields({ payload, onChange }: { payload: Record<string, unknown>; onChange: (k: string, v: string) => void }) {
  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
      <TextField label="Tarea" size="small" fullWidth value={String(payload.task_name ?? '')} onChange={(e) => onChange('task_name', e.target.value)} />
      <ClientField value={String(payload.client_name ?? '')} onChange={(v) => onChange('client_name', v)} />
      <Box sx={{ display: 'flex', gap: 1.5, flexWrap: 'wrap' }}>
        <TextField label="Inicio" size="small" sx={{ flex: 1, minWidth: 180 }} value={String(payload.start_datetime ?? '')} onChange={(e) => onChange('start_datetime', e.target.value)} helperText="YYYY-MM-DDTHH:MM" />
        <TextField label="Fin" size="small" sx={{ flex: 1, minWidth: 180 }} value={String(payload.end_datetime ?? '')} onChange={(e) => onChange('end_datetime', e.target.value)} helperText="YYYY-MM-DDTHH:MM" />
      </Box>
      <TextField label="Descripción" size="small" fullWidth multiline rows={2} value={String(payload.description ?? '')} onChange={(e) => onChange('description', e.target.value)} />
    </Box>
  );
}

function ReplyFields({ payload, helperText, onChange }: { payload: Record<string, unknown>; helperText?: string; onChange: (k: string, v: string) => void }) {
  return (
    <TextField label="Respuesta al cliente" size="small" fullWidth multiline rows={6}
      value={String(payload.body ?? '')} onChange={(e) => onChange('body', e.target.value)}
      helperText={helperText ?? 'Texto que se enviará públicamente al cliente en Freshservice.'} />
  );
}

const USER_STORY_FIELDS: Array<{ key: string; label: string; rows: number; half?: boolean }> = [
  { key: 'title', label: 'Título de la tarea', rows: 1 },
  { key: 'description', label: 'Descripción', rows: 3 },
  { key: 'user_story_statement', label: 'User story', rows: 2 },
  { key: 'functional_description', label: 'Descripción funcional', rows: 3 },
  { key: 'acceptance_criteria_in_gerkin', label: 'Criterios de aceptación (Gherkin)', rows: 4 },
  { key: 'constraints', label: 'Restricciones técnicas', rows: 2 },
  { key: 'out_of_scope', label: 'Fuera de alcance', rows: 2 },
  { key: 'requested_by', label: 'Solicitado por', rows: 1 },
];

function UserStoryEditor({ payload, onChange }: { payload: Record<string, unknown>; onChange: (k: string, v: unknown) => void }) {
  const story = payload.user_story;
  const storyObj: Record<string, string> = typeof story === 'object' && story !== null ? (story as Record<string, string>) : {};

  function handleFieldChange(key: string, value: string) {
    onChange('user_story', { ...storyObj, [key]: value });
  }

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      <Typography variant="caption" color="text.secondary">
        Revisa y ajusta la user story antes de crear la tarea en ClickUp. Los cambios se guardan al aprobar.
      </Typography>
      {USER_STORY_FIELDS.map(({ key, label, rows }) => (
        <TextField
          key={key}
          label={label}
          size="small"
          fullWidth
          multiline={rows > 1}
          rows={rows > 1 ? rows : undefined}
          value={storyObj[key] ?? ''}
          onChange={(e) => handleFieldChange(key, e.target.value)}
        />
      ))}
    </Box>
  );
}

function LinkTaskFields({ payload, onChange }: { payload: Record<string, unknown>; onChange: (k: string, v: string) => void }) {
  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
      <TextField label="URL de la tarea en ClickUp" size="small" fullWidth value={String(payload.task_url ?? '')} onChange={(e) => onChange('task_url', e.target.value)} helperText="URL completa de la tarea de ClickUp existente." />
      <TextField label="Respuesta al cliente (opcional)" size="small" fullWidth multiline rows={4} value={String(payload.body ?? '')} onChange={(e) => onChange('body', e.target.value)} helperText="Si está vacío, no se enviará reply al cliente." />
    </Box>
  );
}

function ActionPayloadEditor({ action, payload, onFieldChange }: {
  action: AssistantAction;
  payload: Record<string, unknown>;
  onFieldChange: (k: string, v: unknown) => void;
}) {
  if (action.action_type === 'save_time_entry') {
    return <TimeEntryFields payload={payload} onChange={(k, v) => onFieldChange(k, v)} />;
  }
  if (action.action_type === 'reply_freshservice_ticket' || action.action_type === 'request_info_freshservice_ticket') {
    const helperText = action.action_type === 'request_info_freshservice_ticket'
      ? 'Mensaje público al cliente. El ticket pasará a "esperando respuesta de tercero".'
      : undefined;
    return <ReplyFields payload={payload} helperText={helperText} onChange={(k, v) => onFieldChange(k, v)} />;
  }
  if (action.action_type === 'send_ticket_to_backlog') {
    return (
      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
        <UserStoryEditor payload={payload} onChange={(k, v) => onFieldChange(k, v)} />
        <ReplyFields payload={payload} helperText="Mensaje al cliente. El enlace a ClickUp se añadirá al final al crear la tarea." onChange={(k, v) => onFieldChange(k, v)} />
      </Box>
    );
  }
  if (action.action_type === 'prepare_clickup_us') {
    return <UserStoryEditor payload={payload} onChange={(k, v) => onFieldChange(k, v)} />;
  }
  if (action.action_type === 'link_existing_clickup_task') {
    return <LinkTaskFields payload={payload} onChange={(k, v) => onFieldChange(k, v)} />;
  }
  return null;
}

// ─── main review component ─────────────────────────────────────────────────────

export function actionIsActionable(action: AssistantAction): boolean {
  // Failed actions are actionable too: nothing succeeded on the failed attempt
  // (the backend allows re-approving them), so the user can fix the payload and retry.
  return action.status === 'proposed' || action.status === 'failed';
}

interface ActionReviewProps {
  action: AssistantAction;
  onDone?: (updated: AssistantAction) => void;
}

/**
 * Render the full review surface for a pending action: optional ticket context,
 * the editable payload, and approve/reject controls.
 *
 * Designed to live inside a wide container (drawer or page) so payloads with
 * many fields — notably ClickUp user stories — have room to breathe.
 */
export function ActionReview({ action: initialAction, onDone }: ActionReviewProps) {
  const [action, setAction] = useState(initialAction);
  const [editedPayload, setEditedPayload] = useState<Record<string, unknown> | null>(null);
  const [busy, setBusy] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Keep in sync when the parent swaps in a different action instance.
  useEffect(() => {
    setAction(initialAction);
    setEditedPayload(null);
    setErrorMsg(null);
  }, [initialAction]);

  const effectivePayload = editedPayload ?? action.payload;
  const hasEdits = editedPayload !== null;
  const isFailed = action.status === 'failed';
  const canAct = actionIsActionable(action);

  function handleFieldChange(key: string, value: unknown) {
    setEditedPayload((prev) => ({ ...(prev ?? action.payload), [key]: value }));
  }

  async function handleApprove() {
    setBusy(true);
    setErrorMsg(null);
    try {
      if (hasEdits) {
        await updateAssistantActionPayload(action.id, editedPayload!);
      }
      const updated = await approveAssistantAction(action.id);
      setAction(updated);
      setEditedPayload(null);
      onDone?.(updated);
    } catch (err) {
      setErrorMsg((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function handleReject() {
    setBusy(true);
    setErrorMsg(null);
    try {
      const updated = await rejectAssistantAction(action.id);
      setAction(updated);
      onDone?.(updated);
    } catch (err) {
      setErrorMsg((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const showTicketContext = action.ticket_id != null && TICKET_CONTEXT_TYPES.has(action.action_type);
  const statusColor = STATUS_COLORS[action.status] ?? 'default';

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      {action.description ? (
        <Typography variant="body2" color="text.secondary">{action.description}</Typography>
      ) : null}

      {hasEdits ? (
        <Box>
          <Chip label="Editado — se guardará al aprobar" size="small" color="warning" variant="outlined" />
        </Box>
      ) : null}

      {showTicketContext ? <TicketContextPanel ticketId={action.ticket_id!} /> : null}

      {canAct ? (
        <>
          {showTicketContext ? <Divider /> : null}
          <ActionPayloadEditor action={action} payload={effectivePayload} onFieldChange={handleFieldChange} />
        </>
      ) : null}

      {action.status === 'completed' ? (
        <Box sx={{ p: 1.5, bgcolor: 'success.50', borderRadius: 1, border: '1px solid', borderColor: 'success.200' }}>
          <Typography variant="body2" color="success.main" sx={{ fontWeight: 600 }}>Acción completada</Typography>
        </Box>
      ) : null}

      {action.status === 'rejected' ? (
        <Box sx={{ p: 1.5, bgcolor: 'action.hover', borderRadius: 1 }}>
          <Typography variant="body2" color="text.secondary">Acción rechazada</Typography>
        </Box>
      ) : null}

      {isFailed ? (
        <Box sx={{ p: 1.5, bgcolor: 'error.50', borderRadius: 1, border: '1px solid', borderColor: 'error.200' }}>
          <Typography variant="caption" color="error">
            {String((action.result as Record<string, unknown>)?.message ?? 'Error desconocido')}
          </Typography>
        </Box>
      ) : null}

      {errorMsg ? <Typography color="error" variant="caption">{errorMsg}</Typography> : null}

      {canAct ? (
        <>
          <Chip
            label={ACTION_TYPE_LABELS[action.action_type] ?? action.action_type}
            size="small"
            color={statusColor}
            variant="outlined"
            sx={{ alignSelf: 'flex-start' }}
          />
          <Box sx={{ display: 'flex', justifyContent: 'flex-end', gap: 1, mt: 1 }}>
            <Button color="error" startIcon={<CloseIcon />} disabled={busy} onClick={() => void handleReject()}>
              Rechazar
            </Button>
            <Button color="success" variant="contained"
              startIcon={busy ? <CircularProgress size={16} color="inherit" /> : <CheckIcon />}
              disabled={busy} onClick={() => void handleApprove()}>
              {isFailed ? 'Reintentar' : hasEdits ? 'Guardar y aprobar' : 'Aprobar'}
            </Button>
          </Box>
        </>
      ) : null}
    </Box>
  );
}
