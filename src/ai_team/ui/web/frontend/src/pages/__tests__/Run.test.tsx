import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { Run } from "../Run";
import { useRunWebSocket } from "../../hooks/useWebSocket";

vi.mock("../../hooks/useApi", () => ({
  postDemo: vi.fn().mockResolvedValue({ run_id: "demo-1" }),
  postEstimate: vi.fn().mockResolvedValue({
    complexity: "medium",
    rows: [],
    total_usd: 0.05,
    within_budget: true,
  }),
}));

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

  it("Demo button has updated label (T8)", () => {
    render(
      <MemoryRouter>
        <Run />
      </MemoryRouter>,
    );
    expect(screen.getByTestId("run-demo")).toHaveTextContent("Play sample run");
  });
});

describe("Run — T3: prefill from location state", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(useRunWebSocket).mockReturnValue(defaultWs);
  });

  it("prefills description from location state", () => {
    render(
      <MemoryRouter
        initialEntries={[{ pathname: "/run", state: { prefill: { description: "Build a todo app" } } }]}
      >
        <Run />
      </MemoryRouter>,
    );
    expect(screen.getByTestId("run-description")).toHaveValue("Build a todo app");
  });

  it("prefills backend from location state", () => {
    render(
      <MemoryRouter
        initialEntries={[{ pathname: "/run", state: { prefill: { backend: "crewai" } } }]}
      >
        <Run />
      </MemoryRouter>,
    );
    expect(screen.getByTestId("run-backend")).toHaveValue("crewai");
  });

  it("prefills profile from location state", () => {
    render(
      <MemoryRouter
        initialEntries={[{ pathname: "/run", state: { prefill: { profile: "full" } } }]}
      >
        <Run />
      </MemoryRouter>,
    );
    expect(screen.getByTestId("run-profile")).toHaveValue("full");
  });

  it("passes estimate_usd to startRun when estimate was run first", async () => {
    const user = userEvent.setup();
    const startRun = vi.fn();
    vi.mocked(useRunWebSocket).mockReturnValue({ ...defaultWs, startRun });
    const { postEstimate } = await import("../../hooks/useApi");

    render(
      <MemoryRouter>
        <Run />
      </MemoryRouter>,
    );

    await user.type(screen.getByTestId("run-description"), "Build an API");
    await user.click(screen.getByTestId("run-estimate"));
    // Wait for estimate mock to resolve
    await screen.findByText(/0\.05/);
    await user.click(screen.getByTestId("run-submit"));

    expect(postEstimate).toHaveBeenCalled();
    expect(startRun).toHaveBeenCalledWith(
      expect.any(String), // backend
      expect.any(String), // profile
      "Build an API",
      expect.any(String), // complexity
      0.05, // estimate_usd
    );
  });
});
