import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { RunDetail } from "../RunDetail";
import { getRun, getRuns, postCancel } from "../../hooks/useApi";

vi.mock("../../hooks/useApi", () => ({
  ApiError: class ApiError extends Error {
    status: number;
    constructor(message: string, status: number) {
      super(message);
      this.status = status;
    }
  },
  getHealth: vi.fn().mockResolvedValue({ status: "ok" }),
  getRuns: vi.fn(),
  getRun: vi.fn(),
  postDemo: vi.fn(),
  postCancel: vi.fn(),
  getProjectTests: vi.fn().mockResolvedValue({ total: 0, passed: 0, failed: 0, source: "empty" }),
  getProjectArchitecture: vi.fn().mockResolvedValue({ system_overview: "" }),
}));

vi.mock("../../hooks/useWebSocket", () => ({
  useMonitorWebSocket: vi.fn(() => ({
    monitor: {
      phase: "development",
      elapsed: "1m 30s",
      agents: {},
      metrics: {
        tasks_completed: 1,
        tasks_failed: 0,
        retries: 0,
        files_generated: 1,
        guardrails_passed: 1,
        guardrails_failed: 0,
        guardrails_warned: 0,
        tests_passed: 0,
        tests_failed: 0,
      },
      log: [],
      guardrail_events: [],
    },
    runStatus: "running",
    hitlPayload: null,
    errorMessage: null,
    clearHitl: vi.fn(),
  })),
}));

const runningRun = {
  run_id: "live-1",
  backend: "langgraph",
  profile: "full",
  description: "Build a live API",
  status: "running",
  started_at: "2026-06-01T10:00:00Z",
  finished_at: null,
  error: null,
};

describe("Dashboard — T1: Stop run button", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows Stop run button when run is live", async () => {
    vi.mocked(getRuns).mockResolvedValue({ runs: [runningRun] });
    vi.mocked(getRun).mockResolvedValue({
      ...runningRun,
      monitor: {
        phase: "development",
        elapsed: "1m",
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
      },
    });

    render(
      <MemoryRouter initialEntries={["/runs/live-1"]}>
        <Routes>
          <Route path="/runs/:runId" element={<RunDetail />} />
        </Routes>
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("stop-run-btn")).toBeInTheDocument();
    });
  });

  it("calls postCancel after confirming the modal", async () => {
    const user = userEvent.setup();
    vi.mocked(getRuns).mockResolvedValue({ runs: [runningRun] });
    vi.mocked(getRun).mockResolvedValue({
      ...runningRun,
      monitor: {
        phase: "development",
        elapsed: "1m",
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
      },
    });
    vi.mocked(postCancel).mockResolvedValue({ run_id: "live-1", status: "cancelling" });

    render(
      <MemoryRouter initialEntries={["/runs/live-1"]}>
        <Routes>
          <Route path="/runs/:runId" element={<RunDetail />} />
        </Routes>
      </MemoryRouter>,
    );

    await waitFor(() => screen.getByTestId("stop-run-btn"));
    await user.click(screen.getByTestId("stop-run-btn"));

    // Confirm modal should appear
    expect(await screen.findByTestId("confirm-modal-ok")).toBeInTheDocument();
    await user.click(screen.getByTestId("confirm-modal-ok"));

    await waitFor(() => {
      expect(postCancel).toHaveBeenCalledWith("live-1");
    });
  });

  it("Stop run button not visible for cancelling status", async () => {
    const cancellingRun = { ...runningRun, status: "cancelling" };
    vi.mocked(getRuns).mockResolvedValue({ runs: [cancellingRun] });
    vi.mocked(getRun).mockResolvedValue({
      ...cancellingRun,
      monitor: {
        phase: "development",
        elapsed: "2m",
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
      },
    });

    render(
      <MemoryRouter initialEntries={["/runs/live-1"]}>
        <Routes>
          <Route path="/runs/:runId" element={<RunDetail />} />
        </Routes>
      </MemoryRouter>,
    );

    await waitFor(() => screen.getByTestId("run-detail"));
    expect(screen.queryByTestId("stop-run-btn")).not.toBeInTheDocument();
  });

  it("Stop run button not visible when run is terminal", async () => {
    const completedRun = { ...runningRun, status: "complete", finished_at: "2026-06-01T10:05:00Z" };
    vi.mocked(getRuns).mockResolvedValue({ runs: [completedRun] });
    vi.mocked(getRun).mockResolvedValue({
      ...completedRun,
      monitor: {
        phase: "complete",
        elapsed: "5m",
        agents: {},
        metrics: {
          tasks_completed: 3,
          tasks_failed: 0,
          retries: 0,
          files_generated: 3,
          guardrails_passed: 2,
          guardrails_failed: 0,
          guardrails_warned: 0,
          tests_passed: 5,
          tests_failed: 0,
        },
        log: [],
        guardrail_events: [],
      },
    });

    render(
      <MemoryRouter initialEntries={["/runs/live-1"]}>
        <Routes>
          <Route path="/runs/:runId" element={<RunDetail />} />
        </Routes>
      </MemoryRouter>,
    );

    await waitFor(() => screen.getByTestId("run-summary-card"));
    expect(screen.queryByTestId("stop-run-btn")).not.toBeInTheDocument();
  });
});
