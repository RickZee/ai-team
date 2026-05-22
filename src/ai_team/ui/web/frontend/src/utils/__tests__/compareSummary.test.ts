import { describe, expect, it } from "vitest";
import { bestColumnKey, parseElapsedSeconds } from "../compareSummary";
import type { MonitorState } from "../../types";

const baseMetrics = {
  tasks_completed: 0,
  tasks_failed: 0,
  retries: 0,
  files_generated: 0,
  guardrails_passed: 0,
  guardrails_failed: 0,
  guardrails_warned: 0,
  tests_passed: 0,
  tests_failed: 0,
};

function monitor(partial: Partial<MonitorState>): MonitorState {
  return {
    phase: "complete",
    elapsed: "1m 0s",
    agents: {},
    metrics: baseMetrics,
    log: [],
    guardrail_events: [],
    ...partial,
  };
}

describe("compareSummary", () => {
  it("parseElapsedSeconds parses minutes and seconds", () => {
    expect(parseElapsedSeconds("2m 30s")).toBe(150);
    expect(parseElapsedSeconds("45s")).toBe(45);
  });

  it("bestColumnKey picks max tasks completed", () => {
    const rows = [
      { key: "a", m: monitor({ metrics: { ...baseMetrics, tasks_completed: 1 } }) },
      { key: "b", m: monitor({ metrics: { ...baseMetrics, tasks_completed: 5 } }) },
    ];
    expect(
      bestColumnKey(rows, (m) => m.metrics.tasks_completed, "max"),
    ).toBe("b");
  });
});
