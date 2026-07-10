import { Box, Toolbar } from '@mui/material';
import { Sidebar } from './Sidebar';
import { Header } from './Header';

interface AppShellProps {
  children: React.ReactNode;
}

/**
 * Render the main application shell: header, responsive sidebar and content area.
 *
 * The sidebar participates in the flex row (permanent on desktop, an overlay on
 * mobile), so the content area simply grows to fill the remaining space — no
 * hardcoded widths to keep in sync. The spacer Toolbar reserves room under the
 * fixed header.
 */
export function AppShell({ children }: AppShellProps) {
  return (
    <Box sx={{ display: 'flex', minHeight: '100vh' }}>
      <Header />
      <Sidebar />
      <Box
        component="main"
        sx={{
          flexGrow: 1,
          minWidth: 0,
          bgcolor: 'background.default',
          minHeight: '100vh',
          p: { xs: 2, md: 3 },
        }}
      >
        <Toolbar />
        {children}
      </Box>
    </Box>
  );
}
