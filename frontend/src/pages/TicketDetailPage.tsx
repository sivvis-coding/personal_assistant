import { useEffect, useState } from 'react';
import { approveClickUpTask, draftTicketReply, getTicket, prepareClickUpTask, summarizeTicket } from '../api/tickets';
import { ClickUpTaskResult } from '../components/ClickUpTaskResult';
import { DraftEditor } from '../components/DraftEditor';
import { ErrorState } from '../components/ErrorState';
import { LoadingState } from '../components/LoadingState';
import { SummaryBlock } from '../components/SummaryBlock';
import { TicketDetail } from '../components/TicketDetail';
import { UserStoryReview } from '../components/UserStoryReview';
import type { ReplyDraft, TicketSummary, UserStory } from '../types/ai';
import type { CreateClickUpTaskWorkflowResponse } from '../types/clickup';
import type { Ticket } from '../types/ticket';
import type { WorkflowState } from '../types/workflow';

interface TicketDetailPageProps {
  ticketId: string | null;
}

/**
 * Render ticket detail workflow page.
 *
 * Parameters:
 *   ticketId: Selected ticket ID.
 *
 * Returns:
 *   JSX detail page.
 *
 * Edge cases:
 *   Null ticket ID renders a selection prompt.
 */
export function TicketDetailPage({ ticketId }: TicketDetailPageProps) {
  const [ticket, setTicket] = useState<Ticket | null>(null);
  const [source, setSource] = useState('');
  const [summary, setSummary] = useState<TicketSummary | null>(null);
  const [draft, setDraft] = useState<ReplyDraft | null>(null);
  const [reviewUserStory, setReviewUserStory] = useState<UserStory | null>(null);
  const [clickUpResult, setClickUpResult] = useState<CreateClickUpTaskWorkflowResponse | null>(null);
  const [state, setState] = useState<WorkflowState>('idle');
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!ticketId) return;
    setState('loading');
    setError(null);
    getTicket(ticketId)
      .then((response) => {
        setTicket(response.ticket);
        setSource(response.source);
        setState('success');
      })
      .catch((caught: Error) => {
        setError(caught.message);
        setState('error');
      });
  }, [ticketId]);

  if (!ticketId) return <p>Select a ticket to see details.</p>;
  if (state === 'loading') return <LoadingState message="Loading ticket..." />;
  if (error) return <ErrorState message={error} />;
  if (!ticket) return <p>No ticket loaded.</p>;

  /**
   * Purpose: Prepare a ClickUp task proposal without creating external state.
   * Parameters: None.
   * Return value: None.
   * Edge cases: Existing ClickUp tasks are not checked until approval step.
   */
  function handlePrepareClickUpTask(): void {
    prepareClickUpTask(ticket.id).then((response) => {
      setReviewUserStory(response.user_story);
      setClickUpResult(null);
    }).catch((caught: Error) => setError(caught.message));
  }

  /**
   * Purpose: Approve reviewed user story and create ClickUp task.
   * Parameters: None.
   * Return value: None.
   * Edge cases: Approval is ignored when no user story is loaded.
   */
  function handleApproveClickUpTask(): void {
    if (!reviewUserStory) return;
    approveClickUpTask(ticket.id, reviewUserStory).then(setClickUpResult).catch((caught: Error) => setError(caught.message));
  }

  return (
    <section>
      <TicketDetail ticket={ticket} source={source} />
      <div className="actions">
        <button type="button" onClick={() => summarizeTicket(ticket.id).then((response) => setSummary(response.summary))}>Resumir</button>
        <button type="button" onClick={() => draftTicketReply(ticket.id).then((response) => setDraft(response.draft))}>Generar respuesta</button>
        <button type="button" onClick={handlePrepareClickUpTask}>Preparar tarea ClickUp</button>
      </div>
      <SummaryBlock summary={summary} />
      <DraftEditor draft={draft} onChange={setDraft} />
      <UserStoryReview userStory={reviewUserStory} onChange={setReviewUserStory} onApprove={handleApproveClickUpTask} />
      <ClickUpTaskResult result={clickUpResult} />
    </section>
  );
}
