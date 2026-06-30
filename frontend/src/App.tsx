import { BrowserRouter, Route, Routes } from 'react-router-dom';
import { ThemeProvider } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';
import { appTheme } from './theme/theme';
import { AppShell } from './components/layout/AppShell';
import { DashboardPage } from './pages/DashboardPage';
import { ChatPage } from './pages/ChatPage';
import { ConversationHistoryPage } from './pages/ConversationHistoryPage';
import { ConversationDetailPage } from './pages/ConversationDetailPage';
import { ActionsPage } from './pages/ActionsPage';
import { TicketsPage } from './pages/TicketsPage';
import { TicketDetailPage } from './pages/TicketDetailPage';
import { SettingsPage } from './pages/SettingsPage';

/**
 * Render root application with routing and MUI theme.
 *
 * Parameters:
 *   None.
 *
 * Returns:
 *   JSX application root.
 */
export function App() {
  return (
    <ThemeProvider theme={appTheme}>
      <CssBaseline />
      <BrowserRouter>
        <AppShell>
          <Routes>
            <Route path="/" element={<DashboardPage />} />
            <Route path="/assistant" element={<ChatPage />} />
            <Route path="/assistant/history" element={<ConversationHistoryPage />} />
            <Route path="/assistant/history/:id" element={<ConversationDetailPage />} />
            <Route path="/actions" element={<ActionsPage />} />
            <Route path="/tickets" element={<TicketsPage />} />
            <Route path="/tickets/:id" element={<TicketDetailPage />} />
            <Route path="/settings" element={<SettingsPage />} />
          </Routes>
        </AppShell>
      </BrowserRouter>
    </ThemeProvider>
  );
}
