export interface LinkedTaskItem {
  link_id: string;
  ticket_id: string;
  ticket_subject: string;
  ticket_status: string;
  clickup_task_id: string;
  clickup_task_url: string | null;
  clickup_status: string;
  last_known_clickup_status: string | null;
  created_at: string;
}
