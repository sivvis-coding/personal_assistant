import { createTheme } from '@mui/material/styles';

/**
 * Create the application MUI theme (polished light mode).
 *
 * Centralises the design tokens — palette, typography scale, rounded shape and
 * component defaults — so surfaces read as one consistent system instead of the
 * stock MUI defaults. Dark mode can be layered on later via a second palette.
 */
export const appTheme = createTheme({
  palette: {
    mode: 'light',
    primary: {
      main: '#2563eb',
      dark: '#1d4ed8',
      light: '#60a5fa',
    },
    secondary: {
      main: '#7c3aed',
    },
    success: { main: '#16a34a' },
    warning: { main: '#d97706' },
    error: { main: '#dc2626' },
    background: {
      default: '#f4f6f8',
      paper: '#ffffff',
    },
    text: {
      primary: '#1e293b',
      secondary: '#64748b',
    },
    divider: 'rgba(15, 23, 42, 0.10)',
  },
  shape: {
    borderRadius: 10,
  },
  typography: {
    fontFamily: '"Inter", "Roboto", "Helvetica", "Arial", sans-serif',
    h4: { fontWeight: 700, letterSpacing: '-0.02em' },
    h5: { fontWeight: 700, letterSpacing: '-0.01em' },
    h6: { fontWeight: 700 },
    subtitle2: { fontWeight: 600 },
    button: { fontWeight: 600 },
  },
  components: {
    MuiButton: {
      defaultProps: {
        variant: 'contained',
        disableElevation: true,
      },
      styleOverrides: {
        root: {
          textTransform: 'none',
          borderRadius: 8,
        },
      },
    },
    MuiCard: {
      defaultProps: {
        elevation: 0,
        variant: 'outlined',
      },
    },
    MuiPaper: {
      styleOverrides: {
        // Soften the default paper border so outlined surfaces feel lighter.
        outlined: {
          borderColor: 'rgba(15, 23, 42, 0.10)',
        },
      },
    },
    MuiAppBar: {
      defaultProps: {
        elevation: 0,
        color: 'inherit',
      },
      styleOverrides: {
        root: {
          backgroundColor: '#ffffff',
          color: '#1e293b',
          borderBottom: '1px solid rgba(15, 23, 42, 0.10)',
        },
      },
    },
    MuiDrawer: {
      styleOverrides: {
        paper: {
          borderColor: 'rgba(15, 23, 42, 0.10)',
        },
      },
    },
    MuiChip: {
      styleOverrides: {
        root: { fontWeight: 500 },
      },
    },
    MuiListItemButton: {
      styleOverrides: {
        root: {
          '&.Mui-selected': {
            backgroundColor: 'rgba(37, 99, 235, 0.10)',
            '&:hover': {
              backgroundColor: 'rgba(37, 99, 235, 0.16)',
            },
          },
        },
      },
    },
    MuiTooltip: {
      defaultProps: {
        arrow: true,
      },
    },
  },
});
