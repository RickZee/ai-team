import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { Home } from "../Home";
import { RunDetail } from "../RunDetail";
import { getRun, getRuns } from "../../hooks/useApi";
import { useMonitorWebSocket } from "../../hooks/useWebSocket";
import { makeLogLines, makeMonitor, runningRun } from "../../test/fixtures/monitor";

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
  deleteRun: vi.fn(),
  getProjectTests: vi.fn().mockResolvedValue({ total: 0, passed: 0, failed: 0, source: "empty" }),
  getProjectArchitecture: vi.fn().mockResolvedValue({ system_overview: "" }),
  getProjectTree: vi.fn().mockResolvedValue({ tree: [] }),
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

describe("Home — Phase 3 layout", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows empty state when no runs exist", async () => {
    vi.mocked(getRuns).mockResolvedValue({ runs: [] });
    render(
      <MemoryRouter>
        <Home />
      </MemoryRouter>,
    );
    expect(await screen.findByTestId("home-empty")).toBeInTheDocument();
    expect(screen.getByTestId("how-it-works")).toBeInTheDocument();
  });

  it("shows run list when runs exist", async () => {
    vi.mocked(getRuns).mockResolvedValue({ runs: [runningRun] });
    render(
      <MemoryRouter>
        <Home />
      </MemoryRouter>,
    );
    expect(await screen.findByTestId("run-item-live-run-1")).toBeInTheDocument();
  });
});

describe("RunDetail — Phase 2/3 layout", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows stat strip on run detail", async () => {
    const monitor = makeMonitor({
      log: makeLogLines(8),
      cost_usd: 0.08,
    });
    vi.mocked(getRuns).mockResolvedValue({ runs: [runningRun] });
    vi.mocked(getRun).mockResolvedValue({ ...runningRun, monitor });
    vi.mocked(useMonitorWebSocket).mockReturnValue({
      monitor,
      runStatus: "running",
      hitlPayload: null,
      errorMessage: null,
      clearHitl: vi.fn(),
    });

    render(
      <MemoryRouter initialEntries={["/runs/live-run-1"]}>
        <Routes>
          <Route path="/runs/:runId" element={<RunDetail />} />
        </Routes>
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("run-stat-strip")).toBeInTheDocument();
    });
    expect(screen.getByTestId("stat-cost")).toHaveTextContent("$0.0800");
  });

  it("expands activity log on activity tab", async () => {
    const user = userEvent.setup();
    const monitor = makeMonitor({ log: makeLogLines(8) });
    vi.mocked(getRuns).mockResolvedValue({ runs: [runningRun] });
    vi.mocked(getRun).mockResolvedValue({ ...runningRun, monitor });
    vi.mocked(useMonitorWebSocket).mockReturnValue({
      monitor,
      runStatus: "running",
      hitlPayload: null,
      errorMessage: null,
      clearHitl: vi.fn(),
    });

    render(
      <MemoryRouter initialEntries={["/runs/live-run-1"]}>
        <Routes>
          <Route path="/runs/:runId" element={<RunDetail />} />
        </Routes>
      </MemoryRouter>,
    );

    await waitFor(() => screen.getByTestId("run-tab-activity"));
    await user.click(screen.getByTestId("run-tab-activity"));
    await waitFor(() => screen.getByText("Expand full log"));
    await user.click(screen.getByRole("button", { name: "Expand full log" }));
    expect(screen.getByText("Log line 1")).toBeInTheDocument();
    expect(screen.getByTestId("log-search")).toBeInTheDocument();
  });

  it("mounts guardrails panel on activity tab when failures exist", async () => {
    const user = userEvent.setup();
    const monitor = makeMonitor({
      guardrail_events: [
        {
          timestamp: "2026-06-01T10:00:00Z",
          category: "security",
          name: "blocked_path",
          status: "fail",
          message: "Traversal",
        },
      ],
    });
    vi.mocked(getRuns).mockResolvedValue({ runs: [runningRun] });
    vi.mocked(getRun).mockResolvedValue({ ...runningRun, monitor });
    vi.mocked(useMonitorWebSocket).mockReturnValue({
      monitor,
      runStatus: "running",
      hitlPayload: null,
      errorMessage: null,
      clearHitl: vi.fn(),
    });

    render(
      <MemoryRouter initialEntries={["/runs/live-run-1"]}>
        <Routes>
          <Route path="/runs/:runId" element={<RunDetail />} />
        </Routes>
      </MemoryRouter>,
    );

    await user.click(await screen.findByTestId("run-tab-activity"));
    await waitFor(() => screen.getByText("blocked_path"));
  });
});
