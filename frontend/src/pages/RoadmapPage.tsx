import { useEffect, useRef, useState } from 'react';
import {
  Alert,
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
  IconButton,
  Link,
  Menu,
  MenuItem,
  Paper,
  Stack,
  Tab,
  Tabs,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import AutoAwesomeIcon from '@mui/icons-material/AutoAwesome';
import SummarizeIcon from '@mui/icons-material/Summarize';
import AddIcon from '@mui/icons-material/Add';
import MoreVertIcon from '@mui/icons-material/MoreVert';
import CloudDoneIcon from '@mui/icons-material/CloudDone';
import ChevronLeftIcon from '@mui/icons-material/ChevronLeft';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import {
  DndContext,
  DragOverlay,
  PointerSensor,
  useDraggable,
  useDroppable,
  useSensor,
  useSensors,
  type DragEndEvent,
  type DragStartEvent,
} from '@dnd-kit/core';
import { getRoadmap, generateRoadmap, saveRoadmap, summarizeRoadmap } from '../api/roadmap';
import type {
  RoadmapGroup,
  RoadmapListSection,
  RoadmapResponse,
  RoadmapTask,
} from '../types/roadmap';

const UNCLASSIFIED = 'Sin clasificar';
const HIDDEN_STATUSES_KEY = 'roadmap_hidden_statuses';

function loadHiddenStatuses(): Set<string> {
  try {
    const raw = window.localStorage.getItem(HIDDEN_STATUSES_KEY);
    return new Set(raw ? (JSON.parse(raw) as string[]) : []);
  } catch {
    return new Set();
  }
}

const CLICKUP_STATUS_COLORS: Record<string, 'success' | 'warning' | 'error' | 'default' | 'info'> = {
  open: 'error',
  'in progress': 'warning',
  done: 'success',
  closed: 'default',
  review: 'info',
  blocked: 'error',
};

function statusColor(status: string) {
  return CLICKUP_STATUS_COLORS[status.toLowerCase()] ?? 'default';
}

type SaveState = 'idle' | 'saving' | 'saved' | 'error';

function withCounts(sections: RoadmapListSection[]): RoadmapListSection[] {
  return sections.map((s) => ({
    ...s,
    groups: s.groups.map((g) => ({ ...g, count: g.tasks.length })),
  }));
}

function TaskCardBody({ task }: { task: RoadmapTask }) {
  return (
    <CardContent sx={{ p: 1, '&:last-child': { pb: 1 } }}>
      <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 0.5 }}>
        <Typography
          variant="body2"
          sx={{
            flexGrow: 1,
            lineHeight: 1.3,
            display: '-webkit-box',
            WebkitLineClamp: 2,
            WebkitBoxOrient: 'vertical',
            overflow: 'hidden',
          }}
        >
          {task.name}
        </Typography>
        <Chip
          label={task.status}
          size="small"
          color={statusColor(task.status)}
          sx={{ height: 18, '& .MuiChip-label': { px: 0.75, fontSize: 10 } }}
        />
        {task.url ? (
          <Tooltip title="Abrir en ClickUp">
            <Link
              href={task.url}
              target="_blank"
              rel="noopener noreferrer"
              onPointerDown={(e) => e.stopPropagation()}
              sx={{ display: 'flex', mt: 0.25 }}
            >
              <OpenInNewIcon sx={{ fontSize: 14 }} />
            </Link>
          </Tooltip>
        ) : null}
      </Box>
    </CardContent>
  );
}

function DraggableTaskCard({ task }: { task: RoadmapTask }) {
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({ id: task.id });
  return (
    <Card
      ref={setNodeRef}
      variant="outlined"
      sx={{ opacity: isDragging ? 0.4 : 1, cursor: 'grab' }}
      {...listeners}
      {...attributes}
    >
      <TaskCardBody task={task} />
    </Card>
  );
}

interface ColumnProps {
  group: RoadmapGroup;
  droppableId: string;
  hiddenStatuses: Set<string>;
  collapsed: boolean;
  onToggleCollapse: () => void;
  onRename: () => void;
  onDelete: () => void;
}

