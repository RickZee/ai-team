import { describe, expect, it } from "vitest";
import { bestColumnKey, buildCompareVerdict, directionHint, parseElapsedSeconds } from "../compareSummary";
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

  it("directionHint shows lower/higher is better", () => {
    expect(directionHint("min")).toContain("lower");
    expect(directionHint("max")).toContain("higher");
  });

  it("buildCompareVerdict summarizes winners", () => {
    const rows = [
      {
        key: "a",
        label: "CrewAI",
        m: monitor({ cost_usd: 0.2, metrics: { ...baseMetrics, tests_passed: 3 } }),
      },
      {
        key: "b",
        label: "LangGraph",
        m: monitor({ cost_usd: 0.1, metrics: { ...baseMetrics, tests_passed: 5 } }),
      },
    ];
    const verdict = buildCompareVerdict(rows, [
      { label: "cost", prefer: "min", numeric: (m) => m.cost_usd ?? 999 },
      { label: "tests passed", prefer: "max", numeric: (m) => m.metrics.tests_passed },
    ]);
    expect(verdict).toContain("LangGraph: lowest cost");
    expect(verdict).toContain("LangGraph: highest tests passed");
  });
});
