import { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box,
  Button,
  Checkbox,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControl,
  FormControlLabel,
  IconButton,
  InputLabel,
  MenuItem,
  Paper,
  Select,
  Snackbar,
  Alert,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TableSortLabel,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import FilterListIcon from '@mui/icons-material/FilterList';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import SyncIcon from '@mui/icons-material/Sync';
import AddCircleOutlineIcon from '@mui/icons-material/AddCircleOutline';
import ReplyIcon from '@mui/icons-material/Reply';
import TaskIcon from '@mui/icons-material/Task';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';
import HelpOutlineIcon from '@mui/icons-material/HelpOutline';
import { listTickets } from '../api/tickets';
import { createAssistantAction } from '../api/assistant';
import type { AssistantActionType } from '../types/assistant';
import type { SlaStatus, Ticket, TicketPriority, TicketStatus } from '../types/ticket';

// ─── types ────────────────────────────────────────────────────────────────────

interface Filters {
  search: string;
  statuses: TicketStatus[];
  priorities: TicketPriority[];
  includeClosed: boolean;
  onlyOverdue: boolean;
  onlyWithoutTask: boolean;
}

type SortField = 'id' | 'subject' | 'status' | 'priority' | 'requester';
type SortDirection = 'asc' | 'desc';

type QuickActionType = 'reply' | 'task' | 'resolve' | 'request_info';

interface QuickActionState {
  ticket: Ticket;
  type: QuickActionType;
}

// ─── color helpers ────────────────────────────────────────────────────────────

const statusOrder: TicketStatus[] = ['open', 'pending', 'waiting on customer', 'waiting on third party', 'resolved', 'closed', 'unknown'];
const priorityOrder: TicketPriority[] = ['urgent', 'high', 'medium', 'low', 'unknown'];

function statusColor(status: TicketStatus): 'success' | 'warning' | 'info' | 'default' | 'error' {
  switch (status) {
    case 'open': return 'success';
    case 'pending':
    case 'waiting on customer':
    case 'waiting on third party': return 'warning';
    case 'resolved': return 'info';
    case 'closed': return 'default';
    default: return 'error';
  }
}

function priorityColor(priority: TicketPriority): 'error' | 'warning' | 'info' | 'default' {
  switch (priority) {
    case 'urgent': return 'error';
    case 'high': return 'warning';
    case 'medium': return 'info';
    default: return 'default';
  }
}

function slaColor(status: SlaStatus): 'success' | 'warning' | 'error' | 'default' {
  switch (status) {
    case 'ok': return 'success';
    case 'at_risk': return 'warning';
    case 'breached': return 'error';
    default: return 'default';
  }
}

// ─── quick action dialog ──────────────────────────────────────────────────────

const ACTION_META: Record<QuickActionType, { label: string; icon: React.ReactNode; actionType: AssistantActionType; hasBody: boolean; bodyLabel: string; bodyPlaceholder: string }> = {
  reply: {
    label: 'Responder al cliente',
    icon: <ReplyIcon fontSize="small" />,
    actionType: 'reply_freshservice_ticket',
    hasBody: true,
    bodyLabel: 'Cuerpo de la respuesta',
    bodyPlaceholder: 'Escribe la respuesta pública que verá el cliente...',
  },
  task: {
    label: 'Crear tarea ClickUp',
    icon: <TaskIcon fontSize="small" />,
    actionType: 'send_ticket_to_backlog',
    hasBody: true,
    bodyLabel: 'Respuesta al cliente (opcional)',
    bodyPlaceholder: 'Mensaje al cliente. El enlace a ClickUp se añadirá al final...',
  },
  resolve: {
    label: 'Marcar como resuelto',
    icon: <CheckCircleOutlineIcon fontSize="small" />,
    actionType: 'resolve_freshservice_ticket',
    hasBody: false,
    bodyLabel: '',
    bodyPlaceholder: '',
  },
  request_info: {
    label: 'Pedir información',
    icon: <HelpOutlineIcon fontSize="small" />,
    actionType: 'request_info_freshservice_ticket',
    hasBody: true,
    bodyLabel: '¿Qué información necesitas?',
    bodyPlaceholder: 'Explica qué necesitas saber del cliente para avanzar...',
  },
};

interface QuickActionDialogProps {
  state: QuickActionState | null;
  onClose: () => void;
  onSuccess: () => void;
}

function QuickActionDialog({ state, onClose, onSuccess }: QuickActionDialogProps) {
  const [body, setBody] = useState('');
  const [resolveStatus, setResolveStatus] = useState<'resolved' | 'closed'>('resolved');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (state) { setBody(''); setError(null); setResolveStatus('resolved'); }
  }, [state]);

  if (!state) return null;
  const meta = ACTION_META[state.type];
  const ticket = state.ticket;
  const actionType = state.type;

  async function handleSubmit() {
    setSubmitting(true);
    setError(null);
    try {
      let payload: Record<string, unknown> = {};
      if (actionType === 'reply') payload = { body };
      else if (actionType === 'task') payload = body.trim() ? { body } : {};
      else if (actionType === 'resolve') payload = { status: resolveStatus };
      else if (actionType === 'request_info') payload = { body };

      await createAssistantAction({
        action_type: meta.actionType,
        title: `${meta.label} — ticket #${ticket.id}`,
        description: `${meta.label} para "${ticket.subject}"`,
        ticket_id: ticket.id,
        payload,
      });
      onSuccess();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al crear la acción');
    } finally {
      setSubmitting(false);
    }
  }

  const canSubmit = state.type === 'resolve' || body.trim().length > 0;

  return (
    <Dialog open={true} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          {meta.icon}
          {meta.label}
        </Box>
        <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 0.5 }}>
          Ticket #{ticket.id} · {ticket.subject}
        </Typography>
      </DialogTitle>
      <DialogContent>
        {error ? <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert> : null}

        {state.type === 'resolve' ? (
          <FormControl fullWidth size="small">
            <InputLabel>Estado final</InputLabel>
            <Select
              value={resolveStatus}
              label="Estado final"
              onChange={(e) => setResolveStatus(e.target.value as 'resolved' | 'closed')}
            >
              <MenuItem value="resolved">Resuelto</MenuItem>
              <MenuItem value="closed">Cerrado</MenuItem>
            </Select>
          </FormControl>
        ) : (
          <TextField
            autoFocus
            fullWidth
            multiline
            minRows={4}
            label={meta.bodyLabel}
            placeholder={meta.bodyPlaceholder}
            value={body}
            onChange={(e) => setBody(e.target.value)}
            size="small"
          />
        )}

        <Typography variant="caption" color="text.secondary" sx={{ mt: 1.5, display: 'block' }}>
          Se creará una acción pendiente. Deberás aprobarla antes de que se ejecute.
        </Typography>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} disabled={submitting}>Cancelar</Button>
        <Button
          variant="contained"
          onClick={() => void handleSubmit()}
          disabled={submitting || !canSubmit}
          startIcon={submitting ? <CircularProgress size={16} /> : null}
        >
          Crear acción pendiente
        </Button>
      </DialogActions>
    </Dialog>
  );
}

