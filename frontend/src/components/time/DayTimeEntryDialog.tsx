import { useEffect, useRef, useState } from 'react';
import {
  Box,
  Button,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  IconButton,
  Paper,
  TextField,
  Typography,
} from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import SendIcon from '@mui/icons-material/Send';
import { createAssistantConversation, deleteAssistantConversation, sendAssistantMessage } from '../../api/assistant';
import { ActionCard } from '../actions/ActionCard';
import type { AssistantAction } from '../../types/assistant';

interface Turn {
  id: string;
  userText: string;
  answer: string;
  actions: AssistantAction[];
}

function formatDialogDate(isoDate: string): string {
  const [year, month, day] = isoDate.split('-').map(Number);
  return new Date(year, month - 1, day).toLocaleDateString('es-ES', {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  });
}

interface DayTimeEntryDialogProps {
  date: string | null;
  onClose: () => void;
  onActionSettled?: () => void;
}

/**
 * Render a lightweight, single-purpose popup to log hours for one specific day.
 *
 * Unlike the full assistant chat, this does not persist as browsable chat
 * history: a throwaway conversation is created while the popup is open and
 * deleted as soon as it closes — only the resulting ClickUp actions live on.
 *
 * Parameters:
 *   date: ISO day (YYYY-MM-DD) to log hours for, or null to keep the dialog closed.
 *   onClose: Called when the popup should close (backdrop click, X button, or "Cerrar").
 *   onActionSettled: Called whenever a proposed action is approved/rejected, so the
 *     caller (the calendar) can refresh its hours without waiting for the popup to close.
 *
 * Returns:
 *   JSX dialog component.
 *
 * Edge cases:
 *   If conversation creation fails (e.g. no personal list configured), the error
 *   is shown inline and the input is disabled.
 */
export function DayTimeEntryDialog({ date, onClose, onActionSettled }: DayTimeEntryDialogProps) {
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [initializing, setInitializing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const conversationIdRef = useRef<string | null>(null);

  useEffect(() => {
    if (!date) return;
    setTurns([]);
    setInputValue('');
    setError(null);
    setInitializing(true);
    createAssistantConversation(date)
      .then((conv) => {
        setConversationId(conv.conversation_id);
        conversationIdRef.current = conv.conversation_id;
      })
      .catch((caught: Error) => setError(caught.message))
      .finally(() => setInitializing(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [date]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [turns]);

  function handleClose(): void {
    const idToDelete = conversationIdRef.current;
    conversationIdRef.current = null;
    setConversationId(null);
    if (idToDelete) {
      void deleteAssistantConversation(idToDelete).catch(() => null);
    }
    onClose();
  }

  async function handleSend(): Promise<void> {
    const text = inputValue.trim();
    if (!text || !conversationId) return;

    setSubmitting(true);
    setError(null);
    setInputValue('');
    try {
      const response = await sendAssistantMessage(conversationId, text);
      setTurns((prev) => [
        ...prev,
        { id: `turn-${prev.length}-${Date.now()}`, userText: text, answer: response.answer, actions: response.proposed_actions },
      ]);
    } catch (caught) {
      setError((caught as Error).message);
      setInputValue(text);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Dialog open={date !== null} onClose={handleClose} maxWidth="sm" fullWidth>
      <DialogTitle sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <Box>
          <Typography variant="h6" component="div" sx={{ textTransform: 'capitalize' }}>
            {date ? formatDialogDate(date) : ''}
          </Typography>
          <Typography variant="caption" color="text.secondary">
            Cuéntame qué hiciste y cuánto tiempo — la fecha ya está fijada
          </Typography>
        </Box>
        <IconButton onClick={handleClose} size="small">
          <CloseIcon />
        </IconButton>
      </DialogTitle>

      <DialogContent dividers sx={{ minHeight: 240, display: 'flex', flexDirection: 'column', gap: 2 }}>
        {initializing ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
            <CircularProgress size={28} />
          </Box>
        ) : (
          <>
            {turns.length === 0 ? (
              <Typography variant="body2" color="text.secondary" sx={{ fontStyle: 'italic' }}>
                Ej. "2h revisando tickets y 1h en una reunión con el cliente Acme"
              </Typography>
            ) : null}

            {turns.map((turn) => (
              <Box key={turn.id} sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                <Paper variant="outlined" sx={{ p: 1.25, bgcolor: 'action.hover', alignSelf: 'flex-end', maxWidth: '85%' }}>
                  <Typography variant="body2">{turn.userText}</Typography>
                </Paper>
                <Typography variant="body2" color="text.secondary" sx={{ whiteSpace: 'pre-wrap' }}>
                  {turn.answer}
                </Typography>
                {turn.actions.map((action) => (
                  <ActionCard key={action.id} action={action} onDone={() => onActionSettled?.()} />
                ))}
              </Box>
            ))}
            <div ref={bottomRef} />
          </>
        )}

        {error ? <Typography color="error" variant="caption">{error}</Typography> : null}
      </DialogContent>

      <DialogActions sx={{ p: 2, gap: 1 }}>
        <TextField
          autoFocus
          fullWidth
          size="small"
          placeholder="Describe la actividad y las horas…"
          value={inputValue}
          disabled={!conversationId || submitting}
          onChange={(e) => setInputValue(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              void handleSend();
            }
          }}
        />
        <Button
          variant="contained"
          endIcon={submitting ? <CircularProgress size={16} color="inherit" /> : <SendIcon />}
          disabled={!conversationId || submitting || !inputValue.trim()}
          onClick={() => void handleSend()}
        >
          Enviar
        </Button>
      </DialogActions>
    </Dialog>
  );
}
