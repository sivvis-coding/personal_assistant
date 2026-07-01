import { useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import {
  Box,
  Divider,
  Drawer,
  IconButton,
  List,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Toolbar,
  Typography,
  Badge,
} from '@mui/material';
import DashboardIcon from '@mui/icons-material/Dashboard';
import ChatIcon from '@mui/icons-material/Chat';
import AssignmentTurnedInIcon from '@mui/icons-material/AssignmentTurnedIn';
import ConfirmationNumberIcon from '@mui/icons-material/ConfirmationNumber';
import ChevronLeftIcon from '@mui/icons-material/ChevronLeft';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import SettingsIcon from '@mui/icons-material/Settings';
import LinkIcon from '@mui/icons-material/Link';
import { useActionsStore } from '../../stores/actionsStore';

const DRAWER_WIDTH = 240;
const COLLAPSED_WIDTH = 64;

interface NavItem {
  label: string;
  path: string;
  icon: React.ReactNode;
  badge?: number;
}

/**
 * Render the application sidebar with navigation.
 *
 * Parameters:
 *   None.
 *
 * Returns:
 *   JSX sidebar component.
 *
 * Edge cases:
 *   Sidebar can be collapsed to save horizontal space.
 */
export function Sidebar() {
  const navigate = useNavigate();
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(false);
  const pendingCount = useActionsStore((state) => state.pendingActions.length);

  const navItems: NavItem[] = [
    { label: 'Dashboard', path: '/', icon: <DashboardIcon /> },
    { label: 'Agente', path: '/assistant', icon: <ChatIcon /> },
    { label: 'Acciones', path: '/actions', icon: <AssignmentTurnedInIcon />, badge: pendingCount },
    { label: 'Tickets', path: '/tickets', icon: <ConfirmationNumberIcon /> },
    { label: 'Tareas', path: '/linked-tasks', icon: <LinkIcon /> },
    { label: 'Configuración', path: '/settings', icon: <SettingsIcon /> },
  ];

  const width = collapsed ? COLLAPSED_WIDTH : DRAWER_WIDTH;

  return (
    <Drawer
      variant="permanent"
      sx={{
        width,
        flexShrink: 0,
        '& .MuiDrawer-paper': {
          width,
          boxSizing: 'border-box',
          transition: (theme) => theme.transitions.create('width', {
            easing: theme.transitions.easing.sharp,
            duration: theme.transitions.duration.enteringScreen,
          }),
          overflowX: 'hidden',
        },
      }}
    >
      <Toolbar
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: collapsed ? 'center' : 'space-between',
          px: [1],
        }}
      >
        {!collapsed ? <Typography variant="h6">Assistant</Typography> : null}
        <IconButton onClick={() => setCollapsed((value) => !value)} size="small">
          {collapsed ? <ChevronRightIcon /> : <ChevronLeftIcon />}
        </IconButton>
      </Toolbar>
      <Divider />
      <List>
        {navItems.map((item) => {
          const selected = location.pathname === item.path || location.pathname.startsWith(`${item.path}/`);
          return (
            <ListItemButton
              key={item.path}
              selected={selected}
              onClick={() => navigate(item.path)}
              sx={{
                minHeight: 48,
                justifyContent: collapsed ? 'center' : 'initial',
                px: 2.5,
              }}
            >
              <ListItemIcon
                sx={{
                  minWidth: 0,
                  mr: collapsed ? 'auto' : 3,
                  justifyContent: 'center',
                }}
              >
                {item.badge ? (
                  <Badge badgeContent={item.badge} color="error">
                    <Box>{item.icon}</Box>
                  </Badge>
                ) : (
                  item.icon
                )}
              </ListItemIcon>
              {!collapsed ? <ListItemText primary={item.label} /> : null}
            </ListItemButton>
          );
        })}
      </List>
    </Drawer>
  );
}
