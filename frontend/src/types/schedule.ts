// Types matching the backend's uAgents Model definitions (Rewind Spec v2)

export type Priority = "P0" | "P1" | "P2" | "P3";

export interface Task {
  id: string;
  title: string;
  description?: string;
  priority: Priority;
  start_time: string; // ISO 8601
  end_time: string; // ISO 8601
  energy_cost: number; // 1-5
  estimated_duration: number; // minutes
  status: "scheduled" | "in_progress" | "completed" | "delegated" | "buffered";
  delegatable: boolean;
  task_type?: string; // email_reply | slack_message | uber_book | cancel_appointment | doc_update
}

export interface SwapOperation {
  action: "swap_in" | "swap_out" | "preempt" | "delegate";
  task_id: string;
  reason: string;
  new_time_slot: string | null; // ISO 8601 start time
}

export interface DisruptionEvent {
  severity: "minor" | "major" | "critical";
  affected_task_ids: string[];
  freed_minutes: number;
  recommended_action: string;
  context_summary: string;
}

export interface EnergyLevel {
  level: number; // 1-5
  confidence: number; // 0.0-1.0
  source: "inferred" | "user_reported" | "time_based";
}

export interface DelegationTask {
  task_id: string;
  task_type: string;
  context: Record<string, unknown>;
  approval_required: boolean;
  max_cost_fet: number;
}

export interface UpdatedSchedule {
  tasks: Task[];
  swaps: SwapOperation[];
  energy: EnergyLevel;
  timestamp: string;
}

export interface ReminderNotification {
  reminder_type: "upcoming_task" | "check_in" | "completion_check" | "transition";
  task_id: string;
  title: string;
  message: string;
  urgency: "low" | "medium" | "high";
  suggested_actions: string[];
  timestamp: string;
}

// WebSocket message types
export type WSMessageType =
  | "updated_schedule"
  | "disruption_event"
  | "swap_operation"
  | "energy_update"
  | "delegation_update"
  | "ghost_worker_status"
  | "ghostworker_draft"
  | "agent_activity"
  | "reminder";

export interface WSMessage {
  type: WSMessageType;
  payload: unknown;
  timestamp: string;
}
