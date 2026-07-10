import DashboardIcon from '@mui/icons-material/Dashboard';
import ChatIcon from '@mui/icons-material/Chat';
import AssignmentTurnedInIcon from '@mui/icons-material/AssignmentTurnedIn';
import ConfirmationNumberIcon from '@mui/icons-material/ConfirmationNumber';
import LinkIcon from '@mui/icons-material/Link';
import MapIcon from '@mui/icons-material/Map';
import AutoStoriesIcon from '@mui/icons-material/AutoStories';
import CalendarMonthIcon from '@mui/icons-material/CalendarMonth';
import SettingsIcon from '@mui/icons-material/Settings';

export const DRAWER_WIDTH = 240;
export const RAIL_WIDTH = 64;

export interface NavItem {
  label: string;
  /** Path used both for navigation and as the active-route prefix. */
  path: string;
  icon: React.ReactNode;
  /** Show the pending-actions badge on this item. */
  badge?: boolean;
}

/**
 * Single source of truth for the primary navigation. Both the sidebar (menu)
 * and the header (page title) derive from this list, so they can never drift
 * out of sync the way the old duplicated arrays did.
 */
export const NAV_ITEMS: NavItem[] = [
  { label: 'Dashboard', path: '/', icon: <DashboardIcon /> },
  { label: 'Agente', path: '/assistant', icon: <ChatIcon /> },
  { label: 'Acciones', path: '/actions', icon: <AssignmentTurnedInIcon />, badge: true },
  { label: 'Tickets', path: '/tickets', icon: <ConfirmationNumberIcon /> },
  { label: 'Tareas', path: '/linked-tasks', icon: <LinkIcon /> },
  { label: 'Roadmap', path: '/roadmap', icon: <MapIcon /> },
  { label: 'Insights', path: '/insights', icon: <AutoStoriesIcon /> },
  { label: 'Calendario de horas', path: '/time-calendar', icon: <CalendarMonthIcon /> },
  { label: 'Configuración', path: '/settings', icon: <SettingsIcon /> },
];

// Titles for sub-routes that are not top-level nav entries.
const EXTRA_TITLES: Array<{ prefix: string; title: string }> = [
  { prefix: '/assistant/history', title: 'Historial de conversaciones' },
];

/** True when `pathname` is (or is nested under) `path`. */
export function isPathActive(pathname: string, path: string): boolean {
  if (path === '/') return pathname === '/';
  return pathname === path || pathname.startsWith(`${path}/`);
}

/**
 * Resolve the page title for the current location from the nav config, matching
 * the most specific (longest) prefix so nested routes get the right title.
 */
export function pageTitleForPath(pathname: string): string {
  const candidates = [
    ...EXTRA_TITLES.map((e) => ({ path: e.prefix, title: e.title })),
    ...NAV_ITEMS.map((i) => ({ path: i.path, title: i.label })),
  ].sort((a, b) => b.path.length - a.path.length);

  const match = candidates.find((c) => isPathActive(pathname, c.path));
  return match?.title ?? 'Local Assistant';
}
