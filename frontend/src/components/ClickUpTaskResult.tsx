import type { CreateClickUpTaskWorkflowResponse } from '../types/clickup';

interface ClickUpTaskResultProps {
  result: CreateClickUpTaskWorkflowResponse | null;
}

/**
 * Render ClickUp task creation result.
 *
 * Parameters:
 *   result: Workflow result or null.
 *
 * Returns:
 *   JSX result block.
 *
 * Edge cases:
 *   Null result renders a simple pending message.
 */
export function ClickUpTaskResult({ result }: ClickUpTaskResultProps) {
  if (!result) {
    return <section className="panel"><h3>ClickUp</h3><p>No task created yet.</p></section>;
  }

  return (
    <section className="panel">
      <h3>ClickUp task</h3>
      <p><strong>ID:</strong> {result.clickup_task.id}</p>
      <p><strong>Source:</strong> {result.clickup_task.source}</p>
      {result.clickup_task.url ? <a href={result.clickup_task.url}>Open task</a> : null}
      <h4>User story</h4>
      <p><strong>{result.user_story.title}</strong></p>
      <p>{result.user_story.user_story_statement}</p>
    </section>
  );
}
