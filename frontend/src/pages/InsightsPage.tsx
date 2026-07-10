import { useCallback, useEffect, useState } from 'react';
import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  Divider,
  LinearProgress,
  Paper,
  Stack,
  Tab,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TablePagination,
  TableRow,
  Tabs,
  Typography,
} from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import RefreshIcon from '@mui/icons-material/Refresh';
import SyncIcon from '@mui/icons-material/Sync';
import HistoryIcon from '@mui/icons-material/History';
import AutoAwesomeIcon from '@mui/icons-material/AutoAwesome';
import TravelExploreIcon from '@mui/icons-material/TravelExplore';
import {
  generateKnowledge,
  getArchivedTickets,
  getInsightsStatus,
  getKnowledge,
  getWorkspaces,
  importWorkspaces,
  triggerBackfill,
  triggerSync,
} from '../api/insights';
import type {
  ArchivedTicket,
  DepartmentKnowledge,
  HarvestStatus,
  KnowledgeResponse,
  WorkspacesResponse,
} from '../types/insights';

function formatDate(iso: string | null): string {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleString('es-ES', {
      day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit',
    });
  } catch {
    return iso;
  }
}

const SEVERITY_COLORS: Record<string, 'default' | 'warning' | 'error'> = {
  low: 'default',
  medium: 'warning',
  high: 'error',
};

// --- Conocimiento tab --------------------------------------------------------

