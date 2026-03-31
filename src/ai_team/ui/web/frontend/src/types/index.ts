export interface AgentState {
  role: string;
  status: "idle" | "working" | "done" | "error";
  current_task: string;
  tasks_completed: number;
  model: string;
}

export interface Metrics {
  tasks_completed: number;
  tasks_failed: number;
  retries: number;
  files_generated: number;
  guardrails_passed: number;
  guardrails_failed: number;
  guardrails_warned: number;
  tests_passed: number;
  tests_failed: number;
}

export interface LogEntry {
  timestamp: string;
  agent: string;
  message: string;
  level: "info" | "warn" | "error" | "success";
}

export interface GuardrailEvent {
  timestamp: string;
  category: string;
  name: string;
  status: "pass" | "fail" | "warn";
  message: string;
}

export interface MonitorState {
  phase: string;
  elapsed: string;
  agents: Record<string, AgentState>;
  metrics: Metrics;
  log: LogEntry[];
  guardrail_events: GuardrailEvent[];
  run_status?: string;
}

export interface RunInfo {
  run_id: string;
  backend: string;
  profile: string;
  description: string;
  status: string;
  started_at: string;
  finished_at: string | null;
  error: string | null;
}

export interface CostRow {
  role: string;
  model_id: string;
  input_tokens: number;
  output_tokens: number;
  cost_usd: number;
}

export interface CostEstimate {
  complexity: string;
  rows: CostRow[];
  total_usd: number;
  within_budget: boolean;
}

export interface BackendInfo {
  name: string;
  label: string;
  streaming: boolean;
}

export interface ProfileInfo {
  agents: string[];
  phases: string[];
  model_overrides: Record<string, string>;
}
