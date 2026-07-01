import { useEffect, useState } from 'react';
import {
  Box,
  Chip,
  CircularProgress,
  Link,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Tooltip,
  Typography,
} from '@mui/material';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import { getLinkedTasks } from '../api/links';
import type { LinkedTaskItem } from '../types/links';
import { useNavigate } from 'react-router-dom';

const TICKET_STATUS_COLORS: Record<string, 'success' | 'warning' | 'error' | 'default' | 'info'> = {
  open: 'error',
  pending: 'warning',
  resolved: 'success',
  closed: 'default',
  'waiting on customer': 'info',
  'waiting on third party': 'info',
};

const CLICKUP_STATUS_COLORS: Record<string, 'success' | 'warning' | 'error' | 'default' | 'info'> = {
  open: 'error',
  'in progress': 'warning',
  done: 'success',
  closed: 'default',
  review: 'info',
  blocked: 'error',
};

function StatusChip({ label, system }: { label: string; system: 'ticket' | 'clickup' }) {
  const map = system === 'ticket' ? TICKET_STATUS_COLORS : CLICKUP_STATUS_COLORS;
  const color = map[label.toLowerCase()] ?? 'default';
  return label ? <Chip label={label} size="small" color={color} /> : <Typography variant="caption" color="text.disabled">—</Typography>;
}

function formatDate(iso: string): string {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleString('es-ES', {
      day: '2-digit', month: '2-digit', year: 'numeric',
      hour: '2-digit', minute: '2-digit',
    });
  } catch {
    return iso;
  }
}

export function LinkedTasksPage() {
  const [items, setItems] = useState<LinkedTaskItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    async function load() {
      try {
        setItems(await getLinkedTasks());
      } catch (e) {
        setError((e as Error).message);
      } finally {
        setLoading(false);
      }
    }
    void load();
  }, []);

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', mt: 8 }}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box>
      <Typography variant="h4" gutterBottom>
        Tareas vinculadas
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
        Tickets de Freshservice con tarea creada en ClickUp.
      </Typography>

      {error ? (
        <Typography color="error" sx={{ mb: 2 }}>{error}</Typography>
      ) : null}

      {items.length === 0 && !error ? (
        <Typography color="text.secondary">No hay tareas vinculadas todavía.</Typography>
      ) : (
        <TableContainer component={Paper} variant="outlined">
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Ticket</TableCell>
                <TableCell>Estado ticket</TableCell>
                <TableCell>Tarea ClickUp</TableCell>
                <TableCell>Estado ClickUp</TableCell>
                <TableCell>Creado</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {items.map((item) => {
                const displayClickupStatus = item.clickup_status || item.last_known_clickup_status || '';
                const needsReply = ['open', 'pending'].includes(item.ticket_status.toLowerCase()) &&
                  ['done', 'closed'].includes(displayClickupStatus.toLowerCase());

                return (
                  <TableRow
                    key={item.link_id}
                    hover
                    sx={needsReply ? { backgroundColor: 'warning.light' } : undefined}
                  >
                    <TableCell>
                      <Box sx={{ display: 'flex', flexDirection: 'column' }}>
                        <Link
                          component="button"
                          variant="body2"
                          sx={{ textAlign: 'left', fontWeight: 600 }}
                          onClick={() => navigate(`/tickets/${item.ticket_id}`)}
                        >
                          #{item.ticket_id}
                        </Link>
                        {item.ticket_subject ? (
                          <Tooltip title={item.ticket_subject}>
                            <Typography
                              variant="caption"
                              color="text.secondary"
                              sx={{
                                maxWidth: 220,
                                overflow: 'hidden',
                                textOverflow: 'ellipsis',
                                whiteSpace: 'nowrap',
                                display: 'block',
                              }}
                            >
                              {item.ticket_subject}
                            </Typography>
                          </Tooltip>
                        ) : null}
                        {needsReply ? (
                          <Chip label="Pendiente responder" size="small" color="warning" sx={{ mt: 0.5, width: 'fit-content' }} />
                        ) : null}
                      </Box>
                    </TableCell>

                    <TableCell>
                      <StatusChip label={item.ticket_status} system="ticket" />
                    </TableCell>

                    <TableCell>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                        <Typography variant="body2" sx={{ fontFamily: 'monospace', fontSize: 12 }}>
                          {item.clickup_task_id}
                        </Typography>
                        {item.clickup_task_url ? (
                          <Tooltip title="Abrir en ClickUp">
                            <Link href={item.clickup_task_url} target="_blank" rel="noopener noreferrer" sx={{ display: 'flex' }}>
                              <OpenInNewIcon sx={{ fontSize: 14 }} />
                            </Link>
                          </Tooltip>
                        ) : null}
                      </Box>
                    </TableCell>

                    <TableCell>
                      <StatusChip label={displayClickupStatus} system="clickup" />
                    </TableCell>

                    <TableCell>
                      <Typography variant="caption" color="text.secondary">
                        {formatDate(item.created_at)}
                      </Typography>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </TableContainer>
      )}
    </Box>
  );
}
