import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { Run } from "../Run";
import { useRunWebSocket } from "../../hooks/useWebSocket";

vi.mock("../../hooks/useCatalog", () => ({
  useCatalog: vi.fn(() => ({
    backends: [
      { name: "langgraph", label: "LangGraph", streaming: true },
      { name: "crewai", label: "CrewAI", streaming: false },
    ],
    profiles: { full: { agents: [], phases: [] } },
    profileNames: ["full"],
    loading: false,
    error: null,
  })),
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
}));

const defaultWs = {
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

describe("Run", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(useRunWebSocket).mockReturnValue(defaultWs);
  });

  it("disables Run when description is empty", () => {
    render(
      <MemoryRouter>
        <Run />
      </MemoryRouter>,
    );
    expect(screen.getByTestId("run-submit")).toBeDisabled();
  });

  it("renders backend select from catalog", () => {
    render(
      <MemoryRouter>
        <Run />
      </MemoryRouter>,
    );
    expect(screen.getByTestId("run-backend")).toBeInTheDocument();
    expect(screen.getByText(/LangGraph/)).toBeInTheDocument();
  });

  it("enables Run when description is provided", async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <Run />
      </MemoryRouter>,
    );
    await user.type(screen.getByTestId("run-description"), "Build an API");
    expect(screen.getByTestId("run-submit")).toBeEnabled();
  });

  it("shows HITL panel when awaiting human", () => {
    vi.mocked(useRunWebSocket).mockReturnValue({
      monitor: null,
      events: [],
      runId: "hitl-1",
      projectId: "hitl-1",
      status: "awaiting_human",
      errorMessage: null,
      hitlPayload: { phase: "awaiting_human" },
      startRun: vi.fn(),
      disconnect: vi.fn(),
    });
    render(
      <MemoryRouter>
        <Run />
      </MemoryRouter>,
    );
    expect(screen.getByTestId("hitl-panel")).toBeInTheDocument();
  });
});
