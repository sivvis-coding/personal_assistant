import { useEffect, useState } from 'react';
import { getWeekTime } from '../api/clickup';
import { ErrorState } from '../components/ErrorState';
import { LoadingState } from '../components/LoadingState';
import type { WeekTimeResponse } from '../types/clickup';

/**
 * Render current week ClickUp time entries.
 *
 * Parameters:
 *   None.
 *
 * Returns:
 *   JSX weekly time page.
 *
 * Edge cases:
 *   Missing ClickUp credentials render mock data from backend.
 */
export function WeekTimePage() {
  const [report, setReport] = useState<WeekTimeResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getWeekTime().then(setReport).catch((caught: Error) => setError(caught.message));
  }, []);

  if (error) return <ErrorState message={error} />;
  if (!report) return <LoadingState message="Loading week time..." />;

  return (
    <section className="panel">
      <h1>Horas semana</h1>
      <p>{report.week_start} → {report.week_end}</p>
      <p><strong>Total:</strong> {report.total_hours}h</p>
      <p><strong>Source:</strong> {report.source}</p>
      <ul>
        {report.entries.map((entry) => (
          <li key={`${entry.task_id}-${entry.date}`}>{entry.date}: {entry.task_name} — {entry.hours}h</li>
        ))}
      </ul>
    </section>
  );
}
