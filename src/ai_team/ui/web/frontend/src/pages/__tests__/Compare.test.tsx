import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { Compare } from "../Compare";
import { useRunWebSocket, useMonitorWebSocket } from "../../hooks/useWebSocket";

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
};

vi.mock("../../hooks/useWebSocket", () => ({
  useRunWebSocket: vi.fn(() => ({ ...idleWs })),
  useMonitorWebSocket: vi.fn(() => ({ ...idleMonitor })),
}));

describe("Compare — base rendering", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(useRunWebSocket).mockReturnValue({ ...idleWs });
    vi.mocked(useMonitorWebSocket).mockReturnValue({ ...idleMonitor });
  });

  it("renders three backend columns", () => {
    render(<MemoryRouter><Compare /></MemoryRouter>);
    expect(screen.getByText("CrewAI")).toBeInTheDocument();
    expect(screen.getByText("LangGraph")).toBeInTheDocument();
    expect(screen.getByText("Claude Agent SDK")).toBeInTheDocument();
    expect(screen.getByTestId("compare-crewai-col")).toBeInTheDocument();
    expect(screen.getByTestId("compare-langgraph-col")).toBeInTheDocument();
    expect(screen.getByTestId("compare-claude-col")).toBeInTheDocument();
  });

  it("disables compare submit without description", () => {
    render(<MemoryRouter><Compare /></MemoryRouter>);
    expect(screen.getByTestId("compare-submit")).toBeDisabled();
  });

  it("shows compare demo button", () => {
    render(<MemoryRouter><Compare /></MemoryRouter>);
    expect(screen.getByTestId("compare-demo")).toBeInTheDocument();
  });

  it("no failure banner when all idle", () => {
    render(<MemoryRouter><Compare /></MemoryRouter>);
    expect(screen.queryByTestId("compare-failures-banner")).not.toBeInTheDocument();
  });
});

