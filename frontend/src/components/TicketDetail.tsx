import type { Ticket } from '../types/ticket';

interface TicketDetailProps {
  ticket: Ticket;
  source: string;
}

/**
 * Render ticket detail information.
 *
 * Parameters:
 *   ticket: Ticket to display.
 *   source: Source used by backend.
 *
 * Returns:
 *   JSX ticket detail block.
 *
 * Edge cases:
 *   Missing description renders a clear fallback.
 */
export function TicketDetail({ ticket, source }: TicketDetailProps) {
  return (
    <section className="panel">
      <h2>{ticket.subject}</h2>
      <p><strong>Source:</strong> {source}</p>
      <p><strong>Status:</strong> {ticket.status}</p>
      <p><strong>Priority:</strong> {ticket.priority}</p>
      <p><strong>Requester:</strong> {ticket.requester.name} {ticket.requester.email ? `<${ticket.requester.email}>` : ''}</p>
      <p><strong>Description:</strong></p>
      <pre>{ticket.description || 'No description available.'}</pre>
    </section>
  );
}
