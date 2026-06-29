interface ErrorStateProps {
  message: string;
}

/**
 * Render a consistent error message.
 *
 * Parameters:
 *   message: Error text displayed to the user.
 *
 * Returns:
 *   JSX error block.
 *
 * Edge cases:
 *   Empty message renders a generic fallback.
 */
export function ErrorState({ message }: ErrorStateProps) {
  return <div className="state error" role="alert">{message || 'Unknown error'}</div>;
}
