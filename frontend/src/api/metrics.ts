import { apiRequest } from './client';
import type { DashboardMetrics } from '../types/metrics';

/**
 * Fetch aggregated dashboard metrics.
 *
 * Parameters:
 *   None.
 *
 * Returns:
 *   Dashboard metrics DTO.
 *
 * Edge cases:
 *   Backend returns zeros when external integrations are unavailable.
 */
export function getDashboardMetrics(): Promise<DashboardMetrics> {
  return apiRequest<DashboardMetrics>('/metrics');
}
