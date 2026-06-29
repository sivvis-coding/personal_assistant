import { useEffect, useState } from 'react';
import { listTickets, type TicketListScope } from '../api/tickets';
import { ErrorState } from '../components/ErrorState';
import { LoadingState } from '../components/LoadingState';
import { TicketList } from '../components/TicketList';
import type { Ticket } from '../types/ticket';

interface TicketsPageProps {
  selectedTicketId: string | null;
  onSelectTicket: (ticketId: string) => void;
}

/**
 * Render tickets page and load ticket list.
 *
 * Parameters:
 *   selectedTicketId: Current selected ticket ID.
 *   onSelectTicket: Selection callback.
 *
 * Returns:
 *   JSX tickets page.
 *
 * Edge cases:
 *   Backend errors render readable error state.
 */
export function TicketsPage({ selectedTicketId, onSelectTicket }: TicketsPageProps) {
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [source, setSource] = useState<string>('');
  const [scope, setScope] = useState<TicketListScope>('mine');
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setIsLoading(true);
    setError(null);
    listTickets(scope)
      .then((response) => {
        setTickets(response.items);
        setSource(response.source);
      })
      .catch((caught: Error) => setError(caught.message))
      .finally(() => setIsLoading(false));
  }, [scope]);

  return (
    <section>
      <h1>Tickets</h1>
      <label>
        View
        <select value={scope} onChange={(event) => setScope(event.target.value as TicketListScope)}>
          <option value="mine">Assigned to me</option>
          <option value="all">All tickets</option>
        </select>
      </label>
      <p>Source: {source}</p>
      {isLoading ? <LoadingState message="Loading tickets..." /> : null}
      {error ? <ErrorState message={error} /> : null}
      {!isLoading && !error ? (
        <TicketList tickets={tickets} selectedTicketId={selectedTicketId} onSelectTicket={onSelectTicket} />
      ) : null}
    </section>
  );
}
