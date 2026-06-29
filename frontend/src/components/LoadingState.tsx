interface LoadingStateProps {
  message: string;
}

/**
 * Render a consistent loading message.
 *
 * Parameters:
 *   message: Text displayed to the user.
 *
 * Returns:
 *   JSX loading block.
 *
 * Edge cases:
 *   Empty message still renders accessible status container.
 */
export function LoadingState({ message }: LoadingStateProps) {
  return <div className="state" role="status">{message}</div>;
}