// ─── main page ────────────────────────────────────────────────────────────────

export function TicketsPage() {
  const navigate = useNavigate();
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [source, setSource] = useState<string>('');
  const [scope, setScope] = useState<'mine' | 'all'>('mine');
  const [isLoading, setIsLoading] = useState(true);
  const [isSyncing, setIsSyncing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showFilters, setShowFilters] = useState(false);
  const [filters, setFilters] = useState<Filters>({
    search: '',
    statuses: [],
    priorities: [],
    includeClosed: false,
    onlyOverdue: false,
    onlyWithoutTask: false,
  });
  const [sort, setSort] = useState<{ field: SortField; direction: SortDirection }>({
    field: 'id',
    direction: 'desc',
  });
  const [quickAction, setQuickAction] = useState<QuickActionState | null>(null);
  const [snackbar, setSnackbar] = useState<string | null>(null);
  const lastFetchParams = useRef({ scope, includeClosed: filters.includeClosed });

  function fetchTickets(forceRefresh = false) {
    setIsLoading(!forceRefresh);
    if (forceRefresh) setIsSyncing(true);
    setError(null);
    lastFetchParams.current = { scope, includeClosed: filters.includeClosed };
    listTickets({ scope, includeClosed: filters.includeClosed, forceRefresh })
      .then((response) => {
        setTickets(response.items);
        setSource(response.source);
        if (forceRefresh) setSnackbar(`Sincronizados ${response.items.length} tickets`);
      })
      .catch((caught: Error) => setError(caught.message))
      .finally(() => { setIsLoading(false); setIsSyncing(false); });
  }

  useEffect(() => {
    fetchTickets(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scope, filters.includeClosed]);

  const allStatuses = useMemo(
    () => Array.from(new Set(tickets.map((t) => t.status))).sort(
      (a, b) => statusOrder.indexOf(a) - statusOrder.indexOf(b)
    ),
    [tickets]
  );
  const allPriorities = useMemo(
    () => Array.from(new Set(tickets.map((t) => t.priority))).sort(
      (a, b) => priorityOrder.indexOf(a) - priorityOrder.indexOf(b)
    ),
    [tickets]
  );

  const filteredTickets = useMemo(() => {
    let result = tickets.filter((ticket) => {
      const q = filters.search.toLowerCase();
      const matchesSearch = !q ||
        ticket.subject.toLowerCase().includes(q) ||
        ticket.id.includes(filters.search) ||
        ticket.requester.name.toLowerCase().includes(q) ||
        (ticket.requester.email ?? '').toLowerCase().includes(q);
      const matchesStatus = !filters.statuses.length || filters.statuses.includes(ticket.status);
      const matchesPriority = !filters.priorities.length || filters.priorities.includes(ticket.priority);
      const matchesOverdue = !filters.onlyOverdue || ticket.overdue === true;
      const matchesNoTask = !filters.onlyWithoutTask || !ticket.clickup_url;
      return matchesSearch && matchesStatus && matchesPriority && matchesOverdue && matchesNoTask;
    });

    result = [...result].sort((a, b) => {
      let cmp = 0;
      switch (sort.field) {
        case 'id': cmp = a.id.localeCompare(b.id, undefined, { numeric: true }); break;
        case 'subject': cmp = a.subject.localeCompare(b.subject); break;
        case 'status': cmp = statusOrder.indexOf(a.status) - statusOrder.indexOf(b.status); break;
        case 'priority': cmp = priorityOrder.indexOf(a.priority) - priorityOrder.indexOf(b.priority); break;
        case 'requester': cmp = a.requester.name.localeCompare(b.requester.name); break;
      }
      return sort.direction === 'asc' ? cmp : -cmp;
    });
    return result;
  }, [tickets, filters, sort]);

  function toggleSort(field: SortField) {
    setSort((c) => ({ field, direction: c.field === field && c.direction === 'asc' ? 'desc' : 'asc' }));
  }

  function toggleStatus(s: TicketStatus) {
    setFilters((c) => ({ ...c, statuses: c.statuses.includes(s) ? c.statuses.filter((x) => x !== s) : [...c.statuses, s] }));
  }

  function togglePriority(p: TicketPriority) {
    setFilters((c) => ({ ...c, priorities: c.priorities.includes(p) ? c.priorities.filter((x) => x !== p) : [...c.priorities, p] }));
  }

  return (
    <Box>
      {/* ── toolbar ── */}
      <Box sx={{ display: 'flex', gap: 1.5, alignItems: 'center', mb: 2, flexWrap: 'wrap' }}>
        <FormControl sx={{ minWidth: 160 }} size="small">
          <InputLabel>Vista</InputLabel>
          <Select value={scope} label="Vista" onChange={(e) => setScope(e.target.value as 'mine' | 'all')}>
            <MenuItem value="mine">Asignados a mí</MenuItem>
            <MenuItem value="all">Todos</MenuItem>
          </Select>
        </FormControl>

        <TextField
          size="small"
          placeholder="Buscar por ID, asunto o solicitante..."
          value={filters.search}
          onChange={(e) => setFilters((c) => ({ ...c, search: e.target.value }))}
          sx={{ minWidth: 280 }}
        />

        <FormControlLabel
          control={<Checkbox checked={filters.includeClosed} onChange={(e) => setFilters((c) => ({ ...c, includeClosed: e.target.checked }))} />}
          label="Incluir cerrados"
        />
        <FormControlLabel
          control={<Checkbox checked={filters.onlyOverdue} onChange={(e) => setFilters((c) => ({ ...c, onlyOverdue: e.target.checked }))} />}
          label="Solo vencidos"
        />
        <FormControlLabel
          control={<Checkbox checked={filters.onlyWithoutTask} onChange={(e) => setFilters((c) => ({ ...c, onlyWithoutTask: e.target.checked }))} />}
          label="Sin tarea"
        />

        <Tooltip title="Filtros avanzados">
          <IconButton color={showFilters ? 'primary' : 'default'} onClick={() => setShowFilters((v) => !v)}>
            <FilterListIcon />
          </IconButton>
        </Tooltip>

        <Tooltip title="Sincronizar con Freshservice">
          <span>
            <IconButton onClick={() => fetchTickets(true)} disabled={isSyncing}>
              <SyncIcon sx={{ animation: isSyncing ? 'spin 1s linear infinite' : 'none', '@keyframes spin': { from: { transform: 'rotate(0deg)' }, to: { transform: 'rotate(360deg)' } } }} />
            </IconButton>
          </span>
        </Tooltip>

        <Typography variant="body2" color="text.secondary" sx={{ ml: 'auto' }}>
          {filteredTickets.length} de {tickets.length} · {source || '-'}
        </Typography>
      </Box>

      {/* ── advanced filters ── */}
      {showFilters ? (
        <Paper sx={{ p: 2, mb: 2 }}>
          <Typography variant="subtitle2" gutterBottom>Estados</Typography>
          <Stack direction="row" spacing={1} flexWrap="wrap" mb={2}>
            {allStatuses.map((s) => (
              <Chip key={s} label={s} color={statusColor(s)} variant={filters.statuses.includes(s) ? 'filled' : 'outlined'} onClick={() => toggleStatus(s)} clickable />
            ))}
          </Stack>
          <Typography variant="subtitle2" gutterBottom>Prioridades</Typography>
          <Stack direction="row" spacing={1} flexWrap="wrap">
            {allPriorities.map((p) => (
              <Chip key={p} label={p} color={priorityColor(p)} variant={filters.priorities.includes(p) ? 'filled' : 'outlined'} onClick={() => togglePriority(p)} clickable />
            ))}
          </Stack>
        </Paper>
      ) : null}

      {isLoading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', mt: 8 }}><CircularProgress /></Box>
      ) : null}

      {error ? <Alert severity="error" sx={{ mt: 2 }}>{error}</Alert> : null}

      {!isLoading && !error ? (
        <TableContainer component={Paper}>
          <Table size="small">
            <TableHead>
              <TableRow>
                {(['id', 'subject', 'status', 'priority', 'requester'] as SortField[]).map((field) => (
                  <TableCell key={field}>
                    <TableSortLabel active={sort.field === field} direction={sort.direction} onClick={() => toggleSort(field)}>
                      {{ id: 'ID', subject: 'Asunto', status: 'Estado', priority: 'Prioridad', requester: 'Solicitante' }[field]}
                    </TableSortLabel>
                  </TableCell>
                ))}
                <TableCell>SLA</TableCell>
                <TableCell align="right">Acciones</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {filteredTickets.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={7} align="center">
                    <Typography color="text.secondary" sx={{ py: 3 }}>No hay tickets que coincidan.</Typography>
                  </TableCell>
                </TableRow>
              ) : (
                filteredTickets.map((ticket) => (
                  <TableRow
                    key={ticket.id}
                    hover
                    onClick={() => navigate(`/tickets/${ticket.id}`)}
                    sx={{ cursor: 'pointer', '&:hover .row-actions': { opacity: 1 } }}
                  >
                    <TableCell sx={{ fontFamily: 'monospace', fontSize: 12, whiteSpace: 'nowrap' }}>
                      {ticket.id}
                    </TableCell>
                    <TableCell sx={{ maxWidth: 320 }}>
                      <Typography variant="body2" noWrap>{ticket.subject}</Typography>
                    </TableCell>
                    <TableCell>
                      <Chip label={ticket.status} color={statusColor(ticket.status)} size="small" />
                    </TableCell>
                    <TableCell>
                      <Chip label={ticket.priority} color={priorityColor(ticket.priority)} size="small" variant="outlined" />
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2" noWrap>{ticket.requester.name}</Typography>
                      {ticket.requester.email ? (
                        <Typography variant="caption" color="text.disabled" display="block" noWrap>{ticket.requester.email}</Typography>
                      ) : null}
                    </TableCell>
                    <TableCell>
                      {ticket.sla && ticket.sla.status !== 'none' ? (
                        <Chip label={ticket.sla.status} color={slaColor(ticket.sla.status)} size="small" />
                      ) : null}
                    </TableCell>
                    <TableCell align="right">
                      <Box
                        className="row-actions"
                        sx={{
                          display: 'flex',
                          justifyContent: 'flex-end',
                          gap: 0.5,
                          // Touch devices have no hover, so keep the actions visible
                          // there; only fade-until-hover where a pointer can hover.
                          opacity: 1,
                          '@media (hover: hover)': { opacity: 0, transition: 'opacity 0.15s' },
                        }}
                      >
                        <Tooltip title="Responder">
                          <IconButton size="small" color="primary" onClick={(e) => { e.stopPropagation(); setQuickAction({ ticket, type: 'reply' }); }}>
                            <ReplyIcon fontSize="small" />
                          </IconButton>
                        </Tooltip>
                        <Tooltip title="Crear tarea ClickUp">
                          <IconButton size="small" color="secondary" onClick={(e) => { e.stopPropagation(); setQuickAction({ ticket, type: 'task' }); }}>
                            <TaskIcon fontSize="small" />
                          </IconButton>
                        </Tooltip>
                        <Tooltip title="Pedir información">
                          <IconButton size="small" onClick={(e) => { e.stopPropagation(); setQuickAction({ ticket, type: 'request_info' }); }}>
                            <HelpOutlineIcon fontSize="small" />
                          </IconButton>
                        </Tooltip>
                        <Tooltip title="Resolver">
                          <IconButton size="small" color="success" onClick={(e) => { e.stopPropagation(); setQuickAction({ ticket, type: 'resolve' }); }}>
                            <CheckCircleOutlineIcon fontSize="small" />
                          </IconButton>
                        </Tooltip>
                        {ticket.clickup_url ? (
                          <Tooltip title="Ver en ClickUp">
                            <IconButton size="small" component="a" href={ticket.clickup_url} target="_blank" rel="noopener noreferrer" onClick={(e) => e.stopPropagation()}>
                              <OpenInNewIcon fontSize="small" />
                            </IconButton>
                          </Tooltip>
                        ) : null}
                        {ticket.url ? (
                          <Tooltip title="Abrir en Freshservice">
                            <IconButton size="small" component="a" href={ticket.url} target="_blank" rel="noopener noreferrer" onClick={(e) => e.stopPropagation()}>
                              <OpenInNewIcon fontSize="small" />
                            </IconButton>
                          </Tooltip>
                        ) : null}
                      </Box>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </TableContainer>
      ) : null}

      <QuickActionDialog
        state={quickAction}
        onClose={() => setQuickAction(null)}
        onSuccess={() => setSnackbar('Acción pendiente creada. Apruébala en el panel de acciones.')}
      />

      <Snackbar
        open={snackbar !== null}
        autoHideDuration={4000}
        onClose={() => setSnackbar(null)}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert severity="success" onClose={() => setSnackbar(null)} sx={{ width: '100%' }}>
          {snackbar}
        </Alert>
      </Snackbar>
    </Box>
  );
}
