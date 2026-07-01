import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box,
  Checkbox,
  Chip,
  CircularProgress,
  FormControl,
  FormControlLabel,
  IconButton,
  InputLabel,
  MenuItem,
  Paper,
  Select,
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
import { listTickets } from '../api/tickets';
import type { SlaStatus, Ticket, TicketPriority, TicketStatus } from '../types/ticket';

interface Filters {
  search: string;
  statuses: TicketStatus[];
  priorities: TicketPriority[];
  includeClosed: boolean;
  onlyOverdue: boolean;
}

type SortField = 'id' | 'subject' | 'status' | 'priority' | 'requester';
type SortDirection = 'asc' | 'desc';

const statusOrder: TicketStatus[] = ['open', 'pending', 'waiting on customer', 'waiting on third party', 'resolved', 'closed', 'unknown'];
const priorityOrder: TicketPriority[] = ['urgent', 'high', 'medium', 'low', 'unknown'];

function statusColor(status: TicketStatus): 'success' | 'warning' | 'info' | 'default' | 'error' {
  switch (status) {
    case 'open':
      return 'success';
    case 'pending':
    case 'waiting on customer':
    case 'waiting on third party':
      return 'warning';
    case 'resolved':
      return 'info';
    case 'closed':
      return 'default';
    default:
      return 'error';
  }
}

function priorityColor(priority: TicketPriority): 'error' | 'warning' | 'info' | 'default' {
  switch (priority) {
    case 'urgent':
      return 'error';
    case 'high':
      return 'warning';
    case 'medium':
      return 'info';
    default:
      return 'default';
  }
}

function slaColor(status: SlaStatus): 'success' | 'warning' | 'error' | 'default' {
  switch (status) {
    case 'ok':
      return 'success';
    case 'at_risk':
      return 'warning';
    case 'breached':
      return 'error';
    default:
      return 'default';
  }
}

/**
 * Render the tickets list page with filters and sorting.
 *
 * Parameters:
 *   None.
 *
 * Returns:
 *   JSX tickets page.
 *
 * Edge cases:
 *   Backend excludes closed tickets by default.
 */
