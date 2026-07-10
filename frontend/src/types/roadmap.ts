export interface RoadmapTask {
  id: string;
  name: string;
  status: string;
  url?: string | null;
  description?: string | null;
  list_id?: string | null;
  list_name?: string | null;
}

export interface RoadmapGroup {
  list_id: string;
  title: string;
  summary: string;
  count: number;
  tasks: RoadmapTask[];
}

export interface RoadmapListSection {
  list_id: string;
  list_name: string;
  summary: string;
  total_tasks: number;
  groups: RoadmapGroup[];
}

export interface RoadmapResponse {
  lists: RoadmapListSection[];
  total_tasks: number;
  model: string;
  generated_at: string;
  persisted: boolean;
}

export interface RoadmapGroupInput {
  list_id: string;
  title: string;
  summary: string;
  task_ids: string[];
}

export interface RoadmapSummaryTaskInput {
  name: string;
  status: string;
  description?: string | null;
}

export interface RoadmapSummaryListInput {
  list_id: string;
  list_name: string;
  tasks: RoadmapSummaryTaskInput[];
}

export interface RoadmapListSummary {
  list_id: string;
  summary: string;
}

export interface RoadmapSummariesResponse {
  summaries: RoadmapListSummary[];
}
