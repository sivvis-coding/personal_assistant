import { Box, Toolbar } from '@mui/material';
import { Sidebar } from './Sidebar';
import { Header } from './Header';

interface AppShellProps {
  children: React.ReactNode;
}

/**
 * Render the main application shell with sidebar, header and content area.
 *
 * Parameters:
 *   children: Page content to render inside the shell.
 *
 * Returns:
 *   JSX layout shell.
 *
 * Edge cases:
 *   Content area reserves space for the fixed header.
 */
export function AppShell({ children }: AppShellProps) {
  return (
    <Box sx={{ display: 'flex' }}>
      <Header />
      <Sidebar />
      <Box
        component="main"
        sx={{
          flexGrow: 1,
          bgcolor: 'background.default',
          minHeight: '100vh',
          p: 3,
        }}
      >
        <Toolbar />
        {children}
      </Box>
    </Box>
  );
}
