import { useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import {
  AppBar,
  Box,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  IconButton,
  TextField,
  Toolbar,
  Typography,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import KeyIcon from '@mui/icons-material/Key';
import { useChatStore } from '../../stores/chatStore';

/**
 * Render the application header with page title and contextual actions.
 *
 * Parameters:
 *   None.
 *
 * Returns:
 *   JSX header component.
 *
 * Edge cases:
 *   API key is stored only in localStorage for local development convenience.
 */
export function Header() {
  const location = useLocation();
  const navigate = useNavigate();
  const [keyDialogOpen, setKeyDialogOpen] = useState(false);
  const [localKey, setLocalKey] = useState(window.localStorage.getItem('LOCAL_APP_API_KEY') ?? '');
  const resetChat = useChatStore((state) => state.resetChat);

  const pageTitles: Record<string, string> = {
    '/': 'Dashboard',
    '/assistant': 'Agente',
    '/actions': 'Acciones pendientes',
    '/tickets': 'Tickets',
    '/assistant/history': 'Historial de conversaciones',
  };

  const title = Object.entries(pageTitles).find(([path]) => location.pathname === path || location.pathname.startsWith(`${path}/`))?.[1] ?? 'Local Assistant';

  /**
   * Persist local API key for backend requests.
   */
  function saveLocalKey(value: string): void {
    window.localStorage.setItem('LOCAL_APP_API_KEY', value);
    setLocalKey(value);
  }

  /**
   * Reset the active chat and navigate to a fresh conversation.
   */
  function handleNewChat(): void {
    resetChat();
    navigate('/assistant');
  }

  return (
    <>
      <AppBar
        position="fixed"
        sx={{
          width: { sm: `calc(100% - 240px)` },
          ml: { sm: '240px' },
        }}
      >
        <Toolbar>
          <Typography variant="h6" component="div" sx={{ flexGrow: 1 }}>
            {title}
          </Typography>
          {location.pathname.startsWith('/assistant') ? (
            <Button
              color="inherit"
              startIcon={<AddIcon />}
              onClick={handleNewChat}
              sx={{ mr: 2 }}
            >
              Nuevo chat
            </Button>
          ) : null}
          <IconButton color="inherit" onClick={() => setKeyDialogOpen(true)}>
            <KeyIcon />
          </IconButton>
        </Toolbar>
      </AppBar>

      <Dialog open={keyDialogOpen} onClose={() => setKeyDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Local API key</DialogTitle>
        <DialogContent>
          <TextField
            autoFocus
            fullWidth
            label="API key"
            margin="dense"
            placeholder="Optional"
            type="password"
            value={localKey}
            onChange={(event) => saveLocalKey(event.target.value)}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setKeyDialogOpen(false)}>Cerrar</Button>
        </DialogActions>
      </Dialog>
    </>
  );
}
