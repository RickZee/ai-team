import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { Home } from "../Home";
import { RunDetail } from "../RunDetail";
import { getRun, getRuns, postResume } from "../../hooks/useApi";
import { useMonitorWebSocket } from "../../hooks/useWebSocket";

vi.mock("../../hooks/useApi", () => ({
  ApiError: class ApiError extends Error {
    status: number;
    constructor(message: string, status: number) {
      super(message);
      this.status = status;
    }
  },
  getHealth: vi.fn().mockResolvedValue({ status: "ok" }),
  getRuns: vi.fn().mockResolvedValue({ runs: [] }),
  getRun: vi.fn(),
  postDemo: vi.fn().mockResolvedValue({ run_id: "demo-99" }),
  postCancel: vi.fn(),
  postResume: vi.fn(),
  deleteRun: vi.fn(),
  getProjectTests: vi.fn().mockResolvedValue({ total: 0, passed: 0, failed: 0, source: "empty" }),
  getProjectArchitecture: vi.fn().mockResolvedValue({ system_overview: "" }),
  getProjectTree: vi.fn().mockResolvedValue({ tree: [] }),
  getProjectFile: vi.fn(),
}));

vi.mock("../../hooks/useWebSocket", () => ({
  useMonitorWebSocket: vi.fn(() => ({
    monitor: null,
    runStatus: null,
    hitlPayload: null,
    errorMessage: null,
    clearHitl: vi.fn(),
  })),
}));

describe("Home", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders empty state with CTAs", async () => {
    render(
      <MemoryRouter>
        <Home />
      </MemoryRouter>,
    );
    expect(await screen.findByTestId("home-empty")).toBeInTheDocument();
    expect(screen.getByTestId("how-it-works")).toBeInTheDocument();
    expect(screen.getByTestId("home-new-run")).toBeInTheDocument();
    expect(screen.getByTestId("home-demo")).toBeInTheDocument();
  });

  it("shows run in list on home", async () => {
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

    render(
      <MemoryRouter>
        <Home />
      </MemoryRouter>,
    );

    expect(await screen.findByTestId("run-item-run-1")).toBeInTheDocument();
    expect(screen.getByTestId("run-item-run-1")).toHaveTextContent(
      "Build a Flask REST API for todos",
    );
  });
});

describe("RunDetail", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows summary and artifacts link for completed run", async () => {
    vi.mocked(getRuns).mockResolvedValue({ runs: [] });
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
          <Route path="/runs/:runId" element={<RunDetail />} />
        </Routes>
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("run-detail")).toBeInTheDocument();
    });
    expect(screen.getByTestId("run-summary-card")).toBeInTheDocument();
    expect(screen.getByTestId("dashboard-view-artifacts")).toHaveAttribute(
      "href",
      "/runs/run-1#artifacts",
    );
  });

  it("shows Sample tag for is_sample runs on home list", async () => {
    vi.mocked(getRuns).mockResolvedValue({
      runs: [
        {
          run_id: "sample-1",
          backend: "demo",
          profile: "full",
          description: "Sample run",
          status: "complete",
          started_at: "2026-06-01T10:00:00Z",
          finished_at: "2026-06-01T10:01:00Z",
          error: null,
          is_sample: true,
        },
      ],
    });

    render(
      <MemoryRouter>
        <Home />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("sample-tag-sample-1")).toBeInTheDocument();
    });
  });

  it("renders terminal run when runs list is empty", async () => {
    vi.mocked(getRuns).mockResolvedValue({ runs: [] });
    vi.mocked(getRun).mockResolvedValue({
      run_id: "orphan-complete",
      backend: "langgraph",
      profile: "full",
      description: "Orphan completed run",
      status: "complete",
      monitor: {
        phase: "complete",
        elapsed: "5m",
        agents: {},
        metrics: {
          tasks_completed: 2,
          tasks_failed: 0,
          retries: 0,
          files_generated: 1,
          guardrails_passed: 0,
          guardrails_failed: 0,
          guardrails_warned: 0,
          tests_passed: 3,
          tests_failed: 0,
        },
        log: [],
        guardrail_events: [],
      },
    });

    render(
      <MemoryRouter initialEntries={["/runs/orphan-complete"]}>
        <Routes>
          <Route path="/runs/:runId" element={<RunDetail />} />
        </Routes>
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("run-summary-card")).toBeInTheDocument();
    });
    expect(screen.queryByText(/Waiting for agents/i)).not.toBeInTheDocument();
  });

  it("hides HITL panel after successful resume", async () => {
    const user = userEvent.setup();
    const clearHitl = vi.fn();
    let resumed = false;
    const awaitingRun = {
      run_id: "hitl-1",
      backend: "langgraph",
      profile: "full",
      description: "HITL run",
      status: "awaiting_human",
      started_at: "2026-06-01T10:00:00Z",
      finished_at: null,
      error: null,
    };
    const monitor = {
      phase: "planning",
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
    };

    vi.mocked(getRuns).mockImplementation(async () => ({
      runs: [{ ...awaitingRun, status: resumed ? "running" : "awaiting_human" }],
    }));
    vi.mocked(getRun).mockImplementation(async () => ({
      ...awaitingRun,
      status: resumed ? "running" : "awaiting_human",
      monitor,
    }));
    vi.mocked(useMonitorWebSocket).mockReturnValue({
      monitor,
      runStatus: "awaiting_human",
      hitlPayload: { phase: "awaiting_human" },
      errorMessage: null,
      clearHitl,
    });
    vi.mocked(postResume).mockImplementation(async () => {
      resumed = true;
      return { run_id: "hitl-1", status: "running" };
    });

    render(
      <MemoryRouter initialEntries={["/runs/hitl-1"]}>
        <Routes>
          <Route path="/runs/:runId" element={<RunDetail />} />
        </Routes>
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("hitl-panel")).toBeInTheDocument();
    });

    await user.click(screen.getByTestId("hitl-approve"));

    await waitFor(() => {
      expect(postResume).toHaveBeenCalledTimes(1);
      expect(clearHitl).toHaveBeenCalled();
    });

    await waitFor(() => {
      expect(screen.queryByTestId("hitl-panel")).not.toBeInTheDocument();
    });
  });
});
