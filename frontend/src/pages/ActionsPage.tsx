import { useEffect, useState } from 'react';
import { Box, CircularProgress, Typography } from '@mui/material';
import { useActionsStore } from '../stores/actionsStore';
import { useChatStore } from '../stores/chatStore';
import { listPendingAssistantActions } from '../api/assistant';
import { ActionCard } from '../components/actions/ActionCard';
import type { AssistantAction } from '../types/assistant';

export function ActionsPage() {
  const { pendingActions, isLoading, error, setPendingActions, setLoading, setError, removeAction } = useActionsStore();
  const { updatePendingAction: updateChatPendingAction } = useChatStore();
  const [refreshing, setRefreshing] = useState(false);

  useEffect(() => {
    async function loadActions() {
      setLoading(true);
      try {
        const actions = await listPendingAssistantActions();
        setPendingActions(actions);
      } catch (caught) {
        setError((caught as Error).message);
      } finally {
        setLoading(false);
      }
    }
    void loadActions();
  }, [setPendingActions, setLoading, setError]);

  async function handleDone(updated: AssistantAction) {
    removeAction(updated.id);
    updateChatPendingAction(updated);
    setRefreshing(true);
    try {
      setPendingActions(await listPendingAssistantActions());
    } finally {
      setRefreshing(false);
    }
  }

  if (isLoading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', mt: 8 }}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 3 }}>
        <Typography variant="h4">Acciones pendientes</Typography>
        {refreshing ? <CircularProgress size={20} /> : null}
      </Box>

      {error ? <Typography color="error" sx={{ mb: 2 }}>{error}</Typography> : null}

      {pendingActions.length === 0 ? (
        <Typography color="text.secondary">No hay acciones pendientes.</Typography>
      ) : (
        pendingActions.map((action) => (
          <ActionCard key={action.id} action={action} onDone={(updated) => void handleDone(updated)} />
        ))
      )}
    </Box>
  );
}
