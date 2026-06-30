import { create } from 'zustand';
import type { DashboardMetrics } from '../types/metrics';

interface MetricsState {
  metrics: DashboardMetrics | null;
  isLoading: boolean;
  error: string | null;
}

interface MetricsActions {
  setMetrics: (metrics: DashboardMetrics) => void;
  setLoading: (value: boolean) => void;
  setError: (error: string | null) => void;
}

const defaultMetrics: DashboardMetrics = {
  tickets: { open: 0, overdue: 0, pending_development: 0, assigned_to_me: 0 },
  tasks: { pending: 0, in_progress: 0, in_sprint: 0, blocked: 0 },
  time: { today_hours: 0, week_hours: 0, month_hours: 0 },
  actions: { pending_approval: 0 },
};

/**
 * Global dashboard metrics state managed by Zustand.
 *
 * Parameters:
 *   None.
 *
 * Returns:
 *   Hook returning metrics state and actions.
 */
export const useMetricsStore = create<MetricsState & MetricsActions>((set) => ({
  metrics: defaultMetrics,
  isLoading: false,
  error: null,

  setMetrics: (metrics) => set({ metrics }),
  setLoading: (value) => set({ isLoading: value }),
  setError: (error) => set({ error }),
}));
