import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { Dashboard } from "../Dashboard";
import { getRun, getRuns } from "../../hooks/useApi";

vi.mock("../../hooks/useApi", () => ({
  getHealth: vi.fn().mockResolvedValue({ status: "ok" }),
  getRuns: vi.fn().mockResolvedValue({ runs: [] }),
  getRun: vi.fn(),
  postDemo: vi.fn(),
  getProjectTests: vi.fn().mockResolvedValue({ total: 0, passed: 0, failed: 0 }),
  getProjectArchitecture: vi.fn().mockResolvedValue({ system_overview: "" }),
}));

vi.mock("../../hooks/useWebSocket", () => ({
  useMonitorWebSocket: vi.fn(() => ({
    monitor: null,
    runStatus: null,
    hitlPayload: null,
    errorMessage: null,
  })),
}));

describe("Dashboard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders empty state with CTAs", async () => {
    render(
      <MemoryRouter>
        <Dashboard />
      </MemoryRouter>,
    );
    expect(await screen.findByTestId("dashboard-empty")).toBeInTheDocument();
    expect(screen.getByText("Go to Run")).toBeInTheDocument();
    expect(screen.getByTestId("dashboard-demo")).toBeInTheDocument();
  });

  it("shows run date and assignment in sidebar", async () => {
    vi.mocked(getRuns).mockResolvedValue({
      runs: [
        {
          run_id: "run-1",
          backend: "langgraph",
          profile: "full",
          description: "Build a Flask REST API for todos",
          status: "complete",
          started_at: "2026-05-20T10:00:00.000Z",
          finished_at: "2026-05-20T10:05:00.000Z",
          error: null,
        },
      ],
    });
    vi.mocked(getRun).mockResolvedValue({
      run_id: "run-1",
      backend: "langgraph",
      profile: "full",
      description: "Build a Flask REST API for todos",
      status: "complete",
      monitor: {
        phase: "complete",
        elapsed: "5m",
        agents: {},
        metrics: {
          tasks_completed: 1,
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
      },
    });

    render(
      <MemoryRouter initialEntries={["/runs/run-1"]}>
        <Routes>
          <Route path="/runs/:runId" element={<Dashboard />} />
        </Routes>
      </MemoryRouter>,
    );

    expect(await screen.findByTestId("run-item-run-1")).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByTestId("dashboard-active")).toBeInTheDocument();
    });
    expect(screen.getByTestId("run-item-run-1")).toHaveTextContent(
      "Build a Flask REST API for todos",
    );
    expect(screen.getByTestId("run-summary-card")).toBeInTheDocument();
    expect(screen.getByTestId("dashboard-view-artifacts")).toBeInTheDocument();
  });
});