function DroppableColumn({ group, droppableId, hiddenStatuses, collapsed, onToggleCollapse, onRename, onDelete }: ColumnProps) {
  const { setNodeRef, isOver } = useDroppable({ id: droppableId });
  const [menuAnchor, setMenuAnchor] = useState<null | HTMLElement>(null);
  const isUnclassified = group.title === UNCLASSIFIED;
  const visibleTasks = group.tasks.filter((t) => !hiddenStatuses.has(t.status.toLowerCase()));
  const hiddenCount = group.tasks.length - visibleTasks.length;
  const countLabel = hiddenCount > 0 ? `${visibleTasks.length}/${group.tasks.length}` : String(group.tasks.length);

  if (collapsed) {
    return (
      <Tooltip title={`${group.title} — expandir`}>
        <Paper
          ref={setNodeRef}
          variant="outlined"
          onClick={onToggleCollapse}
          sx={{
            width: 48,
            minWidth: 48,
            py: 1,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: 1,
            cursor: 'pointer',
            bgcolor: isOver ? 'action.hover' : 'background.paper',
          }}
        >
          <ChevronRightIcon fontSize="small" color="action" />
          <Chip label={countLabel} size="small" />
          <Typography
            variant="caption"
            color="text.secondary"
            sx={{ writingMode: 'vertical-rl', maxHeight: 180, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
          >
            {group.title}
          </Typography>
        </Paper>
      </Tooltip>
    );
  }

  return (
    <Paper
      ref={setNodeRef}
      variant="outlined"
      sx={{
        p: 1.5,
        width: 288,
        minWidth: 288,
        display: 'flex',
        flexDirection: 'column',
        gap: 1,
        bgcolor: isOver ? 'action.hover' : 'background.paper',
        outline: isOver ? '2px dashed' : 'none',
        outlineColor: 'primary.main',
        transition: 'background-color 120ms ease',
      }}
    >
      <Box>
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 0.5 }}>
          <Typography variant="subtitle2" sx={{ fontWeight: 700, flexGrow: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {group.title}
          </Typography>
          <Chip label={countLabel} size="small" />
          <Tooltip title="Contraer">
            <IconButton size="small" onClick={onToggleCollapse}>
              <ChevronLeftIcon fontSize="small" />
            </IconButton>
          </Tooltip>
          {!isUnclassified ? (
            <IconButton size="small" onClick={(e) => setMenuAnchor(e.currentTarget)}>
              <MoreVertIcon fontSize="small" />
            </IconButton>
          ) : null}
        </Box>
        {group.summary ? (
          <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.5 }}>
            {group.summary}
          </Typography>
        ) : null}
      </Box>

      <Stack spacing={1} sx={{ minHeight: 40, maxHeight: 'calc(100vh - 340px)', overflowY: 'auto', pr: 0.5 }}>
        {visibleTasks.map((task) => (
          <DraggableTaskCard key={task.id} task={task} />
        ))}
        {visibleTasks.length === 0 ? (
          <Typography variant="caption" color="text.disabled" sx={{ textAlign: 'center', py: 2 }}>
            {group.tasks.length > 0 ? `${hiddenCount} tareas ocultas por el filtro` : 'Arrastra tareas aquí'}
          </Typography>
        ) : null}
      </Stack>

      <Menu anchorEl={menuAnchor} open={Boolean(menuAnchor)} onClose={() => setMenuAnchor(null)}>
        <MenuItem
          onClick={() => {
            setMenuAnchor(null);
            onRename();
          }}
        >
          Renombrar
        </MenuItem>
        <MenuItem
          onClick={() => {
            setMenuAnchor(null);
            onDelete();
          }}
        >
          Eliminar tema
        </MenuItem>
      </Menu>
    </Paper>
  );
}

