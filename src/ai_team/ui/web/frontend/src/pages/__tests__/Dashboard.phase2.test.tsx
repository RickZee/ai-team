import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { Dashboard } from "../Dashboard";
import { getRun, getRuns } from "../../hooks/useApi";
import { useMonitorWebSocket } from "../../hooks/useWebSocket";
import { makeLogLines, makeMonitor, runningRun } from "../../test/fixtures/monitor";
import { mockMatchMedia } from "../../test/matchMedia";

vi.mock("../../hooks/useApi", () => ({
  getHealth: vi.fn().mockResolvedValue({ status: "ok" }),
  getRuns: vi.fn(),
  getRun: vi.fn(),
  postDemo: vi.fn(),
  postCancel: vi.fn(),
  deleteRun: vi.fn(),
  getProjectTests: vi.fn().mockResolvedValue({ total: 0, passed: 0, failed: 0 }),
  getProjectArchitecture: vi.fn().mockResolvedValue({ system_overview: "" }),
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

const SIDEBAR_KEY = "ai-team-sidebar-collapsed";

describe("Dashboard — Phase 2 layout & UX", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    mockMatchMedia(false);
  });

  it("shows sidebar empty state when no runs exist", async () => {
    vi.mocked(getRuns).mockResolvedValue({ runs: [] });
    render(
      <MemoryRouter>
        <Dashboard />
      </MemoryRouter>,
    );
    expect(await screen.findByTestId("run-list-empty")).toBeInTheDocument();
    expect(screen.getByTestId("run-list-empty")).toHaveTextContent("No runs yet");
  });

  it("collapses sidebar and persists preference", async () => {
    const user = userEvent.setup();
    vi.mocked(getRuns).mockResolvedValue({ runs: [] });
    const { container } = render(
      <MemoryRouter>
        <Dashboard />
      </MemoryRouter>,
    );

    await screen.findByTestId("sidebar-toggle");
    await user.click(screen.getByTestId("sidebar-toggle"));

    expect(container.querySelector(".dashboard-layout.sidebar-collapsed")).toBeTruthy();
    expect(localStorage.getItem(SIDEBAR_KEY)).toBe("true");
  });

  it("shows stat strip and log preview for live runs", async () => {
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
          <Route path="/runs/:runId" element={<Dashboard />} />
        </Routes>
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("run-stat-strip")).toBeInTheDocument();
    });
    expect(screen.getByTestId("stat-cost")).toHaveTextContent("$0.0800");
    expect(screen.getByText(/Showing last 5 of 8 lines/)).toBeInTheDocument();
    expect(screen.queryByText("Log line 1")).not.toBeInTheDocument();
    expect(screen.getByText("Log line 8")).toBeInTheDocument();
  });

  it("expands activity log on demand", async () => {
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
          <Route path="/runs/:runId" element={<Dashboard />} />
        </Routes>
      </MemoryRouter>,
    );

    await waitFor(() => screen.getByText("Expand full log"));
    await user.click(screen.getByRole("button", { name: "Expand full log" }));
    expect(screen.getByText("Log line 1")).toBeInTheDocument();
    expect(screen.getByTestId("log-search")).toBeInTheDocument();
  });

  it("spans guardrails full width when failures exist", async () => {
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

    const { container } = render(
      <MemoryRouter initialEntries={["/runs/live-run-1"]}>
        <Routes>
          <Route path="/runs/:runId" element={<Dashboard />} />
        </Routes>
      </MemoryRouter>,
    );

    await waitFor(() => screen.getByText("blocked_path"));
    expect(container.querySelector(".guardrails.guardrails--span-full")).toBeTruthy();
  });

  it("opens sidebar drawer on narrow viewports", async () => {
    const user = userEvent.setup();
    mockMatchMedia(true);
    vi.mocked(getRuns).mockResolvedValue({ runs: [] });

    const { container } = render(
      <MemoryRouter>
        <Dashboard />
      </MemoryRouter>,
    );

    await screen.findByTestId("sidebar-toggle");
    expect(screen.getByTestId("sidebar-toggle")).toHaveTextContent("Show runs");
    await user.click(screen.getByTestId("sidebar-toggle"));
    expect(container.querySelector(".dashboard-layout.sidebar-drawer-open")).toBeTruthy();
  });
});
