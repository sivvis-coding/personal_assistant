import { apiRequest } from './client';
import type { MonthTimeResponse, PersonalListClientsResponse, WeekTimeResponse } from '../types/clickup';

/**
 * Purpose: Load current week time entries.
 * Parameters: None.
 * Return value: Promise with weekly time report.
 * Edge cases: Backend returns mock data when ClickUp credentials are absent.
 */
export function getWeekTime(): Promise<WeekTimeResponse> {
  return apiRequest<WeekTimeResponse>('/clickup/week-time');
}

/**
 * Purpose: Load a calendar month's time entries, one summary per day.
 * Parameters: year, month (1-12).
 * Return value: Promise with the monthly time report.
 * Edge cases: Backend returns mock data when ClickUp credentials are absent.
 */
export function getMonthTime(year: number, month: number): Promise<MonthTimeResponse> {
  return apiRequest<MonthTimeResponse>(`/clickup/month-time?year=${year}&month=${month}`);
}

/**
 * Purpose: Load the valid client options configured on the personal ClickUp list.
 * Parameters: None.
 * Return value: Promise with the client options response.
 * Edge cases: Empty list when no personal list is configured or the field allows free text.
 */
export function getPersonalListClients(): Promise<PersonalListClientsResponse> {
  return apiRequest<PersonalListClientsResponse>('/clickup/personal-list-clients');
}
