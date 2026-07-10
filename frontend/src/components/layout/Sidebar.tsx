import { useLocation, useNavigate } from 'react-router-dom';
import {
  Badge,
  Box,
  Divider,
  Drawer,
  IconButton,
  List,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Toolbar,
  Tooltip,
  Typography,
  useMediaQuery,
  useTheme,
} from '@mui/material';
import ChevronLeftIcon from '@mui/icons-material/ChevronLeft';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import { useActionsStore } from '../../stores/actionsStore';
import { useUiStore } from '../../stores/uiStore';
import { DRAWER_WIDTH, NAV_ITEMS, RAIL_WIDTH, isPathActive } from './navConfig';

/**
 * Render the primary navigation.
 *
 * Responsive behaviour:
 *   - md and up: a permanent drawer that can collapse to an icon rail.
 *   - below md: a temporary overlay drawer toggled from the header hamburger,
 *     always shown at full width (never collapsed to a rail on a phone).
 */
export function Sidebar() {
  const navigate = useNavigate();
  const location = useLocation();
  const theme = useTheme();
  const isDesktop = useMediaQuery(theme.breakpoints.up('md'));
  const pendingCount = useActionsStore((state) => state.pendingActions.length);
  const { collapsed, mobileOpen, toggleCollapsed, setMobileOpen } = useUiStore();

  // On mobile the drawer always shows full labels; only the desktop rail collapses.
  const showLabels = !isDesktop || !collapsed;
  const width = isDesktop && collapsed ? RAIL_WIDTH : DRAWER_WIDTH;

  function handleNavigate(path: string): void {
    navigate(path);
    if (!isDesktop) setMobileOpen(false);
  }

  const content = (
    <>
      <Toolbar
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: showLabels ? 'space-between' : 'center',
          px: [1.5],
        }}
      >
        {showLabels ? <Typography variant="h6" noWrap>Assistant</Typography> : null}
        {isDesktop ? (
          <IconButton onClick={toggleCollapsed} size="small" aria-label={collapsed ? 'Expandir menú' : 'Colapsar menú'}>
            {collapsed ? <ChevronRightIcon /> : <ChevronLeftIcon />}
          </IconButton>
        ) : null}
      </Toolbar>
      <Divider />
      <List>
        {NAV_ITEMS.map((item) => {
          const selected = isPathActive(location.pathname, item.path);
          const iconEl = item.badge ? (
            <Badge badgeContent={pendingCount} color="error">
              <Box sx={{ display: 'flex' }}>{item.icon}</Box>
            </Badge>
          ) : (
            item.icon
          );
          const button = (
            <ListItemButton
              selected={selected}
              onClick={() => handleNavigate(item.path)}
              sx={{
                minHeight: 48,
                justifyContent: showLabels ? 'initial' : 'center',
                px: 2.5,
                mx: 1,
                borderRadius: 1,
              }}
            >
              <ListItemIcon
                sx={{
                  minWidth: 0,
                  mr: showLabels ? 3 : 'auto',
                  justifyContent: 'center',
                }}
              >
                {iconEl}
              </ListItemIcon>
              {showLabels ? <ListItemText primary={item.label} /> : null}
            </ListItemButton>
          );
          return (
            <Box component="li" key={item.path} sx={{ listStyle: 'none' }}>
              {showLabels ? button : <Tooltip title={item.label} placement="right">{button}</Tooltip>}
            </Box>
          );
        })}
      </List>
    </>
  );

  if (isDesktop) {
    return (
      <Drawer
        variant="permanent"
        sx={{
          width,
          flexShrink: 0,
          '& .MuiDrawer-paper': {
            width,
            boxSizing: 'border-box',
            overflowX: 'hidden',
            transition: theme.transitions.create('width', {
              easing: theme.transitions.easing.sharp,
              duration: theme.transitions.duration.enteringScreen,
            }),
          },
        }}
      >
        {content}
      </Drawer>
    );
  }

  return (
    <Drawer
      variant="temporary"
      open={mobileOpen}
      onClose={() => setMobileOpen(false)}
      ModalProps={{ keepMounted: true }}
      sx={{
        '& .MuiDrawer-paper': { width: DRAWER_WIDTH, boxSizing: 'border-box' },
      }}
    >
      {content}
    </Drawer>
  );
}
