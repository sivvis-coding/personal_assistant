/**
 * Represent dashboard metrics for tickets, tasks, time and pending actions.
 */
export interface DashboardMetrics {
  tickets: {
    open: number;
    overdue: number;
    pending_development: number;
    assigned_to_me: number;
  };
  tasks: {
    pending: number;
    in_progress: number;
    in_sprint: number;
    blocked: number;
  };
  time: {
    today_hours: number;
    week_hours: number;
    month_hours: number;
  };
  actions: {
    pending_approval: number;
  };
}
