import { createTheme } from '@mui/material/styles';

/**
 * Create the application MUI theme.
 *
 * Parameters:
 *   None.
 *
 * Returns:
 *   Configured MUI theme.
 *
 * Edge cases:
 *   Theme is light mode by default; dark mode can be added later.
 */
export const appTheme = createTheme({
  palette: {
    mode: 'light',
    primary: {
      main: '#1976d2',
    },
    secondary: {
      main: '#dc004e',
    },
    background: {
      default: '#f5f5f5',
      paper: '#ffffff',
    },
  },
  typography: {
    fontFamily: '"Roboto", "Helvetica", "Arial", sans-serif',
  },
  components: {
    MuiButton: {
      defaultProps: {
        variant: 'contained',
      },
    },
    MuiCard: {
      defaultProps: {
        elevation: 1,
      },
    },
  },
});
