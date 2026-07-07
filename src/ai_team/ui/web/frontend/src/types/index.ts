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

export interface MonitorCostFields {
  token_estimate?: number;
  cost_usd?: number | null;
  session_id?: string;
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

export interface MonitorState extends MonitorCostFields {
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
  estimate_usd?: number | null;
  complexity?: string | null;
  is_sample?: boolean;
  comparison_id?: string | null;
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
  required_key?: string;
  configured?: boolean;
}

export interface ProfileInfo {
  agents: string[];
  phases: string[];
  model_overrides?: Record<string, string>;
}

export type ArtifactRoot = "workspace" | "bundle";

export interface RegistryRun {
  run_id: string;
  output_dir?: string | null;
  started_at?: string | null;
  completed_at?: string | null;
  backend?: string | null;
  team_profile?: string | null;
  status?: string | null;
  description?: string | null;
}

export interface ArtifactTreeNode {
  name: string;
  path: string;
  type: "file" | "dir";
  size?: number | null;
  children: ArtifactTreeNode[];
}

export interface ArtifactFileContent {
  path: string;
  root: ArtifactRoot;
  content: string | null;
  language?: string | null;
  size_bytes: number;
  is_binary: boolean;
  truncated: boolean;
}

export interface TestFailureItem {
  test_name: string;
  error: string;
  traceback: string;
}

export interface FileCoverageItem {
  path: string;
  line_coverage: number;
  branch_coverage: number;
}

export interface TestsPanelData {
  total: number;
  passed: number;
  failed: number;
  errors: number;
  skipped: number;
  coverage_line: number;
  coverage_branch: number;
  duration_seconds: number;
  failures: TestFailureItem[];
  per_file_coverage: FileCoverageItem[];
  raw_pytest?: string | null;
  source?: string | null;
}

export interface ArchitecturePanelData {
  system_overview: string;
  ascii_diagram: string;
  components: { name: string; responsibilities: string }[];
  technology_stack: { name: string; category: string; justification: string }[];
  interface_contracts: Record<string, unknown>[];
  data_model_outline: string;
  deployment_topology: string;
  adrs: Record<string, unknown>[];
  markdown_fallback?: string | null;
  source?: string | null;
}

export interface OpenFileTab {
  path: string;
  root: ArtifactRoot;
  label: string;
}
