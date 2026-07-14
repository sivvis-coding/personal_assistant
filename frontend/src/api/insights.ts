import { API_BASE_URL, apiRequest } from './client';
import type {
  ArchivedTicketsResponse,
  HarvestStatus,
  KnowledgeResponse,
  WorkspacesResponse,
} from '../types/insights';

/**
 * Purpose: List Freshservice workspaces available (from the API) and configured.
 * Return value: Promise with available + configured workspaces.
 */
export function getWorkspaces(): Promise<WorkspacesResponse> {
  return apiRequest<WorkspacesResponse>('/insights/workspaces');
}

/**
 * Purpose: Discover workspaces from Freshservice and save them into the config.
 * Return value: Promise with the resulting available + configured workspaces.
 */
export function importWorkspaces(): Promise<WorkspacesResponse> {
  return apiRequest<WorkspacesResponse>('/insights/workspaces/import', { method: 'POST' });
}

/**
 * Purpose: Load per-workspace harvest progress and archive counts.
 * Return value: Promise with the aggregate harvest status.
 */
export function getInsightsStatus(): Promise<HarvestStatus> {
  return apiRequest<HarvestStatus>('/insights/status');
}

/**
 * Purpose: Kick off a resumable historic backfill (runs in the background).
 * Parameters: optional workspace_id / since_months overrides.
 * Return value: Promise with the current status (progress arrives via refresh).
 */
export function triggerBackfill(params: { workspace_id?: string; since_months?: number } = {}): Promise<HarvestStatus> {
  return apiRequest<HarvestStatus>('/insights/backfill', {
    method: 'POST',
    body: JSON.stringify(params),
  });
}

/**
 * Purpose: Kick off an incremental sync (runs in the background).
 * Return value: Promise with the current status.
 */
export function triggerSync(): Promise<HarvestStatus> {
  return apiRequest<HarvestStatus>('/insights/sync', { method: 'POST' });
}

/**
 * Purpose: List archived tickets with their per-ticket signature ficha.
 * Parameters: skip/limit for pagination.
 * Return value: Promise with a page of archived tickets.
 */
export function getArchivedTickets(skip = 0, limit = 50): Promise<ArchivedTicketsResponse> {
  return apiRequest<ArchivedTicketsResponse>(`/insights/tickets?skip=${skip}&limit=${limit}`);
}

/**
 * Purpose: Kick off knowledge-base generation (runs in the background).
 * Parameters: statuses to include (default resolved + closed).
 * Return value: Promise with the currently persisted knowledge base.
 */
export function generateKnowledge(statuses: string[] = ['resolved', 'closed']): Promise<KnowledgeResponse> {
  return apiRequest<KnowledgeResponse>('/insights/knowledge/generate', {
    method: 'POST',
    body: JSON.stringify({ statuses }),
  });
}

/**
 * Purpose: Load the persisted knowledge base (themes + recurring ranking).
 * Return value: Promise with the knowledge base (persisted=false if never generated).
 */
export function getKnowledge(): Promise<KnowledgeResponse> {
  return apiRequest<KnowledgeResponse>('/insights/knowledge');
}

/**
 * Purpose: Download the plain-text JSONL export for RAG ingestion.
 * Parameters: include ("themes" by default — symptom/resolution knowledge only;
 *   pass e.g. "themes,bottlenecks,automation,metrics,tickets" for more), optional workspace_id filter.
 * Return value: Promise that resolves once the browser download has been triggered.
 * Edge cases: Uses fetch + blob directly (not apiRequest) since the response is not JSON.
 */
export async function downloadInsightsExport(params: { include?: string; workspace_id?: string } = {}): Promise<void> {
  const localKey = window.localStorage.getItem('LOCAL_APP_API_KEY') ?? '';
  const query = new URLSearchParams({ include: params.include ?? 'themes' });
  if (params.workspace_id) query.set('workspace_id', params.workspace_id);

  const response = await fetch(`${API_BASE_URL}/insights/export?${query.toString()}`, {
    headers: localKey ? { 'X-Local-App-Key': localKey } : {},
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(String(payload.detail ?? response.statusText));
  }

  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = 'insights_export.jsonl';
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}
