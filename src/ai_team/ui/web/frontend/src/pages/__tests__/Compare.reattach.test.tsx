import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { Compare } from "../Compare";
import { getComparison, getRun } from "../../hooks/useApi";
import { useRunWebSocket, useMonitorWebSocket } from "../../hooks/useWebSocket";

const ACTIVE_COMPARE_KEY = "ai-team-compare-active";

vi.mock("../../hooks/useCatalog", () => ({
  useCatalog: vi.fn(() => ({
    backends: [],
    profiles: {},
    profileNames: ["full"],
    loading: false,
    error: null,
  })),
}));

vi.mock("../../hooks/useApi", () => ({
  postEstimate: vi.fn(),
  postDemo: vi.fn(),
  getComparison: vi.fn(),
  getRun: vi.fn(),
}));

const idleWs = {
  monitor: null,
  events: [],
  runId: null,
  projectId: null,
  status: "idle" as const,
  errorMessage: null,
  hitlPayload: null,
  startRun: vi.fn(),
  disconnect: vi.fn(),
};

const idleMonitor = {
  monitor: null,
  runStatus: null,
  hitlPayload: null,
  errorMessage: null,
  clearHitl: vi.fn(),
};

vi.mock("../../hooks/useWebSocket", () => ({
  useRunWebSocket: vi.fn(() => ({ ...idleWs })),
  useMonitorWebSocket: vi.fn(() => ({ ...idleMonitor })),
}));

const terminalMonitor = {
  phase: "complete",
  elapsed: "5m",
  agents: {
    backend_developer: {
      role: "backend_developer",
      status: "working",
      current_task: "Stale",
      tasks_completed: 1,
      model: "test",
    },
  },
  metrics: {
    tasks_completed: 2,
    tasks_failed: 0,
    retries: 0,
    files_generated: 1,
    guardrails_passed: 0,
    guardrails_failed: 0,
    guardrails_warned: 0,
    tests_passed: 1,
    tests_failed: 0,
  },
  log: [],
  guardrail_events: [],
};

describe("Compare — stale reattach", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    vi.mocked(useRunWebSocket).mockReturnValue({ ...idleWs });
    vi.mocked(useMonitorWebSocket).mockReturnValue({ ...idleMonitor });
  });

  it("shows finished banner without active/waiting affordances for terminal reattach", async () => {
    localStorage.setItem(
      ACTIVE_COMPARE_KEY,
      JSON.stringify({
        comparisonId: "cmp-1",
        runIds: { crewai: "r1", langgraph: "r2", "claude-agent-sdk": "r3" },
      }),
    );

    vi.mocked(getComparison).mockResolvedValue({
      runs: [
        { backend: "crewai", run_id: "r1", status: "complete", error: null },
        { backend: "langgraph", run_id: "r2", status: "complete", error: null },
        { backend: "claude-agent-sdk", run_id: "r3", status: "complete", error: null },
      ],
    });
    vi.mocked(getRun).mockResolvedValue({
      run_id: "r1",
      backend: "crewai",
      profile: "full",
      description: "Done",
      status: "complete",
      monitor: terminalMonitor,
    });

    render(
      <MemoryRouter>
        <Compare />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("compare-finished-banner")).toBeInTheDocument();
    });
    expect(screen.queryByText(/Waiting for agents/i)).not.toBeInTheDocument();
    expect(screen.queryByText("Not started")).not.toBeInTheDocument();
    expect(screen.getAllByTestId("compare-crewai-open-run").length).toBeGreaterThan(0);
  });

  it("clears stored comparison when New comparison is clicked", async () => {
    const user = userEvent.setup();
    localStorage.setItem(
      ACTIVE_COMPARE_KEY,
      JSON.stringify({
        comparisonId: "cmp-2",
        runIds: { crewai: "r1", langgraph: "r2", "claude-agent-sdk": "r3" },
      }),
    );

    vi.mocked(getComparison).mockResolvedValue({
      runs: [
        { backend: "crewai", run_id: "r1", status: "complete", error: null },
        { backend: "langgraph", run_id: "r2", status: "complete", error: null },
        { backend: "claude-agent-sdk", run_id: "r3", status: "complete", error: null },
      ],
    });
    vi.mocked(getRun).mockResolvedValue({
      run_id: "r1",
      backend: "crewai",
      profile: "full",
      description: "Done",
      status: "complete",
      monitor: terminalMonitor,
    });

    render(
      <MemoryRouter>
        <Compare />
      </MemoryRouter>,
    );

    await waitFor(() => screen.getByTestId("compare-clear"));
    await user.click(screen.getByTestId("compare-clear"));
    expect(localStorage.getItem(ACTIVE_COMPARE_KEY)).toBeNull();
    expect(screen.queryByTestId("compare-finished-banner")).not.toBeInTheDocument();
  });
});