function KnowledgeTab() {
  const [knowledge, setKnowledge] = useState<KnowledgeResponse | null>(null);
  const [deptIndex, setDeptIndex] = useState(0);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await getKnowledge();
      setKnowledge(res);
      setDeptIndex((i) => Math.min(i, Math.max(res.departments.length - 1, 0)));
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  async function handleGenerate() {
    setBusy(true);
    setNotice(null);
    try {
      await generateKnowledge();
      setNotice('Generación lanzada en segundo plano. Pulsa "Refrescar" en unos momentos para ver el resultado.');
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  if (loading) return <CenteredSpinner />;

  const departments = knowledge?.departments ?? [];
  const dept = departments[deptIndex];

  return (
    <Box>
      <Stack direction="row" spacing={1} sx={{ mb: 2 }}>
        <Button variant="contained" startIcon={<AutoAwesomeIcon />} onClick={handleGenerate} disabled={busy}>
          {busy ? 'Lanzando…' : 'Generar'}
        </Button>
        <Button variant="outlined" startIcon={<RefreshIcon />} onClick={() => void load()}>Refrescar</Button>
      </Stack>

      {notice ? <Alert severity="info" sx={{ mb: 2 }} onClose={() => setNotice(null)}>{notice}</Alert> : null}
      {error ? <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert> : null}

      {!knowledge?.persisted || departments.length === 0 ? (
        <Typography color="text.secondary">
          Aún no hay conocimiento generado. Configura los workspaces e ingiere el histórico en la pestaña "Estado", luego pulsa "Generar".
        </Typography>
      ) : (
        <>
          <Typography variant="caption" color="text.secondary">
            Generado {formatDate(knowledge.generated_at)} · modelo {knowledge.model}
          </Typography>

          <Tabs
            value={deptIndex}
            onChange={(_, v) => setDeptIndex(v)}
            variant="scrollable"
            scrollButtons="auto"
            sx={{ mt: 1, mb: 2, borderBottom: 1, borderColor: 'divider' }}
          >
            {departments.map((d) => (
              <Tab key={d.workspace_id} label={`${d.name || d.workspace_id} (${d.total_tickets})`} />
            ))}
          </Tabs>

          {dept ? <DepartmentView dept={dept} /> : null}
        </>
      )}
    </Box>
  );
}

function DepartmentView({ dept }: { dept: DepartmentKnowledge }) {
  return (
    <Box>
      <Section title="Cuellos de botella">
        {dept.bottlenecks.length === 0 ? <Empty /> : dept.bottlenecks.map((b, i) => (
          <Paper key={i} variant="outlined" sx={{ p: 1.5, mb: 1 }}>
            <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 0.5 }}>
              <Typography sx={{ fontWeight: 600, flexGrow: 1 }}>{b.title}</Typography>
              <Chip size="small" label={b.severity} color={SEVERITY_COLORS[b.severity] ?? 'default'} />
              {b.category ? <Chip size="small" variant="outlined" label={b.category} /> : null}
            </Stack>
            <Typography variant="body2" color="text.secondary">{b.description}</Typography>
          </Paper>
        ))}
      </Section>

      <Section title="Oportunidades de automatización">
        {dept.automation.length === 0 ? <Empty /> : dept.automation.map((a, i) => (
          <Paper key={i} variant="outlined" sx={{ p: 1.5, mb: 1 }}>
            <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 0.5 }}>
              <Typography sx={{ fontWeight: 600, flexGrow: 1 }}>{a.title}</Typography>
              {a.category ? <Chip size="small" variant="outlined" label={a.category} /> : null}
            </Stack>
            <Typography variant="body2" color="text.secondary">{a.description}</Typography>
            {a.rationale ? <Typography variant="caption" color="text.disabled">Por qué: {a.rationale}</Typography> : null}
          </Paper>
        ))}
      </Section>

      <Section title="Problemas recurrentes">
        {dept.recurring.length === 0 ? <Empty /> : (
          <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap sx={{ mb: 1 }}>
            {dept.recurring.map((r) => <Chip key={r.label} label={`${r.label} · ${r.count}`} color="primary" variant="outlined" />)}
          </Stack>
        )}
      </Section>

      <Section title={`Temas (${dept.themes.length})`}>
        {dept.themes.map((theme, i) => (
          <Accordion key={`${theme.title}-${i}`}>
            <AccordionSummary expandIcon={<ExpandMoreIcon />}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, width: '100%' }}>
                <Typography sx={{ fontWeight: 600, flexGrow: 1 }}>{theme.title}</Typography>
                <Chip label={`${theme.frequency} tickets`} size="small" />
              </Box>
            </AccordionSummary>
            <AccordionDetails>
              <Typography variant="body2" sx={{ mb: 1 }}>{theme.summary}</Typography>
              <ThemeSection title="Síntomas" text={theme.symptoms} />
              <ThemeSection title="Causas" text={theme.root_causes} />
              <ThemeSection title="Resolución" text={theme.resolution_steps} />
              <Divider sx={{ my: 1 }} />
              <Typography variant="caption" color="text.secondary">
                Tickets: {theme.ticket_refs.map((t) => `#${t.ticket_id}`).join(', ')}
              </Typography>
            </AccordionDetails>
          </Accordion>
        ))}
      </Section>

      <Section title="Métricas por categoría">
        <TableContainer component={Paper} variant="outlined">
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Categoría</TableCell>
                <TableCell align="right">Volumen</TableCell>
                <TableCell align="right">Resolución media (h)</TableCell>
                <TableCell align="right">Tasa reapertura</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {dept.metrics.map((m) => (
                <TableRow key={m.category} hover>
                  <TableCell>{m.category}</TableCell>
                  <TableCell align="right">{m.volume}</TableCell>
                  <TableCell align="right">{m.avg_resolution_hours ?? '—'}</TableCell>
                  <TableCell align="right">{m.reopen_rate != null ? `${Math.round(m.reopen_rate * 100)}%` : '—'}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      </Section>
    </Box>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <Box sx={{ mb: 3 }}>
      <Typography variant="h6" sx={{ mb: 1 }}>{title}</Typography>
      {children}
    </Box>
  );
}

function Empty() {
  return <Typography variant="body2" color="text.secondary">Sin datos.</Typography>;
}

function ThemeSection({ title, text }: { title: string; text: string }) {
  if (!text) return null;
  return (
    <Box sx={{ mb: 1 }}>
      <Typography variant="subtitle2">{title}</Typography>
      <Typography variant="body2" color="text.secondary" sx={{ whiteSpace: 'pre-line' }}>{text}</Typography>
    </Box>
  );
}

// --- Estado tab --------------------------------------------------------------

function StatusTab() {
  const [status, setStatus] = useState<HarvestStatus | null>(null);
  const [workspaces, setWorkspaces] = useState<WorkspacesResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [s, w] = await Promise.all([getInsightsStatus(), getWorkspaces()]);
      setStatus(s);
      setWorkspaces(w);
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  async function run(action: () => Promise<unknown>, message: string) {
    setBusy(true);
    setNotice(null);
    try {
      await action();
      setNotice(message);
      await load();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  if (loading) return <CenteredSpinner />;

  const anyInProgress = status?.workspaces.some((w) => w.in_progress) ?? false;

  return (
    <Box>
      <Stack direction="row" spacing={1} sx={{ mb: 2 }} flexWrap="wrap" useFlexGap>
        <Button variant="contained" startIcon={<SyncIcon />} onClick={() => run(triggerSync, 'Sincronización lanzada.')} disabled={busy}>
          Sincronizar
        </Button>
        <Button variant="outlined" startIcon={<HistoryIcon />} onClick={() => run(() => triggerBackfill(), 'Backfill histórico lanzado.')} disabled={busy}>
          Backfill histórico
        </Button>
        <Button variant="outlined" startIcon={<TravelExploreIcon />} onClick={() => run(importWorkspaces, 'Workspaces descubiertos y guardados.')} disabled={busy}>
          Descubrir workspaces
        </Button>
        <Button variant="text" startIcon={<RefreshIcon />} onClick={() => void load()}>Refrescar</Button>
      </Stack>

      {anyInProgress ? <LinearProgress sx={{ mb: 2 }} /> : null}
      {notice ? <Alert severity="info" sx={{ mb: 2 }} onClose={() => setNotice(null)}>{notice}</Alert> : null}
      {error ? <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert> : null}

      <Typography variant="subtitle2" sx={{ mb: 1 }}>Workspaces configurados</Typography>
      {(workspaces?.configured.length ?? 0) === 0 ? (
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          Ninguno. Pulsa "Descubrir workspaces" para traerlos de Freshservice.
        </Typography>
      ) : (
        <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap sx={{ mb: 3 }}>
          {workspaces?.configured.map((w) => <Chip key={w.workspace_id} label={`${w.name} (${w.workspace_id})`} />)}
        </Stack>
      )}

      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        Total archivado: {status?.total_archived ?? 0} tickets.
      </Typography>

      <TableContainer component={Paper} variant="outlined">
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Departamento</TableCell>
              <TableCell align="center">Backfill</TableCell>
              <TableCell align="right">Archivados</TableCell>
              <TableCell align="right">Última sync</TableCell>
              <TableCell align="center">Estado</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {(status?.workspaces ?? []).map((w) => (
              <TableRow key={w.workspace_id} hover>
                <TableCell>{w.name || w.workspace_id}</TableCell>
                <TableCell align="center">
                  <Chip size="small" label={w.backfill_done ? 'Completo' : 'Pendiente'} color={w.backfill_done ? 'success' : 'default'} />
                </TableCell>
                <TableCell align="right">{w.archived_count}</TableCell>
                <TableCell align="right">{formatDate(w.last_incremental_at)}</TableCell>
                <TableCell align="center">
                  {w.in_progress
                    ? <Chip size="small" label="En curso" color="warning" />
                    : w.last_error
                      ? <Chip size="small" label={w.last_error} color="error" variant="outlined" />
                      : '—'}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
    </Box>
  );
}

// --- Tickets tab -------------------------------------------------------------

function TicketsTab() {
  const [rows, setRows] = useState<ArchivedTicket[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(50);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await getArchivedTickets(page * rowsPerPage, rowsPerPage);
      setRows(res.items);
      setTotal(res.total);
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, [page, rowsPerPage]);

  useEffect(() => { void load(); }, [load]);

  return (
    <Box>
      <Stack direction="row" spacing={1} sx={{ mb: 2 }}>
        <Button variant="outlined" startIcon={<RefreshIcon />} onClick={() => void load()}>Refrescar</Button>
      </Stack>
      {error ? <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert> : null}
      {loading ? <CenteredSpinner /> : (
        <TableContainer component={Paper} variant="outlined">
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Ticket</TableCell>
                <TableCell>Asunto</TableCell>
                <TableCell>Estado</TableCell>
                <TableCell>Categoría</TableCell>
                <TableCell>Ficha</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {rows.map((t) => (
                <TableRow key={`${t.workspace_id}:${t.ticket_id}`} hover>
                  <TableCell>#{t.ticket_id}</TableCell>
                  <TableCell sx={{ maxWidth: 280, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {t.subject}
                  </TableCell>
                  <TableCell><Chip size="small" label={t.status} /></TableCell>
                  <TableCell>{t.signature?.category ?? '—'}</TableCell>
                  <TableCell sx={{ maxWidth: 360 }}>
                    {t.signature ? (
                      <Typography variant="caption" color="text.secondary">
                        <strong>Problema:</strong> {t.signature.problem}<br />
                        <strong>Resolución:</strong> {t.signature.resolution}
                      </Typography>
                    ) : (
                      <Typography variant="caption" color="text.disabled">Sin firma aún</Typography>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          <TablePagination
            component="div"
            count={total}
            page={page}
            onPageChange={(_, p) => setPage(p)}
            rowsPerPage={rowsPerPage}
            onRowsPerPageChange={(e) => { setRowsPerPage(parseInt(e.target.value, 10)); setPage(0); }}
            rowsPerPageOptions={[25, 50, 100]}
          />
        </TableContainer>
      )}
    </Box>
  );
}

function CenteredSpinner() {
  return (
    <Box sx={{ display: 'flex', justifyContent: 'center', mt: 6 }}>
      <CircularProgress />
    </Box>
  );
}

export function InsightsPage() {
  const [tab, setTab] = useState(0);

  return (
    <Box>
      <Typography variant="h4" gutterBottom>Insights</Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        Conocimiento por departamento del histórico de Freshservice: problemas, cuellos de botella y automatización.
      </Typography>

      <Tabs value={tab} onChange={(_, v) => setTab(v)} sx={{ mb: 2 }}>
        <Tab label="Conocimiento" />
        <Tab label="Estado" />
        <Tab label="Tickets" />
      </Tabs>

      {tab === 0 ? <KnowledgeTab /> : null}
      {tab === 1 ? <StatusTab /> : null}
      {tab === 2 ? <TicketsTab /> : null}
    </Box>
  );
}
