import { apiRequest } from './client';
import type { LinkedTaskItem } from '../types/links';

export async function getLinkedTasks(): Promise<LinkedTaskItem[]> {
  return apiRequest<LinkedTaskItem[]>('/integration-links');
}
