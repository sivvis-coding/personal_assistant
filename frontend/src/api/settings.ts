import { apiRequest } from './client';
import type { AppSettings } from '../types/settings';

/**
 * Load editable application settings.
 *
 * Parameters:
 *   None.
 *
 * Returns:
 *   Current settings.
 */
export function getSettings(): Promise<AppSettings> {
  return apiRequest<AppSettings>('/settings');
}

/**
 * Save editable application settings.
 *
 * Parameters:
 *   settings: Settings to persist.
 *
 * Returns:
 *   Stored settings.
 *
 * Edge cases:
 *   Settings take effect after backend restart.
 */
export function updateSettings(settings: AppSettings): Promise<AppSettings> {
  return apiRequest<AppSettings>('/settings', {
    method: 'PUT',
    body: JSON.stringify(settings),
  });
}
