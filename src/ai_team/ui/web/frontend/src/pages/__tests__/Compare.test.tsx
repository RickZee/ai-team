import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { Compare } from "../Compare";

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

vi.mock("../../hooks/useWebSocket", () => ({
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
  })),
}));

describe("Compare", () => {
  it("renders three backend columns", () => {
    render(<Compare />);
    expect(screen.getByText("CrewAI")).toBeInTheDocument();
    expect(screen.getByText("LangGraph")).toBeInTheDocument();
    expect(screen.getByText("Claude Agent SDK")).toBeInTheDocument();
    expect(screen.getByTestId("compare-crewai-col")).toBeInTheDocument();
    expect(screen.getByTestId("compare-langgraph-col")).toBeInTheDocument();
    expect(screen.getByTestId("compare-claude-col")).toBeInTheDocument();
  });

  it("disables compare submit without description", () => {
    render(<Compare />);
    expect(screen.getByTestId("compare-submit")).toBeDisabled();
  });

  it("shows compare demo button", () => {
    render(<Compare />);
    expect(screen.getByTestId("compare-demo")).toBeInTheDocument();
  });
});
