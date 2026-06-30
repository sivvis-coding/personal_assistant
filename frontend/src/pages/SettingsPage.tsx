import { useEffect, useState } from 'react';
import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Alert,
  Autocomplete,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Divider,
  IconButton,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import SaveIcon from '@mui/icons-material/Save';
import RefreshIcon from '@mui/icons-material/Refresh';
import SearchIcon from '@mui/icons-material/Search';
import DeleteIcon from '@mui/icons-material/Delete';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import AutoFixHighIcon from '@mui/icons-material/AutoFixHigh';
import { getSettings, updateSettings } from '../api/settings';
import {
  discoverClickUpListFields,
  discoverClickUpTeamLists,
  discoverClickUpTeams,
  discoverFreshservice,
  discoverFreshserviceWorkspaces,
  suggestClickUpDescriptions,
} from '../api/discovery';
import type { AppSettings, ClickUpCustomFieldConfig, ClickUpListConfig } from '../types/settings';
import type { ClickUpCustomField, ClickUpList, ClickUpTeam, FreshserviceAgent, FreshserviceWorkspace } from '../types/discovery';

const defaultSettings: AppSettings = {
  fresh_base_url: '',
  fresh_api_key: '',
  fresh_assigned_agent_id: '',
  fresh_assigned_agent_field: 'agent_id',
  fresh_workspace_id: '',
  clickup_api_key: '',
  clickup_team_id: '',
  clickup_lists: [],
  agent_system_prompt: '',
  openai_api_key: '',
  openai_model: 'gpt-5.4',
};

interface DiscoveryState<T> {
  loading: boolean;
  options: T[];
  error: string | null;
}

interface ListFieldsState {
  loading: boolean;
  fields: ClickUpCustomField[];
  error: string | null;
  discovered: boolean;
}

interface ListSuggestState {
  loading: boolean;
  error: string | null;
}

