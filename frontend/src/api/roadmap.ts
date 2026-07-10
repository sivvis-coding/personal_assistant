import { apiRequest } from './client';
import type {
  RoadmapGroupInput,
  RoadmapResponse,
  RoadmapSummariesResponse,
  RoadmapSummaryListInput,
} from '../types/roadmap';

/**
 * Purpose: Load the saved roadmap (split by list), rehydrated with live tasks.
 * Parameters: none.
 * Return value: Promise with the roadmap (persisted=false if never generated).
 * Edge cases: New tasks arrive under each list's "Sin clasificar" without an LLM call.
 */
export function getRoadmap(): Promise<RoadmapResponse> {
  return apiRequest<RoadmapResponse>('/roadmap');
}

/**
 * Purpose: Regroup each configured list's tasks by theme via the LLM and persist.
 * Parameters: none.
 * Return value: Promise with the freshly generated roadmap.
 * Edge cases: Overwrites manual edits — call behind an explicit confirm.
 */
export function generateRoadmap(): Promise<RoadmapResponse> {
  return apiRequest<RoadmapResponse>('/roadmap/generate', { method: 'POST' });
}

/**
 * Purpose: Persist an edited roadmap structure (drag & drop / group edits).
 * Parameters: groups is the flat group structure (each tagged with list_id).
 * Return value: Promise with the rehydrated, saved roadmap.
 * Edge cases: The "Sin clasificar" group is recomputed server-side per list.
 */
export function saveRoadmap(groups: RoadmapGroupInput[]): Promise<RoadmapResponse> {
  return apiRequest<RoadmapResponse>('/roadmap', {
    method: 'PUT',
    body: JSON.stringify({ groups }),
  });
}

/**
 * Purpose: Generate an AI summary for each list from its visible (filtered) tasks.
 * Parameters: lists carry the currently-visible tasks per list.
 * Return value: Promise with one summary per non-empty list.
 * Edge cases: Not persisted; reflects the active status filter.
 */
export function summarizeRoadmap(lists: RoadmapSummaryListInput[]): Promise<RoadmapSummariesResponse> {
  return apiRequest<RoadmapSummariesResponse>('/roadmap/summaries', {
    method: 'POST',
    body: JSON.stringify({ lists }),
  });
}
