import { useEffect, useState } from 'react';
import {
  Box,
  Button,
  Card,
  CardActions,
  CardContent,
  Chip,
  CircularProgress,
  Divider,
  TextField,
  Typography,
} from '@mui/material';
import CheckIcon from '@mui/icons-material/Check';
import CloseIcon from '@mui/icons-material/Close';
import { useActionsStore } from '../stores/actionsStore';
import { useChatStore } from '../stores/chatStore';
import {
  approveAssistantAction,
  listPendingAssistantActions,
  rejectAssistantAction,
  updateAssistantActionPayload,
} from '../api/assistant';
import type { AssistantAction } from '../types/assistant';

const actionTypeLabels: Record<string, string> = {
  prepare_clickup_task: 'Preparar tarea ClickUp',
  approve_clickup_task: 'Crear tarea ClickUp',
  save_time_entry: 'Imputar tiempo',
  reply_freshservice_ticket: 'Responder ticket',
};

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
  ticketId,
  onChange,
}: {
  payload: Record<string, unknown>;
  ticketId: string | null | undefined;
  onChange: (key: string, value: string) => void;
}) {
  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
      {ticketId ? (
        <Typography variant="caption" color="text.secondary">
          Ticket: #{ticketId}
        </Typography>
      ) : null}
      <TextField
        label="Respuesta al cliente"
        size="small"
        fullWidth
        multiline
        rows={6}
        value={String(payload.body ?? '')}
        onChange={(e) => onChange('body', e.target.value)}
        helperText="Texto que se enviará públicamente al cliente en Freshservice."
      />
    </Box>
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

  if (action.action_type === 'reply_freshservice_ticket') {
    return (
      <ReplyFields
        payload={payload}
        ticketId={action.ticket_id}
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

/**
 * Render the full pending actions page with inline payload editing.
 *
 * Parameters:
 *   None.
 *
 * Returns:
 *   JSX actions page.
 *
 * Edge cases:
 *   Payload edits are saved via PATCH before the approve POST executes.
 */
export function ActionsPage() {
  const { pendingActions, isLoading, error, setPendingActions, setLoading, setError, removeAction } = useActionsStore();
  const { updatePendingAction: updateChatPendingAction } = useChatStore();

  // Local edits: actionId → modified payload fields
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
