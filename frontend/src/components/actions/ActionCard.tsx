import { useState } from 'react';
import {
  Box,
  Button,
  Card,
  CardActionArea,
  Chip,
  Typography,
} from '@mui/material';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import { ActionReviewDrawer } from './ActionReviewDrawer';
import { ACTION_TYPE_LABELS, STATUS_COLORS, actionIsActionable } from './ActionReview';
import type { AssistantAction } from '../../types/assistant';

// Re-exported for callers that still import it from here.
export { ACTION_TYPE_LABELS } from './ActionReview';

const STATUS_LABELS: Record<string, string> = {
  approved: 'Aprobada',
  completed: 'Completada',
  rejected: 'Rechazada',
  failed: 'Falló',
};

interface ActionCardProps {
  action: AssistantAction;
  onDone?: (updated: AssistantAction) => void;
}

/**
 * Render a compact summary row for one action. Clicking "Revisar" opens a wide
 * side drawer where the payload is reviewed, edited and approved/rejected.
 *
 * Keeping the row compact lets many actions fit on screen at once; the heavy
 * editing surface lives in the drawer where it has room.
 */
export function ActionCard({ action: initialAction, onDone }: ActionCardProps) {
  const [action, setAction] = useState(initialAction);
  const [open, setOpen] = useState(false);

  const canAct = actionIsActionable(action);
  const isFailed = action.status === 'failed';
  const showStatus = action.status !== 'proposed';

  function handleReviewDone(updated: AssistantAction) {
    setAction(updated);
    onDone?.(updated);
    // Once settled (approved/completed/rejected) the drawer has nothing left to
    // do — close it. Failed stays open so the user can fix and retry inline.
    if (updated.status !== 'failed') setOpen(false);
  }

  return (
    <>
      <Card variant="outlined" sx={{ borderColor: isFailed ? 'error.light' : 'divider' }}>
        <CardActionArea onClick={() => setOpen(true)} sx={{ p: 1.5 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
            <Box sx={{ flex: 1, minWidth: 0 }}>
              <Typography
                variant="subtitle2"
                sx={{ fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
              >
                {action.title}
              </Typography>
              {action.description ? (
                <Typography
                  variant="body2"
                  color="text.secondary"
                  sx={{
                    mt: 0.25,
                    display: '-webkit-box',
                    WebkitLineClamp: 2,
                    WebkitBoxOrient: 'vertical',
                    overflow: 'hidden',
                  }}
                >
                  {action.description}
                </Typography>
              ) : null}
              <Box sx={{ display: 'flex', gap: 0.5, mt: 0.75, flexWrap: 'wrap' }}>
                <Chip label={ACTION_TYPE_LABELS[action.action_type] ?? action.action_type} size="small" />
                {showStatus ? (
                  <Chip
                    label={STATUS_LABELS[action.status] ?? action.status}
                    size="small"
                    color={STATUS_COLORS[action.status] ?? 'default'}
                  />
                ) : null}
              </Box>
            </Box>

            <Box sx={{ flexShrink: 0, display: 'flex', alignItems: 'center' }}>
              {canAct ? (
                <Button
                  variant={isFailed ? 'contained' : 'outlined'}
                  color={isFailed ? 'error' : 'primary'}
                  size="small"
                  endIcon={<ChevronRightIcon />}
                  onClick={(e) => { e.stopPropagation(); setOpen(true); }}
                >
                  {isFailed ? 'Reintentar' : 'Revisar'}
                </Button>
              ) : (
                <Button variant="text" size="small" onClick={(e) => { e.stopPropagation(); setOpen(true); }}>
                  Ver
                </Button>
              )}
            </Box>
          </Box>
        </CardActionArea>
      </Card>

      <ActionReviewDrawer
        action={action}
        open={open}
        onClose={() => setOpen(false)}
        onDone={handleReviewDone}
      />
    </>
  );
}
