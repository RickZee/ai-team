import type { RunWsStatus } from "../hooks/useWebSocket";
import type { MonitorState } from "../types";

const TERMINAL_STATUSES = new Set([
  "complete",
  "complete_approved",
  "error",
  "cancelled",
]);

export type CompareColumnVariant =
  | { kind: "idle" }
  | { kind: "starting" }
  | { kind: "live"; monitor: MonitorState }
  | { kind: "awaiting_human"; monitor: MonitorState | null; runId: string }
  | {
      kind: "terminal";
      monitor: MonitorState;
      status: RunWsStatus;
      runId: string;
    }
  | { kind: "error"; errorMessage: string; runId: string | null; monitor: MonitorState | null };

/** Single derived column state — every fragment reads from this (IA-3). */
export function deriveCompareColumnVariant(
  status: RunWsStatus,
  monitor: MonitorState | null,
  runId: string | null,
  errorMessage: string | null,
): CompareColumnVariant {
  if (status === "idle") {
    return { kind: "idle" };
  }

  if (status === "error") {
    return {
      kind: "error",
      errorMessage: errorMessage ?? "Run failed",
      runId,
      monitor,
    };
  }

  if (TERMINAL_STATUSES.has(status)) {
    if (monitor) {
      return {
        kind: "terminal",
        monitor,
        status,
        runId: runId ?? "",
      };
    }
    if (runId) {
      return {
        kind: "terminal",
        monitor: emptyTerminalMonitor(),
        status,
        runId,
      };
    }
    return { kind: "starting" };
  }

  if (status === "awaiting_human" && runId) {
    return { kind: "awaiting_human", monitor, runId };
  }

  if (status === "connecting" || (status === "running" && !monitor)) {
    return { kind: "starting" };
  }

  if (monitor) {
    return { kind: "live", monitor };
  }

  return { kind: "starting" };
}

function emptyTerminalMonitor(): MonitorState {
  return {
    phase: "complete",
    elapsed: "—",
    agents: {},
    metrics: {
      tasks_completed: 0,
      tasks_failed: 0,
      retries: 0,
      files_generated: 0,
      guardrails_passed: 0,
      guardrails_failed: 0,
      guardrails_warned: 0,
      tests_passed: 0,
      tests_failed: 0,
    },
    log: [],
    guardrail_events: [],
  };
}