export function RoadmapPage() {
  const [sections, setSections] = useState<RoadmapListSection[]>([]);
  const [meta, setMeta] = useState<{ totalTasks: number; persisted: boolean } | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isGenerating, setIsGenerating] = useState(false);
  const [isSummarizing, setIsSummarizing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saveState, setSaveState] = useState<SaveState>('idle');
  const [activeTask, setActiveTask] = useState<RoadmapTask | null>(null);
  const [rename, setRename] = useState<{ s: number; g: number } | null>(null);
  const [renameValue, setRenameValue] = useState('');
  const [confirmGenerate, setConfirmGenerate] = useState(false);
  const [hiddenStatuses, setHiddenStatuses] = useState<Set<string>>(loadHiddenStatuses);
  const [summaries, setSummaries] = useState<Record<string, string>>({});
  const [activeList, setActiveList] = useState(0);
  const [collapsedCols, setCollapsedCols] = useState<Set<string>>(new Set());

  const saveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 5 } }));

  function applyResponse(res: RoadmapResponse) {
    setSections(withCounts(res.lists));
    setMeta({ totalTasks: res.total_tasks, persisted: res.persisted });
  }

  function load() {
    setIsLoading(true);
    setError(null);
    getRoadmap()
      .then(applyResponse)
      .catch((caught: Error) => setError(caught.message))
      .finally(() => setIsLoading(false));
  }

  useEffect(() => {
    load();
    return () => {
      if (saveTimer.current) clearTimeout(saveTimer.current);
    };
  }, []);

  function persist(next: RoadmapListSection[]) {
    setSaveState('saving');
    if (saveTimer.current) clearTimeout(saveTimer.current);
    saveTimer.current = setTimeout(() => {
      const payload = next.flatMap((s) =>
        s.groups.map((g) => ({
          list_id: s.list_id,
          title: g.title,
          summary: g.summary,
          task_ids: g.tasks.map((t) => t.id),
        })),
      );
      saveRoadmap(payload)
        .then((res) => {
          applyResponse(res);
          setSaveState('saved');
        })
        .catch((caught: Error) => {
          setError(caught.message);
          setSaveState('error');
        });
    }, 600);
  }

  function mutate(next: RoadmapListSection[]) {
    const normalized = withCounts(next);
    setSections(normalized);
    persist(normalized);
  }

  function handleDragStart(event: DragStartEvent) {
    const id = String(event.active.id);
    const task = sections.flatMap((s) => s.groups.flatMap((g) => g.tasks)).find((t) => t.id === id) ?? null;
    setActiveTask(task);
  }

  function handleDragEnd(event: DragEndEvent) {
    setActiveTask(null);
    const { active, over } = event;
    if (!over) return;
    const taskId = String(active.id);
    const [, sStr, gStr] = String(over.id).split('-');
    const targetS = Number(sStr);
    const targetG = Number(gStr);
    if (Number.isNaN(targetS) || Number.isNaN(targetG)) return;

    // Find the task's current section + group.
    let sourceS = -1;
    let sourceG = -1;
    sections.forEach((s, si) =>
      s.groups.forEach((g, gi) => {
        if (g.tasks.some((t) => t.id === taskId)) {
          sourceS = si;
          sourceG = gi;
        }
      }),
    );
    if (sourceS === -1) return;
    // Only allow moving within the same list (cross-list moves are not supported).
    if (sourceS !== targetS) return;
    if (sourceG === targetG) return;

    const task = sections[sourceS].groups[sourceG].tasks.find((t) => t.id === taskId);
    if (!task) return;

    const next = sections.map((s, si) => {
      if (si !== targetS) return s;
      const groups = s.groups.map((g, gi) => {
        if (gi === sourceG) return { ...g, tasks: g.tasks.filter((t) => t.id !== taskId) };
        if (gi === targetG) return { ...g, tasks: [...g.tasks, task] };
        return g;
      });
      return { ...s, groups };
    });
    mutate(next);
  }

  function handleAddGroup(si: number) {
    const section = sections[si];
    const newGroup: RoadmapGroup = { list_id: section.list_id, title: 'Nuevo tema', summary: '', count: 0, tasks: [] };
    const unclassifiedAt = section.groups.findIndex((g) => g.title === UNCLASSIFIED);
    const insertAt = unclassifiedAt === -1 ? section.groups.length : unclassifiedAt;
    const groups = [...section.groups.slice(0, insertAt), newGroup, ...section.groups.slice(insertAt)];
    const next = sections.map((s, i) => (i === si ? { ...s, groups } : s));
    mutate(next);
    setRename({ s: si, g: insertAt });
    setRenameValue(newGroup.title);
  }

  function handleDeleteGroup(si: number, gi: number) {
    const section = sections[si];
    const removed = section.groups[gi];
    let groups = section.groups.filter((_, i) => i !== gi);
    if (removed.tasks.length > 0) {
      const unclassifiedIdx = groups.findIndex((g) => g.title === UNCLASSIFIED);
      if (unclassifiedIdx === -1) {
        groups = [...groups, { list_id: section.list_id, title: UNCLASSIFIED, summary: '', count: 0, tasks: removed.tasks }];
      } else {
        groups = groups.map((g, i) => (i === unclassifiedIdx ? { ...g, tasks: [...g.tasks, ...removed.tasks] } : g));
      }
    }
    mutate(sections.map((s, i) => (i === si ? { ...s, groups } : s)));
  }

  function commitRename() {
    if (!rename) return;
    const value = renameValue.trim() || 'Sin título';
    const next = sections.map((s, si) =>
      si === rename.s ? { ...s, groups: s.groups.map((g, gi) => (gi === rename.g ? { ...g, title: value } : g)) } : s,
    );
    setRename(null);
    mutate(next);
  }

  function runGenerate() {
    setConfirmGenerate(false);
    setIsGenerating(true);
    setError(null);
    generateRoadmap()
      .then((res) => {
        applyResponse(res);
        setSaveState('saved');
      })
      .catch((caught: Error) => setError(caught.message))
      .finally(() => setIsGenerating(false));
  }

  function runSummaries() {
    setIsSummarizing(true);
    setError(null);
    const payload = sections.map((s) => ({
      list_id: s.list_id,
      list_name: s.list_name,
      tasks: s.groups
        .flatMap((g) => g.tasks)
        .filter((t) => !hiddenStatuses.has(t.status.toLowerCase()))
        .map((t) => ({ name: t.name, status: t.status, description: t.description ?? null })),
    }));
    summarizeRoadmap(payload)
      .then((res) => {
        setSummaries((prev) => {
          const next = { ...prev };
          res.summaries.forEach((item) => {
            next[item.list_id] = item.summary;
          });
          return next;
        });
      })
      .catch((caught: Error) => setError(caught.message))
      .finally(() => setIsSummarizing(false));
  }

  function toggleStatus(status: string) {
    setHiddenStatuses((prev) => {
      const next = new Set(prev);
      if (next.has(status)) next.delete(status);
      else next.add(status);
      window.localStorage.setItem(HIDDEN_STATUSES_KEY, JSON.stringify([...next]));
      return next;
    });
  }

  function toggleCollapse(key: string) {
    setCollapsedCols((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  const hasContent = sections.length > 0;
  const neverGenerated = meta && !meta.persisted && !hasContent;
  const active = sections.length ? Math.min(activeList, sections.length - 1) : 0;
  const activeSection = sections[active];

  const statusCounts = new Map<string, number>();
  sections.forEach((s) =>
    s.groups.forEach((g) =>
      g.tasks.forEach((t) => {
        const st = t.status.toLowerCase();
        statusCounts.set(st, (statusCounts.get(st) ?? 0) + 1);
      }),
    ),
  );
  const statuses = [...statusCounts.keys()].sort();

  return (
    <Box>
      <Box sx={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 2, mb: 2, flexWrap: 'wrap' }}>
        <Box>
          <Typography variant="h4" gutterBottom>
            Roadmap
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Tus tareas de ClickUp por lista, agrupadas por tema. Arrastra tarjetas dentro de cada lista y filtra por estado.
            {meta ? ` ${meta.totalTasks} tareas en ${sections.length} listas.` : ''}
          </Typography>
        </Box>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
          <SaveIndicator state={saveState} />
          {hasContent ? (
            <Button
              variant="text"
              startIcon={isSummarizing ? <CircularProgress size={16} color="inherit" /> : <SummarizeIcon />}
              onClick={runSummaries}
              disabled={isSummarizing}
            >
              {isSummarizing ? 'Resumiendo…' : 'Generar resúmenes'}
            </Button>
          ) : null}
          <Button
            variant="outlined"
            startIcon={isGenerating ? <CircularProgress size={16} color="inherit" /> : <AutoAwesomeIcon />}
            onClick={() => (hasContent ? setConfirmGenerate(true) : runGenerate())}
            disabled={isGenerating || isLoading}
          >
            {isGenerating ? 'Generando…' : hasContent ? 'Reagrupar con IA' : 'Generar con IA'}
          </Button>
        </Box>
      </Box>

      {error ? (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      ) : null}

      {isLoading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', mt: 8 }}>
          <CircularProgress />
        </Box>
      ) : null}

      {!isLoading && neverGenerated ? (
        <Paper variant="outlined" sx={{ p: 6, textAlign: 'center', bgcolor: 'background.default' }}>
          <AutoAwesomeIcon color="primary" sx={{ fontSize: 40, mb: 1 }} />
          <Typography variant="h6" gutterBottom>
            Aún no has generado tu roadmap
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
            Deja que la IA agrupe tus {meta?.totalTasks ?? 0} tareas por tema en cada lista. Luego
            podrás ajustarlo arrastrando tarjetas y filtrar por estado.
          </Typography>
          <Button
            variant="contained"
            startIcon={isGenerating ? <CircularProgress size={16} color="inherit" /> : <AutoAwesomeIcon />}
            onClick={runGenerate}
            disabled={isGenerating}
          >
            {isGenerating ? 'Generando…' : 'Generar con IA'}
          </Button>
        </Paper>
      ) : null}

      {!isLoading && hasContent && statuses.length > 0 ? (
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap', mb: 2 }}>
          <Typography variant="caption" color="text.secondary" sx={{ mr: 0.5 }}>
            Filtrar por estado:
          </Typography>
          {statuses.map((s) => {
            const hidden = hiddenStatuses.has(s);
            return (
              <Chip
                key={s}
                label={`${s} (${statusCounts.get(s)})`}
                size="small"
                color={hidden ? 'default' : statusColor(s)}
                variant={hidden ? 'outlined' : 'filled'}
                onClick={() => toggleStatus(s)}
                sx={{ opacity: hidden ? 0.5 : 1, cursor: 'pointer' }}
              />
            );
          })}
        </Box>
      ) : null}

      {!isLoading && hasContent && activeSection ? (
        <>
          <Tabs
            value={active}
            onChange={(_e, v) => setActiveList(v)}
            variant="scrollable"
            scrollButtons="auto"
            sx={{ mb: 2, borderBottom: 1, borderColor: 'divider' }}
          >
            {sections.map((s) => (
              <Tab key={s.list_id} label={`${s.list_name} (${s.total_tasks})`} />
            ))}
          </Tabs>

          <Box sx={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 2, mb: 1.5, flexWrap: 'wrap' }}>
            <Box sx={{ flexGrow: 1 }}>
              {summaries[activeSection.list_id] ? (
                <Typography variant="body2" color="text.secondary" sx={{ maxWidth: 900 }}>
                  {summaries[activeSection.list_id]}
                </Typography>
              ) : (
                <Typography variant="caption" color="text.disabled">
                  Pulsa “Generar resúmenes” para un resumen de esta lista.
                </Typography>
              )}
            </Box>
            <Button size="small" startIcon={<AddIcon />} onClick={() => handleAddGroup(active)}>
              Añadir tema
            </Button>
          </Box>

          <DndContext sensors={sensors} onDragStart={handleDragStart} onDragEnd={handleDragEnd}>
            <Box sx={{ display: 'flex', gap: 2, overflowX: 'auto', pb: 2, alignItems: 'flex-start' }}>
              {activeSection.groups.map((group, gi) => {
                const key = `${activeSection.list_id}:${gi}`;
                return (
                  <DroppableColumn
                    key={key}
                    group={group}
                    droppableId={`col-${active}-${gi}`}
                    hiddenStatuses={hiddenStatuses}
                    collapsed={collapsedCols.has(key)}
                    onToggleCollapse={() => toggleCollapse(key)}
                    onRename={() => {
                      setRename({ s: active, g: gi });
                      setRenameValue(group.title);
                    }}
                    onDelete={() => handleDeleteGroup(active, gi)}
                  />
                );
              })}
            </Box>
            <DragOverlay>
              {activeTask ? (
                <Card variant="outlined" sx={{ width: 260, boxShadow: 4 }}>
                  <TaskCardBody task={activeTask} />
                </Card>
              ) : null}
            </DragOverlay>
          </DndContext>
        </>
      ) : null}

      <Dialog open={rename !== null} onClose={() => setRename(null)} maxWidth="xs" fullWidth>
        <DialogTitle>Renombrar tema</DialogTitle>
        <DialogContent>
          <TextField
            autoFocus
            fullWidth
            value={renameValue}
            onChange={(e) => setRenameValue(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') commitRename();
            }}
            sx={{ mt: 1 }}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setRename(null)}>Cancelar</Button>
          <Button variant="contained" onClick={commitRename}>
            Guardar
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog open={confirmGenerate} onClose={() => setConfirmGenerate(false)} maxWidth="xs" fullWidth>
        <DialogTitle>¿Reagrupar con IA?</DialogTitle>
        <DialogContent>
          <DialogContentText>
            Esto vuelve a agrupar todas las tareas de cada lista desde cero y reemplaza tu organización manual actual.
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setConfirmGenerate(false)}>Cancelar</Button>
          <Button variant="contained" color="warning" onClick={runGenerate}>
            Reagrupar
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}

function SaveIndicator({ state }: { state: SaveState }) {
  if (state === 'saving') {
    return (
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, color: 'text.secondary' }}>
        <CircularProgress size={14} color="inherit" />
        <Typography variant="caption">Guardando…</Typography>
      </Box>
    );
  }
  if (state === 'saved') {
    return (
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, color: 'success.main' }}>
        <CloudDoneIcon sx={{ fontSize: 16 }} />
        <Typography variant="caption">Guardado</Typography>
      </Box>
    );
  }
  return null;
}
