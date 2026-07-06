import type { CostEstimate, LogEntry, MonitorState, RunInfo } from "../../types";

export const baseMetrics = {
  tasks_completed: 2,
  tasks_failed: 0,
  retries: 0,
  files_generated: 1,
  guardrails_passed: 1,
  guardrails_failed: 0,
  guardrails_warned: 0,
  tests_passed: 3,
  tests_failed: 1,
};

export function makeMonitor(overrides: Partial<MonitorState> = {}): MonitorState {
  return {
    phase: "development",
    elapsed: "2m 15s",
    cost_usd: 0.0425,
    agents: {},
    metrics: { ...baseMetrics },
    log: [],
    guardrail_events: [],
    ...overrides,
  };
}

export function makeLogLines(count: number): LogEntry[] {
  return Array.from({ length: count }, (_, i) => ({
    timestamp: `2026-06-01T10:${String(i).padStart(2, "0")}:00Z`,
    agent: "manager",
    message: `Log line ${i + 1}`,
    level: "info" as const,
  }));
}

export const sampleEstimate: CostEstimate = {
  complexity: "medium",
  rows: [
    {
      role: "manager",
      model_id: "test-model",
      input_tokens: 1000,
      output_tokens: 500,
      cost_usd: 0.02,
    },
  ],
  total_usd: 0.05,
  within_budget: true,
};

export const runningRun: RunInfo = {
  run_id: "live-run-1",
  backend: "langgraph",
  profile: "full",
  description: "Build a REST API",
  status: "running",
  started_at: "2026-06-01T10:00:00Z",
  finished_at: null,
  error: null,
};

export const completeRun: RunInfo = {
  ...runningRun,
  run_id: "done-run-1",
  status: "complete",
  finished_at: "2026-06-01T10:05:00Z",
};
