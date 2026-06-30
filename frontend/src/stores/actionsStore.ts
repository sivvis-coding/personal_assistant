import { create } from 'zustand';
import type { AssistantAction } from '../types/assistant';

interface ActionsState {
  pendingActions: AssistantAction[];
  isLoading: boolean;
  error: string | null;
}

interface ActionsActions {
  setPendingActions: (actions: AssistantAction[]) => void;
  removeAction: (actionId: string) => void;
  updateAction: (action: AssistantAction) => void;
  setLoading: (value: boolean) => void;
  setError: (error: string | null) => void;
}

/**
 * Global pending actions state managed by Zustand.
 *
 * Parameters:
 *   None.
 *
 * Returns:
 *   Hook returning actions state and actions.
 */
export const useActionsStore = create<ActionsState & ActionsActions>((set) => ({
  pendingActions: [],
  isLoading: false,
  error: null,

  setPendingActions: (pendingActions) => set({ pendingActions }),
  removeAction: (actionId) =>
    set((state) => ({
      pendingActions: state.pendingActions.filter((action) => action.id !== actionId),
    })),
  updateAction: (action) =>
    set((state) => ({
      pendingActions: state.pendingActions.map((pending) => (pending.id === action.id ? action : pending)),
    })),
  setLoading: (value) => set({ isLoading: value }),
  setError: (error) => set({ error }),
}));
