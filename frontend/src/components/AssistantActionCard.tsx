import type { AssistantAction } from '../types/assistant';

interface AssistantActionCardProps {
  action: AssistantAction;
  disabled: boolean;
  onApprove: (actionId: string) => void;
  onReject: (actionId: string) => void;
}

/**
 * Format minutes as hours and minutes for display.
 *
 * Parameters:
 *   minutes: Duration in whole minutes.
 *
 * Returns:
 *   Human-readable string such as "2h 30m".
 *
 * Edge cases:
 *   Returns "0m" for zero minutes.
 */
function formatDuration(minutes: number): string {
  const hours = Math.floor(minutes / 60);
  const remainingMinutes = minutes % 60;
  if (hours === 0) return `${remainingMinutes}m`;
  if (remainingMinutes === 0) return `${hours}h`;
  return `${hours}h ${remainingMinutes}m`;
}

/**
 * Render the payload preview for a save_time_entry action.
 *
 * Parameters:
 *   payload: Action payload.
 *
 * Returns:
 *   JSX preview list.
 *
 * Edge cases:
 *   Returns null when the payload is not a save_time_entry shape.
 */
function TimeEntryPreview({ payload }: { payload: Record<string, unknown> }) {
  const taskName = typeof payload.task_name === 'string' ? payload.task_name : '';
  const clientName = typeof payload.client_name === 'string' ? payload.client_name : '';
  const start = typeof payload.start_datetime === 'string' ? payload.start_datetime : '';
  const end = typeof payload.end_datetime === 'string' ? payload.end_datetime : '';

  return (
    <dl className="time-entry-preview">
      {taskName ? <><dt>Tarea</dt><dd>{taskName}</dd></> : null}
      {clientName ? <><dt>Cliente</dt><dd>{clientName}</dd></> : null}
      {start ? <><dt>Inicio</dt><dd>{start}</dd></> : null}
      {end ? <><dt>Fin</dt><dd>{end}</dd></> : null}
    </dl>
  );
}

/**
 * Render one assistant action that requires user review.
 *
 * Parameters:
 *   action: Assistant action to display.
 *   disabled: Whether controls are disabled while an operation runs.
 *   onApprove: Callback executed when the action is approved.
 *   onReject: Callback executed when the action is rejected.
 *
 * Returns:
 *   JSX action card.
 *
 * Edge cases:
 *   Result payload is shown only after execution creates one.
 */
export function AssistantActionCard({ action, disabled, onApprove, onReject }: AssistantActionCardProps) {
  const isCompleted = action.status === 'completed';
  const isRejected = action.status === 'rejected';
  const isFailed = action.status === 'failed';

  return (
    <article className={`assistant-action-card action-${action.action_type} ${isFailed ? 'action-failed' : ''}`}>
      <h3>{action.title}</h3>
      <p>{action.description}</p>
      {action.ticket_id ? <p><strong>Ticket:</strong> {action.ticket_id}</p> : null}
      {action.action_type === 'save_time_entry' ? <TimeEntryPreview payload={action.payload} /> : null}
      {action.status === 'proposed' ? (
        <div className="actions">
          <button disabled={disabled} type="button" onClick={() => onApprove(action.id)}>Aprobar</button>
          <button disabled={disabled} className="danger-action" type="button" onClick={() => onReject(action.id)}>Rechazar</button>
        </div>
      ) : (
        <span className={`action-badge ${isCompleted ? 'completed' : ''} ${isRejected ? 'rejected' : ''} ${isFailed ? 'failed' : ''}`}>
          {isCompleted ? '✅ Completada' : isRejected ? '❌ Rechazada' : isFailed ? '❌ Fallida' : action.status}
        </span>
      )}
      {action.result ? (
        <div className={`action-result ${action.result.error || isFailed ? 'error' : ''}`}>
          {action.result.error || isFailed ? <strong>❌ Error al ejecutar:</strong> : null}
          <pre>{JSON.stringify(action.result, null, 2)}</pre>
        </div>
      ) : null}
      {isFailed && !action.result ? <p className="action-fallback-error">❌ La acción falló. Revisa el mensaje del asistente.</p> : null}
    </article>
  );
}
