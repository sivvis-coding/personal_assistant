import type { UserStory } from '../types/ai';

interface UserStoryReviewProps {
  userStory: UserStory | null;
  onChange: (userStory: UserStory) => void;
  onApprove: () => void;
}

/**
 * Render editable user story review before ClickUp creation.
 *
 * Parameters:
 *   userStory: Generated user story or null.
 *   onChange: Callback receiving edited user story.
 *   onApprove: Callback executed after human approval.
 *
 * Returns:
 *   JSX review panel.
 *
 * Edge cases:
 *   Null user story renders explicit pending review state.
 */
export function UserStoryReview({ userStory, onChange, onApprove }: UserStoryReviewProps) {
  if (!userStory) {
    return (
      <section className="panel">
        <h3>Revisión ClickUp</h3>
        <p>No hay historia de usuario preparada todavía.</p>
      </section>
    );
  }

  return (
    <section className="panel approval-panel">
      <h3>Revisión ClickUp</h3>
      <p className="warning">Nada se crea en ClickUp hasta pulsar aprobación.</p>
      <label>
        Title
        <input value={userStory.title} onChange={(event) => onChange({ ...userStory, title: event.target.value })} />
      </label>
      <label>
        Description
        <textarea value={userStory.description} rows={5} onChange={(event) => onChange({ ...userStory, description: event.target.value })} />
      </label>
      <label>
        User Story Statement
        <textarea value={userStory.user_story_statement} rows={3} onChange={(event) => onChange({ ...userStory, user_story_statement: event.target.value })} />
      </label>
      <label>
        Acceptance Criteria in Gherkin
        <textarea value={userStory.acceptance_criteria_in_gerkin} rows={8} onChange={(event) => onChange({ ...userStory, acceptance_criteria_in_gerkin: event.target.value })} />
      </label>
      <label>
        Technical Notes / Constraints
        <textarea value={userStory.constraints} rows={4} onChange={(event) => onChange({ ...userStory, constraints: event.target.value })} />
      </label>
      <label>
        Out of Scope
        <textarea value={userStory.out_of_scope} rows={3} onChange={(event) => onChange({ ...userStory, out_of_scope: event.target.value })} />
      </label>
      <label>
        Requested By
        <input value={userStory.requested_by} onChange={(event) => onChange({ ...userStory, requested_by: event.target.value })} />
      </label>
      <label>
        Functional Description
        <textarea value={userStory.functional_description} rows={5} onChange={(event) => onChange({ ...userStory, functional_description: event.target.value })} />
      </label>
      <button className="danger-action" type="button" onClick={onApprove}>Aprobar y crear en ClickUp</button>
    </section>
  );
}
