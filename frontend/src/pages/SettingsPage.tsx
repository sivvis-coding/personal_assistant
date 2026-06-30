import { useEffect, useState } from 'react';
import {
  Alert,
  Autocomplete,
  Box,
  Button,
  Card,
  CardContent,
  CircularProgress,
  Divider,
  TextField,
  Typography,
} from '@mui/material';
import SaveIcon from '@mui/icons-material/Save';
import RefreshIcon from '@mui/icons-material/Refresh';
import SearchIcon from '@mui/icons-material/Search';
import { getSettings, updateSettings } from '../api/settings';
import {
  discoverClickUp,
  discoverFreshservice,
  discoverFreshserviceWorkspaces,
} from '../api/discovery';
import type { AppSettings } from '../types/settings';
import type { ClickUpList, FreshserviceAgent, FreshserviceWorkspace } from '../types/discovery';

const defaultSettings: AppSettings = {
  fresh_base_url: '',
  fresh_api_key: '',
  fresh_assigned_agent_id: '',
  fresh_assigned_agent_field: 'agent_id',
  fresh_workspace_id: '',
  clickup_api_key: '',
  clickup_team_id: '',
  clickup_list_id: '',
  openai_api_key: '',
  openai_model: 'gpt-5.4',
};

interface DiscoveryState<T> {
  loading: boolean;
  options: T[];
  error: string | null;
}

/**
 * Render the settings page for configuring integrations with discovery.
 *
 * Parameters:
 *   None.
 *
 * Returns:
 *   JSX settings page.
 *
 * Edge cases:
 *   Settings are saved to the database but require a backend restart to take effect.
 */
export function SettingsPage() {
  const [settings, setSettings] = useState<AppSettings>(defaultSettings);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

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

  function updateField<K extends keyof AppSettings>(field: K, value: string): void {
    setSettings((current) => ({ ...current, [field]: value }));
  }

  async function handleDiscoverClickUp(): Promise<void> {
    if (!settings.clickup_api_key.trim()) return;
    setClickupDiscovery({ loading: true, options: [], error: null });
    try {
      const response = await discoverClickUp(settings.clickup_api_key);
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
            <Box sx={{ display: 'flex', gap: 1 }}>
              <Button
                variant="outlined"
                startIcon={<SearchIcon />}
                disabled={clickupDiscovery.loading || !settings.clickup_api_key.trim()}
                onClick={() => void handleDiscoverClickUp()}
              >
                {clickupDiscovery.loading ? <CircularProgress size={20} /> : 'Descubrir listas'}
              </Button>
            </Box>

            {clickupDiscovery.error ? (
              <Alert severity="error">{clickupDiscovery.error}</Alert>
            ) : null}

            {clickupDiscovery.options.length > 0 ? (
              <Autocomplete
                options={clickupDiscovery.options}
                getOptionLabel={(option) => option.name}
                value={clickupDiscovery.options.find((list) => list.id === settings.clickup_list_id) || null}
                onChange={(_, newValue) => updateField('clickup_list_id', newValue?.id ?? '')}
                renderInput={(params) => (
                  <TextField {...params} label="Lista de ClickUp" placeholder="Buscar lista..." />
                )}
              />
            ) : null}

            <TextField
              label="Team ID"
              value={settings.clickup_team_id}
              onChange={(event) => updateField('clickup_team_id', event.target.value)}
              fullWidth
              helperText="Opcional si ya seleccionaste una lista"
            />
          </Box>
        </CardContent>
      </Card>

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
