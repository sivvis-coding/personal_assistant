import { apiRequest } from './client';
import type { WeekTimeResponse } from '../types/clickup';

/**
 * Purpose: Load current week time entries.
 * Parameters: None.
 * Return value: Promise with weekly time report.
 * Edge cases: Backend returns mock data when ClickUp credentials are absent.
 */
export function getWeekTime(): Promise<WeekTimeResponse> {
  return apiRequest<WeekTimeResponse>('/clickup/week-time');
}
