import { useState } from 'react';
import { TicketDetailPage } from './pages/TicketDetailPage';
import { TicketsPage } from './pages/TicketsPage';
import { WeekTimePage } from './pages/WeekTimePage';
import { WorkflowRunsPage } from './pages/WorkflowRunsPage';
import './styles.css';

type Page = 'tickets' | 'week-time' | 'workflow-runs';

/**
 * Render root SPA shell.
 *
 * Parameters:
 *   None.
 *
 * Returns:
 *   JSX application shell.
 *
 * Edge cases:
 *   API key is stored only in localStorage for local development convenience.
 */
export function App() {
  const [page, setPage] = useState<Page>('tickets');
  const [selectedTicketId, setSelectedTicketId] = useState<string | null>(null);
  const [localKey, setLocalKey] = useState(window.localStorage.getItem('LOCAL_APP_API_KEY') ?? '');

  /**
   * Purpose: Persist local API key for backend requests.
   * Parameters: value is the key entered by the user.
   * Return value: None.
   * Edge cases: Empty value disables sending the header from the frontend.
   */
  function saveLocalKey(value: string): void {
    window.localStorage.setItem('LOCAL_APP_API_KEY', value);
    setLocalKey(value);
  }

  return (
    <main className="app-shell">
      <header>
        <h1>Local Assistant</h1>
        <nav>
          <button type="button" onClick={() => setPage('tickets')}>Tickets</button>
          <button type="button" onClick={() => setPage('week-time')}>Horas semana</button>
          <button type="button" onClick={() => setPage('workflow-runs')}>Historial workflows</button>
        </nav>
        <label className="api-key">
          Local API key
          <input value={localKey} onChange={(event) => saveLocalKey(event.target.value)} placeholder="Optional" />
        </label>
      </header>
      <div className="layout">
        {page === 'tickets' ? (
          <>
            <TicketsPage selectedTicketId={selectedTicketId} onSelectTicket={setSelectedTicketId} />
            <TicketDetailPage ticketId={selectedTicketId} />
          </>
        ) : null}
        {page === 'week-time' ? (
          <WeekTimePage />
        ) : null}
        {page === 'workflow-runs' ? (
          <WorkflowRunsPage />
        ) : null}
      </div>
    </main>
  );
}
