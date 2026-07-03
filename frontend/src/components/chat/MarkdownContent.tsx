import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Box, Divider, Typography } from '@mui/material';

/**
 * Render assistant message text as formatted markdown using MUI components.
 *
 * Parameters:
 *   content: The text to render.
 *   invert: When true (user bubble), renders as plain text without markdown processing.
 *
 * Returns:
 *   Rendered content node.
 *
 * Edge cases:
 *   User messages are always plain text — markdown parsing is skipped.
 */
export function MarkdownContent({ content, invert }: { content: string; invert?: boolean }) {
  if (invert) {
    return <Typography variant="body2">{content}</Typography>;
  }

  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        p: ({ children }) => (
          <Typography variant="body2" sx={{ mb: 0.5, lineHeight: 1.6 }}>
            {children}
          </Typography>
        ),
        h1: ({ children }) => (
          <Typography variant="subtitle2" fontWeight={700} sx={{ mt: 1, mb: 0.5 }}>
            {children}
          </Typography>
        ),
        h2: ({ children }) => (
          <Typography variant="subtitle2" fontWeight={700} sx={{ mt: 1, mb: 0.5 }}>
            {children}
          </Typography>
        ),
        h3: ({ children }) => (
          <Typography variant="subtitle2" fontWeight={700} sx={{ mt: 1, mb: 0.5 }}>
            {children}
          </Typography>
        ),
        ul: ({ children }) => (
          <Box component="ul" sx={{ pl: 2.5, my: 0.5 }}>
            {children}
          </Box>
        ),
        ol: ({ children }) => (
          <Box component="ol" sx={{ pl: 2.5, my: 0.5 }}>
            {children}
          </Box>
        ),
        li: ({ children }) => (
          <Typography component="li" variant="body2" sx={{ mb: 0.25 }}>
            {children}
          </Typography>
        ),
        strong: ({ children }) => (
          <Box component="strong" sx={{ fontWeight: 700 }}>
            {children}
          </Box>
        ),
        code: ({ children }) => (
          <Box
            component="code"
            sx={{
              fontFamily: 'monospace',
              fontSize: '0.85em',
              bgcolor: 'rgba(0,0,0,0.08)',
              borderRadius: 0.5,
              px: 0.5,
            }}
          >
            {children}
          </Box>
        ),
        blockquote: ({ children }) => (
          <Box
            component="blockquote"
            sx={{
              borderLeft: '3px solid',
              borderColor: 'divider',
              pl: 1.5,
              my: 1,
              color: 'text.secondary',
            }}
          >
            {children}
          </Box>
        ),
        hr: () => <Divider sx={{ my: 1 }} />,
      }}
    >
      {content}
    </ReactMarkdown>
  );
}
