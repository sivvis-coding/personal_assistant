import { useState } from 'react';
import { useLocation } from 'react-router-dom';
import {
  AppBar,
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
import KeyIcon from '@mui/icons-material/Key';
import MenuIcon from '@mui/icons-material/Menu';
import { useUiStore } from '../../stores/uiStore';
import { DRAWER_WIDTH, RAIL_WIDTH, pageTitleForPath } from './navConfig';

/**
 * Render the application header.
 *
 * The AppBar width/offset are derived from the live sidebar state (rail vs full)
 * so header and content stay aligned when the rail collapses. On mobile it shows
 * a hamburger that opens the temporary navigation drawer.
 *
 * Edge cases:
 *   API key is stored only in localStorage for local development convenience.
 */
export function Header() {
  const location = useLocation();
  const { collapsed, setMobileOpen } = useUiStore();
  const [keyDialogOpen, setKeyDialogOpen] = useState(false);
  const [localKey, setLocalKey] = useState(window.localStorage.getItem('LOCAL_APP_API_KEY') ?? '');

  const title = pageTitleForPath(location.pathname);
  const desktopWidth = collapsed ? RAIL_WIDTH : DRAWER_WIDTH;

  function saveLocalKey(value: string): void {
    window.localStorage.setItem('LOCAL_APP_API_KEY', value);
    setLocalKey(value);
  }

  return (
    <>
      <AppBar
        position="fixed"
        sx={{
          width: { md: `calc(100% - ${desktopWidth}px)` },
          ml: { md: `${desktopWidth}px` },
          transition: (theme) => theme.transitions.create(['width', 'margin'], {
            easing: theme.transitions.easing.sharp,
            duration: theme.transitions.duration.enteringScreen,
          }),
        }}
      >
        <Toolbar>
          <IconButton
            color="inherit"
            edge="start"
            aria-label="Abrir menú"
            onClick={() => setMobileOpen(true)}
            sx={{ mr: 2, display: { md: 'none' } }}
          >
            <MenuIcon />
          </IconButton>
          <Typography variant="h6" component="div" sx={{ flexGrow: 1 }} noWrap>
            {title}
          </Typography>
          <IconButton color="inherit" onClick={() => setKeyDialogOpen(true)} aria-label="API key">
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
