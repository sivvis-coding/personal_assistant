import { useEffect, useRef, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import {
  Badge,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle,
  Divider,
  Grid,
  IconButton,
  InputAdornment,
  Paper,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import SendIcon from '@mui/icons-material/Send';
import HistoryIcon from '@mui/icons-material/History';
import AddIcon from '@mui/icons-material/Add';
import DeleteIcon from '@mui/icons-material/Delete';
import TodayIcon from '@mui/icons-material/Today';
import ConfirmationNumberIcon from '@mui/icons-material/ConfirmationNumber';
import AssignmentIcon from '@mui/icons-material/Assignment';
import AccessTimeIcon from '@mui/icons-material/AccessTime';
import RefreshIcon from '@mui/icons-material/Refresh';
import ChevronLeftIcon from '@mui/icons-material/ChevronLeft';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import CalendarMonthIcon from '@mui/icons-material/CalendarMonth';
import { useChatStore } from '../stores/chatStore';
import {
  createAssistantConversation,
  deleteAssistantConversation,
  getAssistantConversation,
  listAssistantConversations,
  listPendingAssistantActions,
  streamAssistantMessage,
} from '../api/assistant';
import { useActionsStore } from '../stores/actionsStore';
import { ActionCard } from '../components/actions/ActionCard';
import { MarkdownContent } from '../components/chat/MarkdownContent';
import type { AssistantAction } from '../types/assistant';

// ─── capability cards shown on empty state ───────────────────────────────────

interface CapabilityCard {
  icon: React.ReactNode;
  title: string;
  description: string;
  color: string;
  examples: string[];
}

const CAPABILITIES: CapabilityCard[] = [
  {
    icon: <TodayIcon />,
    title: 'Revisión diaria',
    description: 'Analiza todos tus tickets y te dice qué necesita acción, qué falta pasar a ClickUp y qué puedes cerrar.',
    color: '#1976d2',
    examples: [
      'Revisa todo lo que tengo hoy',
      'Dame un resumen de mis tickets',
      '¿Qué tickets tienen el SLA en riesgo?',
    ],
  },
  {
    icon: <ConfirmationNumberIcon />,
    title: 'Gestión de tickets',
    description: 'Responde clientes, pide más información, resuelve tickets o ponlos en espera directamente desde aquí.',
    color: '#388e3c',
    examples: [
      'Contéstale al ticket #X que ya lo estamos revisando',
      'Pide más información en el ticket #X',
      'Cierra el ticket #X, el problema está resuelto',
    ],
  },
  {
    icon: <AssignmentIcon />,
    title: 'ClickUp',
    description: 'Crea tareas desde tickets, pasa varios al backlog de golpe o vincula tareas existentes sin duplicar.',
    color: '#7b1fa2',
    examples: [
      'Pasa el ticket #X al backlog de ClickUp',
      'Pasa todos los tickets sin tarea a ClickUp',
      'El ticket #X ya está en ClickUp como T-123, vincúlalos',
    ],
  },
  {
    icon: <AccessTimeIcon />,
    title: 'Imputar tiempo',
    description: 'Registra horas en ClickUp con lenguaje natural. Detecta el cliente automáticamente o te pregunta si no está claro.',
    color: '#f57c00',
    examples: [
      'Imputa 2h hoy a las 09:00 al cliente Acme por revisión',
      'Registra 45min en la tarea de soporte desde las 15:30',
      '¿Cuántas horas llevo esta semana?',
    ],
  },
];

// ─── helpers ─────────────────────────────────────────────────────────────────

function msgId(prefix: string, index: number): string {
  return `${prefix}-${index}-${Date.now()}`;
}

function generateTitle(text: string): string {
  const trimmed = text.trim();
  return trimmed.length > 40 ? `${trimmed.slice(0, 40)}...` : trimmed;
}

function formatTargetDate(isoDate: string): string {
  const [year, month, day] = isoDate.split('-').map(Number);
  return new Date(year, month - 1, day).toLocaleDateString('es-ES', {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  });
}

// ─── sub-components ──────────────────────────────────────────────────────────

function WelcomeScreen({ onExample }: { onExample: (text: string) => void }) {
  return (
    <Box sx={{ py: 4, px: 1 }}>
      <Box sx={{ textAlign: 'center', mb: 4 }}>
        <Typography variant="h5" fontWeight={600} gutterBottom>
          Asistente de soporte
        </Typography>
        <Typography variant="body1" color="text.secondary" sx={{ maxWidth: 520, mx: 'auto' }}>
          Gestiona tickets de Freshservice, crea tareas en ClickUp e imputa tiempo con lenguaje natural.
          Elige un ejemplo o escribe directamente.
        </Typography>
      </Box>

      <Grid container spacing={2}>
        {CAPABILITIES.map((cap) => (
          <Grid item xs={12} sm={6} key={cap.title}>
            <Card elevation={0} sx={{ height: '100%', border: '1px solid', borderColor: 'divider' }}>
              <CardContent sx={{ pb: 1 }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                  <Box sx={{ color: cap.color, display: 'flex' }}>{cap.icon}</Box>
                  <Typography variant="subtitle2" fontWeight={600}>{cap.title}</Typography>
                </Box>
                <Typography variant="caption" color="text.secondary" display="block" sx={{ mb: 1.5 }}>
                  {cap.description}
                </Typography>
                <Divider sx={{ mb: 1.5 }} />
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.75 }}>
                  {cap.examples.map((example) => (
                    <Box
                      key={example}
                      onClick={() => onExample(example)}
                      sx={{
                        cursor: 'pointer',
                        px: 1.5,
                        py: 0.75,
                        borderRadius: 1,
                        border: '1px solid',
                        borderColor: 'divider',
                        typography: 'body2',
                        color: 'text.secondary',
                        '&:hover': {
                          borderColor: cap.color,
                          color: cap.color,
                          bgcolor: 'action.hover',
                        },
                        transition: 'all 0.15s',
                      }}
                    >
                      "{example}"
                    </Box>
                  ))}
                </Box>
              </CardContent>
            </Card>
          </Grid>
        ))}
      </Grid>
    </Box>
  );
}

function InlineActions({ actions, onActionDone }: {
  actions: AssistantAction[];
  onActionDone: (updated: AssistantAction) => void;
}) {
  if (actions.length === 0) return null;
  return (
    <Box sx={{ mt: 1.5, display: 'flex', flexDirection: 'column', gap: 1 }}>
      {actions.map((action) => (
        <ActionCard key={action.id} action={action} onDone={onActionDone} />
      ))}
    </Box>
  );
}

// ─── actions panel (right column) ────────────────────────────────────────────

function ActionsPanel() {
  const { pendingActions, setPendingActions } = useActionsStore();
  const [refreshing, setRefreshing] = useState(false);
  const [collapsed, setCollapsed] = useState(false);

  async function handleRefresh() {
    setRefreshing(true);
    try {
      const actions = await listPendingAssistantActions();
      setPendingActions(actions);
    } catch { /* degrades gracefully */ } finally {
      setRefreshing(false);
    }
  }

  function handleActionDone(_updated: AssistantAction) {
    void listPendingAssistantActions().then(setPendingActions).catch(() => null);
  }

  if (collapsed) {
    return (
      <Box
        sx={{
          width: 44,
          flexShrink: 0,
          display: { xs: 'none', md: 'flex' },
          flexDirection: 'column',
          alignItems: 'center',
          pt: 1,
        }}
      >
        <Tooltip title={pendingActions.length > 0 ? `${pendingActions.length} acciones pendientes` : 'Acciones pendientes'} placement="left">
          <Badge badgeContent={pendingActions.length} color="primary" max={99} overlap="circular">
            <IconButton size="small" onClick={() => setCollapsed(false)}>
              <ChevronLeftIcon fontSize="small" />
            </IconButton>
          </Badge>
        </Tooltip>
      </Box>
    );
  }

  return (
    <Box
      sx={{
        width: 340,
        flexShrink: 0,
        display: { xs: 'none', md: 'flex' },
        flexDirection: 'column',
      }}
    >
      <Paper elevation={0} variant="outlined" sx={{ flex: 1, p: 2, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
        <Box sx={{ height: '100%', overflow: 'auto', display: 'flex', flexDirection: 'column' }}>
          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 1.5, flexShrink: 0 }}>
            <Badge badgeContent={pendingActions.length} color="primary" max={99}>
              <Typography variant="subtitle2" fontWeight={600} sx={{ pr: 1 }}>
                Acciones pendientes
              </Typography>
            </Badge>
            <Box sx={{ display: 'flex', alignItems: 'center' }}>
              <Tooltip title="Actualizar">
                <IconButton size="small" onClick={() => void handleRefresh()} disabled={refreshing}>
                  {refreshing ? <CircularProgress size={16} /> : <RefreshIcon fontSize="small" />}
                </IconButton>
              </Tooltip>
              <Tooltip title="Contraer">
                <IconButton size="small" onClick={() => setCollapsed(true)}>
                  <ChevronRightIcon fontSize="small" />
                </IconButton>
              </Tooltip>
            </Box>
          </Box>

          {pendingActions.length === 0 ? (
            <Box sx={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <Typography variant="body2" color="text.disabled" sx={{ fontStyle: 'italic' }}>
                Sin acciones pendientes
              </Typography>
            </Box>
          ) : (
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
              {pendingActions.map((action) => (
                <ActionCard key={action.id} action={action} onDone={handleActionDone} />
              ))}
            </Box>
          )}
        </Box>
      </Paper>
    </Box>
  );
}

// ─── main page ───────────────────────────────────────────────────────────────

export function ChatPage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const {
    conversationId,
    targetDate,
    conversations,
    messages,
    isLoading,
    isSubmitting,
    error,
    awaitingClientConfirmation,
    candidateClients,
    setConversationId,
    setTargetDate,
    addMessage,
    updateMessage,
    appendToMessage,
    setMessages,
    setSubmitting,
    setError,
    setAwaitingClientConfirmation,
    setConversations,
    resetChat,
  } = useChatStore();

  const { setPendingActions } = useActionsStore();
  const [messageActionOverrides, setMessageActionOverrides] = useState<Record<string, Record<string, AssistantAction>>>({});
  const [inputValue, setInputValue] = useState('');
  const [agentModel, setAgentModel] = useState<string | null>(null);
  const [showHistory, setShowHistory] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);
  const [loadingConvId, setLoadingConvId] = useState<string | null>(null);

  // Arrived from the hours calendar with "?date=YYYY-MM-DD": start a fresh
  // conversation scoped to that day so the user only needs to describe the
  // work/hours, not the date itself. The query param is stripped right after
  // so reloading the page doesn't recreate a conversation every time.
  useEffect(() => {
    const dateParam = searchParams.get('date');
    if (!dateParam) return;
    setSearchParams({}, { replace: true });
    resetChat();
    createAssistantConversation(dateParam)
      .then((conv) => {
        setConversationId(conv.conversation_id);
        setTargetDate(dateParam);
      })
      .catch((caught: Error) => setError(caught.message));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';
    fetch(`${BASE}/health/config`)
      .then((r) => r.json())
      .then((data) => setAgentModel(data?.openai?.model ?? null))
      .catch(() => null);
  }, []);

  // Load conversation list for the history sidebar
  useEffect(() => {
    listAssistantConversations()
      .then((list) => setConversations(list.map((c) => ({
        id: c.id,
        title: c.title,
        lastMessage: '',
        messageCount: c.message_count,
        updatedAt: new Date(c.updated_at),
      }))))
      .catch(() => null);
  }, [setConversations]);

  async function loadConversation(id: string) {
    if (loadingConvId) return;
    setLoadingConvId(id);
    try {
      const detail = await getAssistantConversation(id);
      setConversationId(id);
      setTargetDate(detail.target_date ?? null);
      setMessages(
        detail.messages.flatMap((m, i) => [
          { id: `h-u-${i}`, role: 'user' as const, text: m.user_message, actions: [], suggestions: [], timestamp: new Date(m.created_at) },
          { id: `h-a-${i}`, role: 'assistant' as const, text: m.assistant_answer, actions: [], suggestions: [], timestamp: new Date(m.created_at) },
        ])
      );
    } catch { /* ignore */ } finally {
      setLoadingConvId(null);
    }
  }

  async function confirmAndDelete() {
    if (!confirmDeleteId) return;
    const id = confirmDeleteId;
    setConfirmDeleteId(null);
    setDeletingId(id);
    try {
      await deleteAssistantConversation(id);
      setConversations((current) => current.filter((c) => c.id !== id));
      if (conversationId === id) resetChat();
    } catch { /* ignore */ } finally {
      setDeletingId(null);
    }
  }

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  useEffect(() => {
    listPendingAssistantActions().then(setPendingActions).catch(() => null);
  }, [setPendingActions]);

  function handleActionDone(messageKey: string, updated: AssistantAction) {
    setMessageActionOverrides((prev) => ({
      ...prev,
      [messageKey]: { ...(prev[messageKey] ?? {}), [updated.id]: updated },
    }));
    listPendingAssistantActions().then(setPendingActions).catch(() => null);
  }

  function getMessageActions(msg: { id: string; actions: AssistantAction[] }): AssistantAction[] {
    const overrides = messageActionOverrides[msg.id] ?? {};
    return msg.actions.map((a) => overrides[a.id] ?? a);
  }

  function fillInput(text: string) {
    setInputValue(text);
    inputRef.current?.focus();
  }

  async function submitMessage(text: string): Promise<void> {
    if (!text.trim()) return;

    setSubmitting(true);
    setError(null);
    setAwaitingClientConfirmation(false);
    setInputValue('');

    const userMsgId = msgId('user', messages.length);
    const assistantMsgId = msgId('assistant', messages.length + 1);

    addMessage({ id: userMsgId, role: 'user', text: text.trim(), actions: [], suggestions: [], timestamp: new Date() });
    addMessage({ id: assistantMsgId, role: 'assistant', text: '', actions: [], suggestions: [], timestamp: new Date(), streaming: true });

    try {
      let activeId = conversationId;
      if (!activeId) {
        const conv = await createAssistantConversation();
        activeId = conv.conversation_id;
        setConversationId(activeId);
      }

      await streamAssistantMessage(activeId, text.trim(), {
        onToken: (chunk) => appendToMessage(assistantMsgId, chunk),
        onDone: (response) => {
          updateMessage(assistantMsgId, {
            text: response.answer,
            actions: response.proposed_actions,
            suggestions: response.next_suggestions ?? [],
            streaming: false,
          });
          if (response.needs_clarification) setAwaitingClientConfirmation(true);
          listPendingAssistantActions().then(setPendingActions).catch(() => null);
        },
        onError: (msg) => {
          updateMessage(assistantMsgId, { text: `Error: ${msg}`, streaming: false });
          setError(msg);
        },
      });

      setConversations((current) => {
        if (current.some((c) => c.id === activeId)) return current;
        return [{ id: activeId!, title: generateTitle(text), lastMessage: text, messageCount: 2, updatedAt: new Date() }, ...current];
      });
    } catch (caught) {
      updateMessage(assistantMsgId, { text: `Error: ${(caught as Error).message}`, streaming: false });
      setError((caught as Error).message);
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
    <Box sx={{ display: 'flex', height: 'calc(100vh - 120px)', gap: 0 }}>

      {/* ── history sidebar ── */}
      {showHistory && (
        <Box sx={{
          width: 260,
          flexShrink: 0,
          display: 'flex',
          flexDirection: 'column',
          borderRight: '1px solid',
          borderColor: 'divider',
          bgcolor: 'background.paper',
          mr: 2,
          overflow: 'hidden',
        }}>
          {/* sidebar header */}
          <Box sx={{ px: 1.5, py: 1, display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderBottom: '1px solid', borderColor: 'divider', flexShrink: 0 }}>
            <Typography variant="subtitle2" fontWeight={600}>Conversaciones</Typography>
            <Tooltip title="Nueva conversación">
              <IconButton size="small" onClick={() => { resetChat(); setShowHistory(false); }}>
                <AddIcon fontSize="small" />
              </IconButton>
            </Tooltip>
          </Box>

          {/* conversation list */}
          <Box sx={{ flex: 1, overflow: 'auto' }}>
            {conversations.length === 0 ? (
              <Typography variant="body2" color="text.disabled" sx={{ p: 2, fontStyle: 'italic' }}>
                Sin conversaciones guardadas
              </Typography>
            ) : (
              conversations.map((conv) => (
                <Box
                  key={conv.id}
                  onClick={() => void loadConversation(conv.id)}
                  sx={{
                    display: 'flex',
                    alignItems: 'center',
                    px: 1.5,
                    py: 1,
                    cursor: 'pointer',
                    bgcolor: conversationId === conv.id ? 'action.selected' : 'transparent',
                    '&:hover': { bgcolor: conversationId === conv.id ? 'action.selected' : 'action.hover' },
                    '&:hover .del-btn': { opacity: 1 },
                    borderBottom: '1px solid',
                    borderColor: 'divider',
                  }}
                >
                  {loadingConvId === conv.id ? (
                    <CircularProgress size={14} sx={{ mr: 1, flexShrink: 0 }} />
                  ) : null}
                  <Box sx={{ flex: 1, minWidth: 0 }}>
                    <Typography variant="body2" noWrap fontWeight={conversationId === conv.id ? 600 : 400}>
                      {conv.title || 'Sin título'}
                    </Typography>
                    <Typography variant="caption" color="text.disabled" display="block">
                      {conv.updatedAt.toLocaleDateString('es-ES', { day: '2-digit', month: 'short' })}
                      {' · '}{conv.messageCount} msgs
                    </Typography>
                  </Box>
                  <IconButton
                    className="del-btn"
                    size="small"
                    onClick={(e) => { e.stopPropagation(); setConfirmDeleteId(conv.id); }}
                    disabled={deletingId === conv.id}
                    sx={{ opacity: 0, transition: 'opacity 0.15s', ml: 0.5, flexShrink: 0, color: 'error.main' }}
                  >
                    {deletingId === conv.id
                      ? <CircularProgress size={14} />
                      : <DeleteIcon fontSize="small" />}
                  </IconButton>
                </Box>
              ))
            )}
          </Box>
        </Box>
      )}

      {/* ── center+right columns ── */}
      <Box sx={{ flex: 1, minWidth: 0, display: 'flex', gap: 2 }}>

      {/* ── chat column ── */}
      <Box sx={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column' }}>

        {/* ── top bar ── */}
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1.5 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
            <Typography variant="body2" color="text.secondary" sx={{ fontFamily: 'monospace', fontSize: 11 }}>
              {conversationId ? `#${conversationId.slice(-8)}` : 'sin conversación'}
            </Typography>
            {targetDate && (
              <Tooltip title="Cuéntame la actividad y las horas: la fecha ya está fijada. Clic para quitarla.">
                <Chip
                  icon={<CalendarMonthIcon />}
                  label={`Imputando: ${formatTargetDate(targetDate)}`}
                  size="small"
                  color="primary"
                  variant="outlined"
                  onDelete={() => resetChat()}
                />
              </Tooltip>
            )}
            {agentModel && (
              <Typography variant="body2" color="text.disabled" sx={{ fontFamily: 'monospace', fontSize: 11 }}>
                {agentModel}
              </Typography>
            )}
          </Box>
          <Box sx={{ display: 'flex', gap: 0.5 }}>
            {!showHistory && (
              <Tooltip title="Nueva conversación">
                <IconButton size="small" onClick={() => resetChat()}>
                  <AddIcon fontSize="small" />
                </IconButton>
              </Tooltip>
            )}
            <Tooltip title={showHistory ? 'Cerrar historial' : 'Historial de conversaciones'}>
              <IconButton size="small" onClick={() => setShowHistory((s) => !s)} color={showHistory ? 'primary' : 'default'}>
                <HistoryIcon fontSize="small" />
              </IconButton>
            </Tooltip>
          </Box>
        </Box>

        {/* ── message area ── */}
        <Paper sx={{ flexGrow: 1, overflow: 'auto', p: 2, mb: 1.5, bgcolor: 'grey.50' }} elevation={0} variant="outlined">
          {messages.length === 0 ? (
            <WelcomeScreen onExample={(text) => { fillInput(text); }} />
          ) : (
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
              {messages.map((message) => {
                const isUser = message.role === 'user';
                const currentActions = getMessageActions(message);
                return (
                  <Box key={message.id}>
                    {/* bubble */}
                    <Box sx={{
                      display: 'flex',
                      justifyContent: isUser ? 'flex-end' : 'flex-start',
                    }}>
                      <Box sx={{
                        maxWidth: isUser ? '70%' : '90%',
                        bgcolor: isUser ? 'primary.main' : 'background.paper',
                        color: isUser ? 'primary.contrastText' : 'text.primary',
                        borderRadius: isUser ? '16px 16px 4px 16px' : '16px 16px 16px 4px',
                        px: 2,
                        py: 1.5,
                        boxShadow: 1,
                      }}>
                        {message.streaming && message.text === '' ? (
                          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }}>
                            <CircularProgress size={14} />
                            <Typography variant="body2" color="text.secondary">Pensando…</Typography>
                          </Box>
                        ) : (
                          <>
                            <MarkdownContent content={message.text} invert={isUser} />
                            {message.streaming && (
                              <Box component="span" sx={{
                                display: 'inline-block',
                                width: '2px',
                                height: '1em',
                                bgcolor: 'text.primary',
                                ml: 0.25,
                                verticalAlign: 'text-bottom',
                                animation: 'blink 1s step-end infinite',
                                '@keyframes blink': { '0%, 100%': { opacity: 1 }, '50%': { opacity: 0 } },
                              }} />
                            )}
                          </>
                        )}
                        {!message.streaming && (
                          <Typography variant="caption" sx={{ display: 'block', mt: 0.5, opacity: 0.6, textAlign: isUser ? 'right' : 'left' }}>
                            {message.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                          </Typography>
                        )}
                      </Box>
                    </Box>

                    {/* suggestion chips */}
                    {!isUser && message.suggestions.length > 0 ? (
                      <Box sx={{ display: 'flex', gap: 0.75, flexWrap: 'wrap', mt: 1 }}>
                        {message.suggestions.map((s) => (
                          <Chip
                            key={s}
                            label={s}
                            size="small"
                            variant="outlined"
                            onClick={() => fillInput(s)}
                            clickable
                          />
                        ))}
                      </Box>
                    ) : null}

                    {/* inline action cards — visible on mobile (md panel hidden) */}
                    {!isUser && currentActions.length > 0 ? (
                      <Box sx={{ display: { xs: 'block', md: 'none' } }}>
                        <InlineActions
                          actions={currentActions}
                          onActionDone={(updated) => handleActionDone(message.id, updated)}
                        />
                      </Box>
                    ) : null}
                  </Box>
                );
              })}

              {/* streaming state is shown inside the bubble — no extra spinner needed */}
            </Box>
          )}
          <div ref={messagesEndRef} />
        </Paper>

        {/* ── client confirmation chips ── */}
        {awaitingClientConfirmation && candidateClients.length > 0 ? (
          <Box sx={{ mb: 1.5 }}>
            <Typography variant="caption" color="text.secondary" gutterBottom>Elige el cliente:</Typography>
            <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', mt: 0.5 }}>
              {candidateClients.map((client) => (
                <Chip key={client} label={client} onClick={() => void submitMessage(client)} clickable color="primary" size="small" />
              ))}
            </Box>
          </Box>
        ) : null}

        {/* ── input bar ── */}
        <Box sx={{ display: 'flex', gap: 1, alignItems: 'flex-end' }}>
          <TextField
            inputRef={inputRef}
            fullWidth
            multiline
            maxRows={4}
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            placeholder={awaitingClientConfirmation ? 'Escribe el nombre del cliente…' : 'Escribe tu solicitud o elige un ejemplo arriba…'}
            disabled={isSubmitting}
            variant="outlined"
            size="small"
            sx={{ bgcolor: 'background.paper' }}
            onKeyDown={(event) => {
              if (event.key === 'Enter' && !event.shiftKey) {
                event.preventDefault();
                void submitMessage(inputValue);
              }
            }}
            InputProps={{
              endAdornment: (
                <InputAdornment position="end">
                  <Typography variant="caption" color="text.disabled" sx={{ mr: 0.5 }}>↵</Typography>
                </InputAdornment>
              ),
            }}
          />
          <IconButton
            color="primary"
            disabled={isSubmitting}
            sx={{ bgcolor: 'primary.main', color: 'white', borderRadius: 2, '&:hover': { bgcolor: 'primary.dark' }, '&:disabled': { bgcolor: 'action.disabledBackground' } }}
            onClick={() => void submitMessage(inputValue)}
          >
            <SendIcon />
          </IconButton>
        </Box>

        {error ? <Typography color="error" variant="caption" sx={{ mt: 0.5 }}>{error}</Typography> : null}
      </Box>

      {/* ── right column: pending actions panel ── */}
      <ActionsPanel />

      </Box> {/* end center+right wrapper */}

      {/* ── delete confirmation dialog ── */}
      <Dialog open={confirmDeleteId !== null} onClose={() => setConfirmDeleteId(null)} maxWidth="xs" fullWidth>
        <DialogTitle>Borrar conversación</DialogTitle>
        <DialogContent>
          <DialogContentText>
            ¿Estás seguro de que quieres borrar esta conversación? Esta acción no se puede deshacer.
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setConfirmDeleteId(null)}>Cancelar</Button>
          <Button color="error" variant="contained" onClick={() => void confirmAndDelete()}>
            Borrar
          </Button>
        </DialogActions>
      </Dialog>

    </Box>
  );
}
