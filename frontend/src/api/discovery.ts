import { apiRequest } from './client';
import type {
  ClickUpDiscoveryResponse,
  ClickUpListFieldsResponse,
  FreshserviceDiscoveryResponse,
  FreshserviceWorkspacesResponse,
} from '../types/discovery';

/**
 * Discover ClickUp teams and lists using the provided API key.
 *
 * Parameters:
 *   apiKey: ClickUp API key.
 *
 * Returns:
 *   ClickUp discovery response.
 */
export function discoverClickUp(apiKey: string): Promise<ClickUpDiscoveryResponse> {
  return apiRequest<ClickUpDiscoveryResponse>('/settings/discover/clickup', {
    method: 'POST',
    body: JSON.stringify({ api_key: apiKey }),
  });
}

/**
 * Discover custom fields for a specific ClickUp list.
 *
 * Parameters:
 *   apiKey: ClickUp API key.
 *   listId: ClickUp list ID.
 *
 * Returns:
 *   Fields response with discovered custom fields.
 */
export function discoverClickUpListFields(apiKey: string, listId: string): Promise<ClickUpListFieldsResponse> {
  return apiRequest<ClickUpListFieldsResponse>('/settings/discover/clickup/fields', {
    method: 'POST',
    body: JSON.stringify({ api_key: apiKey, list_id: listId }),
  });
}

/**
 * Discover Freshservice agents using the provided credentials.
 *
 * Parameters:
 *   baseUrl: Freshservice workspace URL.
 *   apiKey: Freshservice API key.
 *
 * Returns:
 *   Freshservice discovery response.
 */
export function discoverFreshservice(baseUrl: string, apiKey: string): Promise<FreshserviceDiscoveryResponse> {
  return apiRequest<FreshserviceDiscoveryResponse>('/settings/discover/freshservice', {
    method: 'POST',
    body: JSON.stringify({ base_url: baseUrl, api_key: apiKey }),
  });
}

/**
 * Discover Freshservice workspaces using the provided credentials.
 *
 * Parameters:
 *   baseUrl: Freshservice workspace URL.
 *   apiKey: Freshservice API key.
 *
 * Returns:
 *   Freshservice workspaces discovery response.
 */
export function discoverFreshserviceWorkspaces(
  baseUrl: string,
  apiKey: string,
): Promise<FreshserviceWorkspacesResponse> {
  return apiRequest<FreshserviceWorkspacesResponse>('/settings/discover/freshservice/workspaces', {
    method: 'POST',
    body: JSON.stringify({ base_url: baseUrl, api_key: apiKey }),
  });
}
