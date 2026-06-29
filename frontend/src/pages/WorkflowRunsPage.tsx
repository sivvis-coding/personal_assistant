import { useEffect, useState } from 'react';
import { listWorkflowRuns } from '../api/workflowRuns';
import { ErrorState } from '../components/ErrorState';
import { LoadingState } from '../components/LoadingState';
import type { WorkflowRunItem } from '../types/workflow';

/**
 * Render workflow run history page.
 *
 * Parameters:
 *   None.
 *
 * Returns:
 *   JSX workflow history page.
 *
 * Edge cases:
 *   Empty workflow history renders explicit empty state.
 */
export function WorkflowRunsPage() {
  const [items, setItems] = useState<WorkflowRunItem[]>([]);
  const [ticketFilter, setTicketFilter] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  /**
   * Purpose: Load workflow history using current filter.
   * Parameters: None.
   * Return value: None.
   * Edge cases: Empty filter loads all workflow runs.
   */
  function loadHistory(): void {
    setIsLoading(true);
    setError(null);
    listWorkflowRuns(50, ticketFilter.trim() || undefined)
      .then((response) => setItems(response.items))
      .catch((caught: Error) => setError(caught.message))
      .finally(() => setIsLoading(false));
  }

  useEffect(() => {
    loadHistory();
  }, []);

  return (
    <section className="panel workflow-history">
      <h1>Historial de workflows</h1>
      <div className="filter-row">
        <label>
          Filtrar por ticket
          <input value={ticketFilter} onChange={(event) => setTicketFilter(event.target.value)} placeholder="Fresh ticket ID" />
        </label>
        <button type="button" onClick={loadHistory}>Actualizar</button>
      </div>
      {isLoading ? <LoadingState message="Loading workflow runs..." /> : null}
      {error ? <ErrorState message={error} /> : null}
      {!isLoading && !error && items.length === 0 ? <p>No workflow runs found.</p> : null}
      {!isLoading && !error && items.length > 0 ? (
        <table>
          <thead>
            <tr>
              <th>Workflow</th>
              <th>Ticket</th>
              <th>Status</th>
              <th>Started</th>
              <th>Error</th>
            </tr>
          </thead>
          <tbody>
            {items.map((item) => (
              <tr key={item.id}>
                <td>{item.workflow_name}</td>
                <td>{item.fresh_ticket_id ?? '-'}</td>
                <td><span className={`status ${item.status}`}>{item.status}</span></td>
                <td>{new Date(item.started_at).toLocaleString()}</td>
                <td>{item.error ?? '-'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : null}
    </section>
  );
}