export function TicketsPage() {
  const navigate = useNavigate();
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [source, setSource] = useState<string>('');
  const [scope, setScope] = useState<'mine' | 'all'>('mine');
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showFilters, setShowFilters] = useState(false);
  const [filters, setFilters] = useState<Filters>({
    search: '',
    statuses: [],
    priorities: [],
    includeClosed: false,
    onlyOverdue: false,
  });
  const [sort, setSort] = useState<{ field: SortField; direction: SortDirection }>({
    field: 'id',
    direction: 'desc',
  });

  useEffect(() => {
    setIsLoading(true);
    setError(null);
    listTickets({ scope, includeClosed: filters.includeClosed })
      .then((response) => {
        setTickets(response.items);
        setSource(response.source);
      })
      .catch((caught: Error) => setError(caught.message))
      .finally(() => setIsLoading(false));
  }, [scope, filters.includeClosed]);

  const allStatuses = useMemo(
    () => Array.from(new Set(tickets.map((ticket) => ticket.status))).sort(
      (a, b) => statusOrder.indexOf(a) - statusOrder.indexOf(b)
    ),
    [tickets]
  );
  const allPriorities = useMemo(
    () => Array.from(new Set(tickets.map((ticket) => ticket.priority))).sort(
      (a, b) => priorityOrder.indexOf(a) - priorityOrder.indexOf(b)
    ),
    [tickets]
  );

  const filteredTickets = useMemo(() => {
    let result = tickets.filter((ticket) => {
      const matchesSearch =
        filters.search === '' ||
        ticket.subject.toLowerCase().includes(filters.search.toLowerCase()) ||
        ticket.id.includes(filters.search) ||
        ticket.requester.name.toLowerCase().includes(filters.search.toLowerCase()) ||
        (ticket.requester.email ?? '').toLowerCase().includes(filters.search.toLowerCase());

      const matchesStatus = filters.statuses.length === 0 || filters.statuses.includes(ticket.status);
      const matchesPriority = filters.priorities.length === 0 || filters.priorities.includes(ticket.priority);
      const matchesOverdue = !filters.onlyOverdue || ticket.overdue === true;

      return matchesSearch && matchesStatus && matchesPriority && matchesOverdue;
    });

    result = [...result].sort((a, b) => {
      let comparison = 0;
      switch (sort.field) {
        case 'id':
          comparison = a.id.localeCompare(b.id, undefined, { numeric: true });
          break;
        case 'subject':
          comparison = a.subject.localeCompare(b.subject);
          break;
        case 'status':
          comparison = statusOrder.indexOf(a.status) - statusOrder.indexOf(b.status);
          break;
        case 'priority':
          comparison = priorityOrder.indexOf(a.priority) - priorityOrder.indexOf(b.priority);
          break;
        case 'requester':
          comparison = a.requester.name.localeCompare(b.requester.name);
          break;
      }
      return sort.direction === 'asc' ? comparison : -comparison;
    });

    return result;
  }, [tickets, filters, sort]);

  function toggleSort(field: SortField): void {
    setSort((current) => ({
      field,
      direction: current.field === field && current.direction === 'asc' ? 'desc' : 'asc',
    }));
  }

  function toggleStatus(status: TicketStatus): void {
    setFilters((current) => ({
      ...current,
      statuses: current.statuses.includes(status)
        ? current.statuses.filter((s) => s !== status)
        : [...current.statuses, status],
    }));
  }

  function togglePriority(priority: TicketPriority): void {
    setFilters((current) => ({
      ...current,
      priorities: current.priorities.includes(priority)
        ? current.priorities.filter((p) => p !== priority)
        : [...current.priorities, priority],
    }));
  }

  return (
    <Box>
      <Typography variant="h4" gutterBottom>
        Tickets
      </Typography>

      <Box sx={{ display: 'flex', gap: 2, alignItems: 'center', mb: 2, flexWrap: 'wrap' }}>
        <FormControl sx={{ minWidth: 160 }} size="small">
          <InputLabel id="ticket-scope-label">Vista</InputLabel>
          <Select
            labelId="ticket-scope-label"
            value={scope}
            label="Vista"
            onChange={(event) => setScope(event.target.value as 'mine' | 'all')}
          >
            <MenuItem value="mine">Asignados a mí</MenuItem>
            <MenuItem value="all">Todos</MenuItem>
          </Select>
        </FormControl>

        <TextField
          size="small"
          placeholder="Buscar por ID, asunto o solicitante..."
          value={filters.search}
          onChange={(event) => setFilters((current) => ({ ...current, search: event.target.value }))}
          sx={{ minWidth: 280 }}
        />

        <FormControlLabel
          control={
            <Checkbox
              checked={filters.includeClosed}
              onChange={(event) =>
                setFilters((current) => ({ ...current, includeClosed: event.target.checked }))
              }
            />
          }
          label="Incluir cerrados"
        />

        <FormControlLabel
          control={
            <Checkbox
              checked={filters.onlyOverdue}
              onChange={(event) =>
                setFilters((current) => ({ ...current, onlyOverdue: event.target.checked }))
              }
            />
          }
          label="Solo vencidos"
        />

        <IconButton color="primary" onClick={() => setShowFilters((value) => !value)}>
          <FilterListIcon />
        </IconButton>

        <Typography variant="body2" color="text.secondary" sx={{ ml: 'auto' }}>
          {filteredTickets.length} de {tickets.length} · Fuente: {source || '-'}
        </Typography>
      </Box>

      {showFilters ? (
        <Paper sx={{ p: 2, mb: 2 }}>
          <Typography variant="subtitle2" gutterBottom>
            Estados
          </Typography>
          <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', mb: 2 }}>
            {allStatuses.map((status) => (
              <Chip
                key={status}
                label={status}
                color={statusColor(status)}
                variant={filters.statuses.includes(status) ? 'filled' : 'outlined'}
                onClick={() => toggleStatus(status)}
                clickable
              />
            ))}
          </Box>
          <Typography variant="subtitle2" gutterBottom>
            Prioridades
          </Typography>
          <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
            {allPriorities.map((priority) => (
              <Chip
                key={priority}
                label={priority}
                color={priorityColor(priority)}
                variant={filters.priorities.includes(priority) ? 'filled' : 'outlined'}
                onClick={() => togglePriority(priority)}
                clickable
              />
            ))}
          </Box>
        </Paper>
      ) : null}

      {isLoading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', mt: 8 }}>
          <CircularProgress />
        </Box>
      ) : null}

      {error ? (
        <Typography color="error" sx={{ mt: 2 }}>
          {error}
        </Typography>
      ) : null}

      {!isLoading && !error ? (
        <TableContainer component={Paper}>
          <Table>
            <TableHead>
              <TableRow>
                <TableCell>
                  <TableSortLabel active={sort.field === 'id'} direction={sort.direction} onClick={() => toggleSort('id')}>
                    ID
                  </TableSortLabel>
                </TableCell>
                <TableCell>
                  <TableSortLabel active={sort.field === 'subject'} direction={sort.direction} onClick={() => toggleSort('subject')}>
                    Asunto
                  </TableSortLabel>
                </TableCell>
                <TableCell>
                  <TableSortLabel active={sort.field === 'status'} direction={sort.direction} onClick={() => toggleSort('status')}>
                    Estado
                  </TableSortLabel>
                </TableCell>
                <TableCell>
                  <TableSortLabel active={sort.field === 'priority'} direction={sort.direction} onClick={() => toggleSort('priority')}>
                    Prioridad
                  </TableSortLabel>
                </TableCell>
                <TableCell>
                  <TableSortLabel active={sort.field === 'requester'} direction={sort.direction} onClick={() => toggleSort('requester')}>
                    Solicitante
                  </TableSortLabel>
                </TableCell>
                <TableCell>SLA</TableCell>
                <TableCell align="right">Acciones</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {filteredTickets.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={7} align="center">
                    <Typography color="text.secondary">No hay tickets que coincidan.</Typography>
                  </TableCell>
                </TableRow>
              ) : (
                filteredTickets.map((ticket) => (
                  <TableRow
                    key={ticket.id}
                    hover
                    onClick={() => navigate(`/tickets/${ticket.id}`)}
                    sx={{ cursor: 'pointer' }}
                  >
                    <TableCell>{ticket.id}</TableCell>
                    <TableCell>{ticket.subject}</TableCell>
                    <TableCell>
                      <Chip label={ticket.status} color={statusColor(ticket.status)} size="small" />
                    </TableCell>
                    <TableCell>
                      <Chip label={ticket.priority} color={priorityColor(ticket.priority)} size="small" />
                    </TableCell>
                    <TableCell>
                      {ticket.requester.name}
                      {ticket.requester.email ? (
                        <Typography variant="caption" color="text.secondary" display="block">
                          {ticket.requester.email}
                        </Typography>
                      ) : null}
                    </TableCell>
                    <TableCell>
                      {ticket.sla && ticket.sla.status !== 'none' ? (
                        <Chip
                          label={ticket.sla.status}
                          color={slaColor(ticket.sla.status)}
                          size="small"
                        />
                      ) : null}
                    </TableCell>
                    <TableCell align="right">
                      <Box sx={{ display: 'flex', justifyContent: 'flex-end', gap: 0.5 }}>
                        {ticket.clickup_url ? (
                          <Tooltip title="Ver en ClickUp">
                            <IconButton
                              size="small"
                              component="a"
                              href={ticket.clickup_url}
                              target="_blank"
                              rel="noopener noreferrer"
                              onClick={(event) => event.stopPropagation()}
                              color="secondary"
                            >
                              <OpenInNewIcon fontSize="small" />
                            </IconButton>
                          </Tooltip>
                        ) : null}
                        {ticket.url ? (
                          <Tooltip title="Abrir en Freshservice">
                            <IconButton
                              size="small"
                              component="a"
                              href={ticket.url}
                              target="_blank"
                              rel="noopener noreferrer"
                              onClick={(event) => event.stopPropagation()}
                            >
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
    </Box>
  );
}
