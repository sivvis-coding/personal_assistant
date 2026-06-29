import type { ReplyDraft } from '../types/ai';

interface DraftEditorProps {
  draft: ReplyDraft | null;
  onChange: (draft: ReplyDraft) => void;
}

/**
 * Render editable reply draft.
 *
 * Parameters:
 *   draft: Reply draft or null.
 *   onChange: Callback with edited draft.
 *
 * Returns:
 *   JSX draft editor.
 *
 * Edge cases:
 *   Null draft renders an empty state instead of uncontrolled inputs.
 */
export function DraftEditor({ draft, onChange }: DraftEditorProps) {
  if (!draft) {
    return <section className="panel"><h3>Borrador</h3><p>No reply draft generated yet.</p></section>;
  }

  return (
    <section className="panel">
      <h3>Borrador editable</h3>
      <label>
        Subject
        <input value={draft.subject} onChange={(event) => onChange({ ...draft, subject: event.target.value })} />
      </label>
      <label>
        Body
        <textarea value={draft.body} rows={8} onChange={(event) => onChange({ ...draft, body: event.target.value })} />
      </label>
      <p><strong>Tone:</strong> {draft.tone}</p>
      <p><strong>Requires review:</strong> {draft.requires_human_review ? 'Yes' : 'No'}</p>
    </section>
  );
}
