import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { Compare } from "../pages/Compare";
import { Home } from "../pages/Home";
import { Run } from "../pages/Run";
import { RunDetail } from "../pages/RunDetail";
import { getRun, getRuns } from "../hooks/useApi";
import { useMonitorWebSocket } from "../hooks/useWebSocket";
import { makeMonitor, runningRun } from "../test/fixtures/monitor";

vi.mock("../hooks/useApi", () => ({
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
  getRunReceipt: vi.fn().mockResolvedValue(null),
  postDemo: vi.fn().mockResolvedValue({ run_id: "demo-1" }),
  postEstimate: vi.fn(),
  postCancel: vi.fn(),
  deleteRun: vi.fn(),
  getProjectTests: vi.fn().mockResolvedValue({ total: 0, passed: 0, failed: 0, source: "empty" }),
  getProjectArchitecture: vi.fn().mockResolvedValue({ system_overview: "" }),
  getProjectTree: vi.fn().mockResolvedValue({ tree: [] }),
  getComparison: vi.fn(),
}));

vi.mock("../hooks/useCatalog", () => ({
  useCatalog: vi.fn(() => ({
    backends: [{ name: "langgraph", label: "LangGraph", streaming: true }],
    profiles: {},
    profileNames: ["full"],
    loading: false,
    error: null,
  })),
}));

vi.mock("../hooks/useWebSocket", () => ({
  useRunWebSocket: vi.fn(() => ({
    monitor: null,
    events: [],
    runId: null,
    projectId: null,
    status: "idle",
    errorMessage: null,
    hitlPayload: null,
    startRun: vi.fn(),
    disconnect: vi.fn(),
  })),
  useMonitorWebSocket: vi.fn(() => ({
    monitor: null,
    runStatus: null,
    hitlPayload: null,
    errorMessage: null,
    clearHitl: vi.fn(),
  })),
}));

function assertLabelsResolve(container: HTMLElement) {
  const labels = [...container.querySelectorAll("label")];
  for (const label of labels) {
    const htmlFor = label.getAttribute("for");
    if (htmlFor) {
      expect(container.querySelector(`#${CSS.escape(htmlFor)}`), `label htmlFor=${htmlFor}`).toBeTruthy();
    } else {
      expect(
        label.querySelector("input, select, textarea"),
        "nested label has a control",
      ).toBeTruthy();
    }
  }
}

function assertTabsResolve(container: HTMLElement) {
  const tabs = [...container.querySelectorAll('[role="tab"]')];
  for (const tab of tabs) {
    const controls = tab.getAttribute("aria-controls");
    expect(controls, "tab aria-controls").toBeTruthy();
    const panel = container.querySelector(`#${CSS.escape(controls!)}`);
    expect(panel, `panel ${controls}`).toBeTruthy();
    expect(panel?.getAttribute("role")).toBe("tabpanel");
  }
}

describe("a11y invariants", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(getRuns).mockResolvedValue({ runs: [] });
  });

  it("Home has one h1 and resolvable labels", async () => {
    render(
      <MemoryRouter>
        <Home />
      </MemoryRouter>,
    );
    expect(await screen.findByRole("heading", { level: 1, name: "Runs" })).toBeInTheDocument();
    expect(document.querySelectorAll("h1")).toHaveLength(1);
    assertLabelsResolve(document.body);
    assertTabsResolve(document.body);
  });

  it("Run has one h1 and resolvable labels", () => {
    render(
      <MemoryRouter>
        <Run />
      </MemoryRouter>,
    );
    expect(screen.getByRole("heading", { level: 1, name: "Run pipeline" })).toBeInTheDocument();
    expect(document.querySelectorAll("h1")).toHaveLength(1);
    assertLabelsResolve(document.body);
  });

  it("Compare has one h1 and resolvable labels", () => {
    render(
      <MemoryRouter>
        <Compare />
      </MemoryRouter>,
    );
    expect(screen.getByRole("heading", { level: 1, name: "Compare backends" })).toBeInTheDocument();
    expect(document.querySelectorAll("h1")).toHaveLength(1);
    assertLabelsResolve(document.body);
  });

  it("RunDetail has one h1 and tab/tabpanel pairing", async () => {
    const monitor = makeMonitor();
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
    expect(await screen.findByTestId("run-detail")).toBeInTheDocument();
    expect(document.querySelectorAll("h1")).toHaveLength(1);
    assertTabsResolve(document.body);
  });
});
