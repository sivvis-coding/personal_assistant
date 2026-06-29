import type { Ticket } from '../types/ticket';

interface TicketListProps {
  tickets: Ticket[];
  selectedTicketId?: string | null;
  onSelectTicket: (ticketId: string) => void;
}

/**
 * Render selectable ticket list.
 *
 * Parameters:
 *   tickets: Tickets to display.
 *   selectedTicketId: Currently selected ticket ID.
 *   onSelectTicket: Callback executed when a ticket is selected.
 *
 * Returns:
 *   JSX ticket list.
 *
 * Edge cases:
 *   Empty ticket list renders an explicit empty state.
 */
export function TicketList({ tickets, selectedTicketId, onSelectTicket }: TicketListProps) {
  if (tickets.length === 0) {
    return <p>No tickets found.</p>;
  }

  return (
    <div className="ticket-list">
      {tickets.map((ticket) => (
        <button
          className={ticket.id === selectedTicketId ? 'ticket-card selected' : 'ticket-card'}
          key={ticket.id}
          onClick={() => onSelectTicket(ticket.id)}
          type="button"
        >
          <strong>{ticket.subject}</strong>
          <span>ID: {ticket.id}</span>
          <span>Status: {ticket.status}</span>
          <span>Priority: {ticket.priority}</span>
        </button>
      ))}
    </div>
  );
}