describe("Compare — failure visibility", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(useMonitorWebSocket).mockReturnValue({ ...idleMonitor });
  });

  const errorWs = (msg: string) => ({
    ...idleWs,
    status: "error" as const,
    errorMessage: msg,
  });

  it("shows failure banner when one backend errors", () => {
    let call = 0;
    vi.mocked(useRunWebSocket).mockImplementation(() => {
      call++;
      if (call === 1) return errorWs("Invalid response from LLM - None or empty.");
      return { ...idleWs };
    });
    render(<MemoryRouter><Compare /></MemoryRouter>);
    expect(screen.getByTestId("compare-failures-banner")).toBeInTheDocument();
    expect(screen.getByText(/CrewAI failed/)).toBeInTheDocument();
  });

  it("banner lists failure reason for the failed backend", () => {
    let call = 0;
    vi.mocked(useRunWebSocket).mockImplementation(() => {
      call++;
      if (call === 1) return errorWs("API rate limit exceeded");
      return { ...idleWs };
    });
    render(<MemoryRouter><Compare /></MemoryRouter>);
    const item = screen.getByTestId("compare-failure-crewai");
    expect(item).toHaveTextContent("API rate limit exceeded");
  });

  it("banner says N backends failed when multiple error", () => {
    let call = 0;
    vi.mocked(useRunWebSocket).mockImplementation(() => {
      call++;
      if (call <= 2) return errorWs("timeout");
      return { ...idleWs };
    });
    render(<MemoryRouter><Compare /></MemoryRouter>);
    expect(screen.getByTestId("compare-failures-banner")).toHaveTextContent("2 backends failed");
  });

  it("banner includes 'remaining backends continue'", () => {
    let call = 0;
    vi.mocked(useRunWebSocket).mockImplementation(() => {
      call++;
      if (call === 2) return errorWs("LLM empty response");
      return { ...idleWs };
    });
    render(<MemoryRouter><Compare /></MemoryRouter>);
    expect(screen.getByTestId("compare-failures-banner")).toHaveTextContent("remaining backends continue");
  });

  it("shows error block in the failed column with reason", () => {
    let call = 0;
    vi.mocked(useRunWebSocket).mockImplementation(() => {
      call++;
      if (call === 2) return errorWs("Model not available");
      return { ...idleWs };
    });
    render(<MemoryRouter><Compare /></MemoryRouter>);
    const errEl = screen.getByTestId("compare-langgraph-error");
    expect(errEl).toBeInTheDocument();
    expect(screen.getByTestId("compare-langgraph-error-reason")).toHaveTextContent("Model not available");
  });

  it("failed backend appears in summary table with '—' metrics", () => {
    let call = 0;
    vi.mocked(useRunWebSocket).mockImplementation(() => {
      call++;
      // crewai errors but has a monitor snapshot
      if (call === 1) return {
        ...idleWs,
        status: "error" as const,
        errorMessage: "crashed",
        monitor: {
          phase: "development",
          elapsed: "1m",
          agents: {},
          metrics: { tasks_completed: 2, tasks_failed: 1, retries: 0, files_generated: 1, guardrails_passed: 1, guardrails_failed: 0, guardrails_warned: 0, tests_passed: 0, tests_failed: 0 },
          log: [],
          guardrail_events: [],
        },
      };
      // langgraph complete with monitor
      if (call === 2) return {
        ...idleWs,
        status: "complete" as const,
        monitor: {
          phase: "complete",
          elapsed: "2m",
          agents: {},
          metrics: { tasks_completed: 5, tasks_failed: 0, retries: 0, files_generated: 3, guardrails_passed: 2, guardrails_failed: 0, guardrails_warned: 0, tests_passed: 4, tests_failed: 0 },
          log: [],
          guardrail_events: [],
        },
      };
      return { ...idleWs };
    });
    render(<MemoryRouter><Compare /></MemoryRouter>);
    expect(screen.getByTestId("compare-summary")).toBeInTheDocument();
    // Failed backend still appears as a column in the summary table
    expect(screen.getByTestId("summary-reason-crewai")).toBeInTheDocument();
    expect(screen.getByTestId("summary-reason-crewai")).toHaveTextContent("crashed");
  });

  it("failure reason row appears in summary when any backend failed", () => {
    let call = 0;
    vi.mocked(useRunWebSocket).mockImplementation(() => {
      call++;
      if (call === 1) return {
        ...idleWs,
        status: "error" as const,
        errorMessage: "LLM timeout after 60s",
        monitor: {
          phase: "planning",
          elapsed: "0m 30s",
          agents: {},
          metrics: { tasks_completed: 0, tasks_failed: 1, retries: 0, files_generated: 0, guardrails_passed: 0, guardrails_failed: 0, guardrails_warned: 0, tests_passed: 0, tests_failed: 0 },
          log: [],
          guardrail_events: [],
        },
      };
      if (call === 2) return {
        ...idleWs,
        status: "complete" as const,
        monitor: {
          phase: "complete",
          elapsed: "3m",
          agents: {},
          metrics: { tasks_completed: 4, tasks_failed: 0, retries: 0, files_generated: 2, guardrails_passed: 1, guardrails_failed: 0, guardrails_warned: 0, tests_passed: 3, tests_failed: 0 },
          log: [],
          guardrail_events: [],
        },
      };
      return { ...idleWs };
    });
    render(<MemoryRouter><Compare /></MemoryRouter>);
    const reasonCell = screen.getByTestId("summary-reason-crewai");
    expect(reasonCell).toHaveTextContent("LLM timeout after 60s");
  });

  it("no failure banner when all backends complete", () => {
    const completeWs = {
      ...idleWs,
      status: "complete" as const,
      monitor: {
        phase: "complete",
        elapsed: "2m",
        agents: {},
        metrics: { tasks_completed: 3, tasks_failed: 0, retries: 0, files_generated: 2, guardrails_passed: 1, guardrails_failed: 0, guardrails_warned: 0, tests_passed: 2, tests_failed: 0 },
        log: [],
        guardrail_events: [],
      },
    };
    vi.mocked(useRunWebSocket).mockReturnValue(completeWs);
    render(<MemoryRouter><Compare /></MemoryRouter>);
    expect(screen.queryByTestId("compare-failures-banner")).not.toBeInTheDocument();
  });
});