export function SettingsPage() {
  const [settings, setSettings] = useState<AppSettings>(defaultSettings);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const [clickupTeamDiscovery, setClickupTeamDiscovery] = useState<DiscoveryState<ClickUpTeam>>({
    loading: false,
    options: [],
    error: null,
  });
  const [selectedTeam, setSelectedTeam] = useState<ClickUpTeam | null>(null);
  const [clickupDiscovery, setClickupDiscovery] = useState<DiscoveryState<ClickUpList>>({
    loading: false,
    options: [],
    error: null,
  });
  const [freshserviceDiscovery, setFreshserviceDiscovery] = useState<DiscoveryState<FreshserviceAgent>>({
    loading: false,
    options: [],
    error: null,
  });
  const [workspaceDiscovery, setWorkspaceDiscovery] = useState<DiscoveryState<FreshserviceWorkspace>>({
    loading: false,
    options: [],
    error: null,
  });
  // Per-list field discovery state keyed by list ID
  const [listFieldsState, setListFieldsState] = useState<Record<string, ListFieldsState>>({});
  // Per-list AI suggestion state keyed by list ID
  const [listSuggestState, setListSuggestState] = useState<Record<string, ListSuggestState>>({});

  useEffect(() => {
    loadSettings();
  }, []);

  async function loadSettings(): Promise<void> {
    setIsLoading(true);
    setError(null);
    try {
      const data = await getSettings();
      setSettings({ ...defaultSettings, ...data });
    } catch (caught) {
      setError((caught as Error).message);
    } finally {
      setIsLoading(false);
    }
  }

  async function handleSave(): Promise<void> {
    setIsSaving(true);
    setError(null);
    setSuccess(false);
    try {
      await updateSettings(settings);
      setSuccess(true);
    } catch (caught) {
      setError((caught as Error).message);
    } finally {
      setIsSaving(false);
    }
  }

  function updateField<K extends keyof AppSettings>(field: K, value: AppSettings[K]): void {
    setSettings((current) => ({ ...current, [field]: value }));
  }

  async function handleDiscoverClickUpTeams(): Promise<void> {
    if (!settings.clickup_api_key.trim()) return;
    setClickupTeamDiscovery({ loading: true, options: [], error: null });
    setClickupDiscovery({ loading: false, options: [], error: null });
    setSelectedTeam(null);
    try {
      const response = await discoverClickUpTeams(settings.clickup_api_key);
      setClickupTeamDiscovery({ loading: false, options: response.teams, error: null });
    } catch (caught) {
      setClickupTeamDiscovery({ loading: false, options: [], error: (caught as Error).message });
    }
  }

  async function handleDiscoverClickUpLists(teamId: string): Promise<void> {
    if (!settings.clickup_api_key.trim()) return;
    setClickupDiscovery({ loading: true, options: [], error: null });
    try {
      const response = await discoverClickUpTeamLists(settings.clickup_api_key, teamId);
      setClickupDiscovery({ loading: false, options: response.lists, error: null });
    } catch (caught) {
      setClickupDiscovery({ loading: false, options: [], error: (caught as Error).message });
    }
  }

  async function handleDiscoverFreshservice(): Promise<void> {
    if (!settings.fresh_base_url.trim() || !settings.fresh_api_key.trim()) return;
    setFreshserviceDiscovery({ loading: true, options: [], error: null });
    try {
      const response = await discoverFreshservice(settings.fresh_base_url, settings.fresh_api_key);
      setFreshserviceDiscovery({ loading: false, options: response.agents, error: null });
    } catch (caught) {
      setFreshserviceDiscovery({ loading: false, options: [], error: (caught as Error).message });
    }
  }

  async function handleDiscoverFreshserviceWorkspaces(): Promise<void> {
    if (!settings.fresh_base_url.trim() || !settings.fresh_api_key.trim()) return;
    setWorkspaceDiscovery({ loading: true, options: [], error: null });
    try {
      const response = await discoverFreshserviceWorkspaces(
        settings.fresh_base_url,
        settings.fresh_api_key,
      );
      setWorkspaceDiscovery({ loading: false, options: response.workspaces, error: null });
    } catch (caught) {
      setWorkspaceDiscovery({ loading: false, options: [], error: (caught as Error).message });
    }
  }

  function addClickUpList(list: ClickUpList): void {
    if (settings.clickup_lists.some((l) => l.id === list.id)) return;
    const newList: ClickUpListConfig = {
      id: list.id,
      name: list.name,
      description: '',
      custom_fields: [],
    };
    updateField('clickup_lists', [...settings.clickup_lists, newList]);
  }

  function removeClickUpList(listId: string): void {
    updateField('clickup_lists', settings.clickup_lists.filter((l) => l.id !== listId));
    setListFieldsState((prev) => {
      const next = { ...prev };
      delete next[listId];
      return next;
    });
  }

  function updateListField(listId: string, key: keyof ClickUpListConfig, value: string): void {
    updateField(
      'clickup_lists',
      settings.clickup_lists.map((l) => (l.id === listId ? { ...l, [key]: value } : l)),
    );
  }

  function updateCustomFieldDescription(listId: string, fieldId: string, description: string): void {
    updateField(
      'clickup_lists',
      settings.clickup_lists.map((l) => {
        if (l.id !== listId) return l;
        const existing = l.custom_fields.find((f) => f.field_id === fieldId);
        if (existing) {
          return {
            ...l,
            custom_fields: l.custom_fields.map((f) =>
              f.field_id === fieldId ? { ...f, description } : f,
            ),
          };
        }
        return l;
      }),
    );
  }

  async function handleDiscoverListFields(listId: string): Promise<void> {
    if (!settings.clickup_api_key.trim()) return;
    setListFieldsState((prev) => ({
      ...prev,
      [listId]: { loading: true, fields: [], error: null, discovered: false },
    }));
    try {
      const response = await discoverClickUpListFields(settings.clickup_api_key, listId);
      setListFieldsState((prev) => ({
        ...prev,
        [listId]: { loading: false, fields: response.fields, error: null, discovered: true },
      }));
      // Merge discovered fields into list config, preserving existing descriptions
      const existingList = settings.clickup_lists.find((l) => l.id === listId);
      if (!existingList) return;
      const mergedFields: ClickUpCustomFieldConfig[] = response.fields.map((f) => {
        const existing = existingList.custom_fields.find((cf) => cf.field_id === f.id);
        return {
          field_id: f.id,
          field_name: f.name,
          description: existing?.description ?? '',
        };
      });
      updateField(
        'clickup_lists',
        settings.clickup_lists.map((l) =>
          l.id === listId ? { ...l, custom_fields: mergedFields } : l,
        ),
      );
    } catch (caught) {
      setListFieldsState((prev) => ({
        ...prev,
        [listId]: { loading: false, fields: [], error: (caught as Error).message, discovered: false },
      }));
    }
  }

  async function handleSuggestDescriptions(listId: string): Promise<void> {
    const list = settings.clickup_lists.find((l) => l.id === listId);
    if (!list) return;
    setListSuggestState((prev) => ({ ...prev, [listId]: { loading: true, error: null } }));
    try {
      const discoveredFields = listFieldsState[listId]?.fields ?? [];
      const response = await suggestClickUpDescriptions(
        settings.clickup_api_key,
        list.name,
        list.description,
        discoveredFields,
      );
      updateField(
        'clickup_lists',
        settings.clickup_lists.map((l) => {
          if (l.id !== listId) return l;
          const updatedFields = l.custom_fields.map((f) => {
            const suggestion = response.field_descriptions.find((s) => s.field_id === f.field_id);
            return suggestion && suggestion.description ? { ...f, description: suggestion.description } : f;
          });
          return {
            ...l,
            description: response.routing_description || l.description,
            custom_fields: updatedFields,
          };
        }),
      );
      setListSuggestState((prev) => ({ ...prev, [listId]: { loading: false, error: null } }));
    } catch (caught) {
      setListSuggestState((prev) => ({
        ...prev,
        [listId]: { loading: false, error: (caught as Error).message },
      }));
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
        Configuración
      </Typography>

      {error ? (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      ) : null}

      {success ? (
        <Alert severity="success" sx={{ mb: 2 }}>
          Configuración guardada. Reinicia el backend (docker compose restart backend) para aplicar los cambios.
        </Alert>
      ) : null}

      {/* Agent system prompt */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            Prompt del agente
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            Instrucciones adicionales que el agente seguirá además de su comportamiento base. Úsalo para ajustar el tono, prioridades, o flujos específicos de tu equipo.
          </Typography>
          <TextField
            label="Instrucciones personalizadas"
            multiline
            minRows={4}
            maxRows={12}
            value={settings.agent_system_prompt}
            onChange={(event) => updateField('agent_system_prompt', event.target.value)}
            fullWidth
            placeholder="Ejemplo: Prioriza siempre los tickets de tipo 'incident'. Cuando propongas enviar un ticket al backlog, usa un tono formal con el cliente."
          />
        </CardContent>
      </Card>

      {/* Freshservice */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            Freshservice
          </Typography>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            <TextField
              label="Workspace URL"
              placeholder="https://tuempresa.freshservice.com"
              value={settings.fresh_base_url}
              onChange={(event) => updateField('fresh_base_url', event.target.value)}
              fullWidth
            />
            <TextField
              label="API Key"
              type="password"
              value={settings.fresh_api_key}
              onChange={(event) => updateField('fresh_api_key', event.target.value)}
              fullWidth
            />
            <Box sx={{ display: 'flex', gap: 1 }}>
              <Button
                variant="outlined"
                startIcon={<SearchIcon />}
                disabled={workspaceDiscovery.loading || !settings.fresh_base_url.trim() || !settings.fresh_api_key.trim()}
                onClick={() => void handleDiscoverFreshserviceWorkspaces()}
              >
                {workspaceDiscovery.loading ? <CircularProgress size={20} /> : 'Descubrir workspaces'}
              </Button>
              <Button
                variant="outlined"
                startIcon={<SearchIcon />}
                disabled={freshserviceDiscovery.loading || !settings.fresh_base_url.trim() || !settings.fresh_api_key.trim()}
                onClick={() => void handleDiscoverFreshservice()}
              >
                {freshserviceDiscovery.loading ? <CircularProgress size={20} /> : 'Descubrir agentes'}
              </Button>
            </Box>

            {workspaceDiscovery.error ? (
              <Alert severity="error">{workspaceDiscovery.error}</Alert>
            ) : null}

            {workspaceDiscovery.options.length > 0 ? (
              <Autocomplete
                options={workspaceDiscovery.options}
                getOptionLabel={(option) => option.name}
                value={
                  workspaceDiscovery.options.find((workspace) => workspace.id === settings.fresh_workspace_id) || null
                }
                onChange={(_, newValue) => updateField('fresh_workspace_id', newValue?.id ?? '')}
                renderInput={(params) => (
                  <TextField {...params} label="Workspace" placeholder="Buscar workspace..." helperText="Filtra tickets por workspace" />
                )}
              />
            ) : null}

            {freshserviceDiscovery.error ? (
              <Alert severity="error">{freshserviceDiscovery.error}</Alert>
            ) : null}

            {freshserviceDiscovery.options.length > 0 ? (
              <Autocomplete
                options={freshserviceDiscovery.options}
                getOptionLabel={(option) => `${option.name} (${option.email ?? option.id})`}
                value={
                  freshserviceDiscovery.options.find((agent) => agent.id === settings.fresh_assigned_agent_id) || null
                }
                onChange={(_, newValue) => updateField('fresh_assigned_agent_id', newValue?.id ?? '')}
                renderInput={(params) => (
                  <TextField {...params} label="Agente asignado" placeholder="Buscar agente..." />
                )}
              />
            ) : null}

            <TextField
              label="Assigned Agent Field"
              value={settings.fresh_assigned_agent_field}
              onChange={(event) => updateField('fresh_assigned_agent_field', event.target.value)}
              fullWidth
              helperText="Usa agent_id para Freshservice"
            />
          </Box>
        </CardContent>
      </Card>

      {/* ClickUp */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            ClickUp
          </Typography>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            <TextField
              label="API Key"
              type="password"
              value={settings.clickup_api_key}
              onChange={(event) => updateField('clickup_api_key', event.target.value)}
              fullWidth
            />
            <TextField
              label="Team ID"
              value={settings.clickup_team_id}
              onChange={(event) => updateField('clickup_team_id', event.target.value)}
              fullWidth
              helperText="Opcional si ya seleccionaste listas"
            />

            {/* List discovery + selector: two-step (team → lists) */}
            <Box>
              <Typography variant="subtitle2" gutterBottom>
                Listas configuradas
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                Añade las listas que usa tu equipo. Para cada una puedes indicar cuándo usarla y describir sus campos personalizados para que el agente sepa cómo rellenarlos.
              </Typography>

              {/* Step 1: pick workspace */}
              <Box sx={{ display: 'flex', gap: 1, mb: 1 }}>
                <Button
                  variant="outlined"
                  startIcon={clickupTeamDiscovery.loading ? <CircularProgress size={16} /> : <SearchIcon />}
                  disabled={clickupTeamDiscovery.loading || !settings.clickup_api_key.trim()}
                  onClick={() => void handleDiscoverClickUpTeams()}
                >
                  {clickupTeamDiscovery.loading ? 'Buscando workspaces…' : 'Descubrir workspaces'}
                </Button>
              </Box>

              {clickupTeamDiscovery.error ? (
                <Alert severity="error" sx={{ mb: 1 }}>{clickupTeamDiscovery.error}</Alert>
              ) : null}

              {clickupTeamDiscovery.options.length > 0 ? (
                <Box sx={{ display: 'flex', gap: 1, mb: 2, alignItems: 'flex-start' }}>
                  <Autocomplete
                    options={clickupTeamDiscovery.options}
                    getOptionLabel={(option) => option.name}
                    value={selectedTeam}
                    onChange={(_, newValue) => {
                      setSelectedTeam(newValue);
                      setClickupDiscovery({ loading: false, options: [], error: null });
                    }}
                    renderInput={(params) => (
                      <TextField {...params} label="Workspace" placeholder="Selecciona un workspace…" size="small" />
                    )}
                    sx={{ flex: 1 }}
                  />
                  {/* Step 2: load lists for selected workspace */}
                  <Button
                    variant="outlined"
                    startIcon={clickupDiscovery.loading ? <CircularProgress size={16} /> : <SearchIcon />}
                    disabled={!selectedTeam || clickupDiscovery.loading}
                    onClick={() => selectedTeam && void handleDiscoverClickUpLists(selectedTeam.id)}
                    sx={{ mt: 0.5 }}
                  >
                    {clickupDiscovery.loading ? 'Cargando listas…' : 'Cargar listas'}
                  </Button>
                </Box>
              ) : null}

              {clickupDiscovery.error ? (
                <Alert severity="error" sx={{ mb: 1 }}>{clickupDiscovery.error}</Alert>
              ) : null}

              {clickupDiscovery.options.length > 0 ? (
                <Autocomplete
                  options={clickupDiscovery.options.filter(
                    (list) => !settings.clickup_lists.some((l) => l.id === list.id),
                  )}
                  getOptionLabel={(option) => option.name}
                  value={null}
                  onChange={(_, newValue) => {
                    if (newValue) addClickUpList(newValue);
                  }}
                  renderInput={(params) => (
                    <TextField {...params} label="Añadir lista" placeholder="Buscar y añadir lista…" size="small" />
                  )}
                  sx={{ mb: 2 }}
                />
              ) : null}

              {/* Configured lists */}
              {settings.clickup_lists.length === 0 ? (
                <Typography variant="body2" color="text.secondary">
                  No hay listas configuradas. Descubre las listas disponibles y añádelas.
                </Typography>
              ) : (
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                  {settings.clickup_lists.map((list) => {
                    const fieldsState = listFieldsState[list.id];
                    return (
                      <Accordion key={list.id} defaultExpanded={false} variant="outlined">
                        <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flex: 1, mr: 1 }}>
                            <Typography variant="subtitle2" sx={{ flex: 1 }}>
                              {list.name}
                            </Typography>
                            {list.description && (
                              <Chip label="con descripción" size="small" color="primary" variant="outlined" />
                            )}
                            {list.custom_fields.length > 0 && (
                              <Chip
                                label={`${list.custom_fields.length} campos`}
                                size="small"
                                color="secondary"
                                variant="outlined"
                              />
                            )}
                          </Box>
                          <Tooltip title="Eliminar lista">
                            <IconButton
                              size="small"
                              onClick={(e) => {
                                e.stopPropagation();
                                removeClickUpList(list.id);
                              }}
                            >
                              <DeleteIcon fontSize="small" />
                            </IconButton>
                          </Tooltip>
                        </AccordionSummary>
                        <AccordionDetails>
                          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                            <TextField
                              label="Descripción de uso"
                              multiline
                              minRows={2}
                              value={list.description}
                              onChange={(e) => updateListField(list.id, 'description', e.target.value)}
                              fullWidth
                              placeholder="Ej: Usar para bugs reportados por usuarios en producción. No usar para solicitudes de funcionalidad nueva."
                              helperText="El agente usa esto para decidir a qué lista enviar cada tarea."
                            />

                            {/* Custom fields */}
                            <Box>
                              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                                <Typography variant="body2" color="text.secondary" sx={{ flex: 1 }}>
                                  Campos personalizados
                                </Typography>
                                <Button
                                  size="small"
                                  variant="outlined"
                                  startIcon={fieldsState?.loading ? <CircularProgress size={14} /> : <SearchIcon />}
                                  disabled={fieldsState?.loading || !settings.clickup_api_key.trim()}
                                  onClick={() => void handleDiscoverListFields(list.id)}
                                >
                                  {fieldsState?.loading ? 'Descubriendo...' : 'Descubrir campos'}
                                </Button>
                                <Tooltip title="Genera automáticamente la descripción de la lista y de sus campos usando IA">
                                  <span>
                                    <Button
                                      size="small"
                                      variant="outlined"
                                      color="secondary"
                                      startIcon={
                                        listSuggestState[list.id]?.loading ? (
                                          <CircularProgress size={14} />
                                        ) : (
                                          <AutoFixHighIcon fontSize="small" />
                                        )
                                      }
                                      disabled={listSuggestState[list.id]?.loading}
                                      onClick={() => void handleSuggestDescriptions(list.id)}
                                    >
                                      {listSuggestState[list.id]?.loading ? 'Generando...' : 'Sugerir con IA'}
                                    </Button>
                                  </span>
                                </Tooltip>
                              </Box>
                              {listSuggestState[list.id]?.error ? (
                                <Alert severity="error" sx={{ mb: 1 }}>{listSuggestState[list.id].error}</Alert>
                              ) : null}

                              {fieldsState?.error ? (
                                <Alert severity="error" sx={{ mb: 1 }}>{fieldsState.error}</Alert>
                              ) : null}

                              {list.custom_fields.length === 0 && !fieldsState?.discovered ? (
                                <Typography variant="body2" color="text.secondary">
                                  Descubre los campos de esta lista para que el agente sepa cómo rellenarlos.
                                </Typography>
                              ) : null}

                              {list.custom_fields.length > 0 ? (
                                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
                                  {list.custom_fields.map((field) => (
                                    <Box key={field.field_id} sx={{ display: 'flex', flexDirection: 'column', gap: 0.5 }}>
                                      <Typography variant="caption" color="text.secondary">
                                        {field.field_name}
                                        <Box component="span" sx={{ ml: 1, opacity: 0.5 }}>
                                          ({field.field_id.slice(0, 8)}...)
                                        </Box>
                                      </Typography>
                                      <TextField
                                        size="small"
                                        value={field.description}
                                        onChange={(e) =>
                                          updateCustomFieldDescription(list.id, field.field_id, e.target.value)
                                        }
                                        fullWidth
                                        placeholder={`Ej: Prioridad del bug. Valores posibles: P0 (crítico), P1 (alto), P2 (medio), P3 (bajo).`}
                                        helperText="El agente usa esta descripción para saber qué valor poner en este campo."
                                      />
                                    </Box>
                                  ))}
                                </Box>
                              ) : null}
                            </Box>
                          </Box>
                        </AccordionDetails>
                      </Accordion>
                    );
                  })}
                </Box>
              )}
            </Box>
          </Box>
        </CardContent>
      </Card>

      {/* OpenAI */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            OpenAI
          </Typography>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            <TextField
              label="API Key"
              type="password"
              value={settings.openai_api_key}
              onChange={(event) => updateField('openai_api_key', event.target.value)}
              fullWidth
            />
            <TextField
              label="Model"
              value={settings.openai_model}
              onChange={(event) => updateField('openai_model', event.target.value)}
              fullWidth
            />
          </Box>
        </CardContent>
      </Card>

      <Divider sx={{ my: 2 }} />

      <Box sx={{ display: 'flex', gap: 2 }}>
        <Button
          variant="contained"
          startIcon={<SaveIcon />}
          disabled={isSaving}
          onClick={() => void handleSave()}
        >
          Guardar configuración
        </Button>
        <Button variant="outlined" startIcon={<RefreshIcon />} onClick={() => void loadSettings()}>
          Recargar
        </Button>
      </Box>
    </Box>
  );
}
