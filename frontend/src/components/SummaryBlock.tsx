import type { TicketSummary } from '../types/ai';

interface SummaryBlockProps {
  summary: TicketSummary | null;
}

/**
 * Render generated ticket summary.
 *
 * Parameters:
 *   summary: Summary data or null.
 *
 * Returns:
 *   JSX summary block.
 *
 * Edge cases:
 *   Null summary renders empty guidance.
 */
export function SummaryBlock({ summary }: SummaryBlockProps) {
  if (!summary) {
    return <section className="panel"><h3>Resumen</h3><p>No summary generated yet.</p></section>;
  }

  return (
    <section className="panel">
      <h3>Resumen</h3>
      <h4>{summary.title}</h4>
      <p><strong>Problem:</strong> {summary.problem}</p>
      <p><strong>Impact:</strong> {summary.impact}</p>
      <strong>Next steps</strong>
      <ul>{summary.suggested_next_steps.map((item) => <li key={item}>{item}</li>)}</ul>
      <strong>Risks</strong>
      <ul>{summary.risks.map((item) => <li key={item}>{item}</li>)}</ul>
    </section>
  );
}
