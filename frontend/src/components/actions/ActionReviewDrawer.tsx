import {
  Box,
  Chip,
  Divider,
  Drawer,
  IconButton,
  Typography,
} from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import { ActionReview, ACTION_TYPE_LABELS } from './ActionReview';
import type { AssistantAction } from '../../types/assistant';

interface ActionReviewDrawerProps {
  action: AssistantAction;
  open: boolean;
  onClose: () => void;
  onDone?: (updated: AssistantAction) => void;
}

/**
 * Render a wide side drawer to review and approve/reject a single action.
 *
 * The drawer gives multi-field payloads (ClickUp user stories especially) the
 * horizontal room the inline cards never had, while keeping the surrounding
 * list/chat visible underneath as context.
 *
 * Edge cases:
 *   Full width on phones; a comfortable fixed width from `sm` up.
 */
export function ActionReviewDrawer({ action, open, onClose, onDone }: ActionReviewDrawerProps) {
  return (
    <Drawer
      anchor="right"
      open={open}
      onClose={onClose}
      PaperProps={{
        sx: {
          width: { xs: '100%', sm: 480, md: 600, lg: 680 },
          maxWidth: '100vw',
        },
      }}
    >
      <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
        {/* sticky header */}
        <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 1, p: 2, flexShrink: 0 }}>
          <Box sx={{ flex: 1, minWidth: 0 }}>
            <Chip
              label={ACTION_TYPE_LABELS[action.action_type] ?? action.action_type}
              size="small"
              sx={{ mb: 0.75 }}
            />
            <Typography variant="h6" sx={{ lineHeight: 1.3 }}>
              {action.title}
            </Typography>
          </Box>
          <IconButton onClick={onClose} size="small" aria-label="Cerrar">
            <CloseIcon />
          </IconButton>
        </Box>
        <Divider />

        {/* scrollable review body */}
        <Box sx={{ flex: 1, overflow: 'auto', p: 2 }}>
          <ActionReview action={action} onDone={onDone} />
        </Box>
      </Box>
    </Drawer>
  );
}
