import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { Artifacts } from "../Artifacts";

vi.mock("../../hooks/useUnifiedRuns", () => ({
  useUnifiedRuns: vi.fn(() => ({
    runs: [
      {
        run_id: "abc12345",
        backend: "langgraph",
        profile: "full",
        description: "Build API",
        status: "complete",
        started_at: "2026-05-20T10:00:00.000Z",
        finished_at: null,
        source: "disk",
        has_disk_artifacts: true,
      },
      {
        run_id: "demo99",
        backend: "demo",
        profile: "full",
        description: "Demo: Flask REST API",
        status: "complete",
        started_at: "2026-05-20T11:00:00.000Z",
        finished_at: null,
        source: "session",
        has_disk_artifacts: false,
      },
    ],
    loading: false,
    error: null,
    refresh: vi.fn(),
  })),
  formatUnifiedRunLabel: (r: { run_id: string; backend: string }) =>
    `${r.run_id} · ${r.backend}`,
}));

vi.mock("../../hooks/useApi", () => ({
  getProjectTree: vi.fn().mockResolvedValue({ tree: [] }),
  getProjectFile: vi.fn(),
  getProjectTests: vi.fn().mockResolvedValue({ total: 0, passed: 0, failed: 0 }),
  getProjectArchitecture: vi.fn().mockResolvedValue({ system_overview: "" }),
}));

describe("Artifacts", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders page and run select", () => {
    render(
      <MemoryRouter>
        <Artifacts />
      </MemoryRouter>,
    );
    expect(screen.getByTestId("artifacts-page")).toBeInTheDocument();
    expect(screen.getByTestId("artifact-run-select")).toBeInTheDocument();
  });

  it("shows demo empty state when demo run selected", async () => {
    render(
      <MemoryRouter initialEntries={["/artifacts?project=demo99"]}>
        <Artifacts />
      </MemoryRouter>,
    );
    expect(await screen.findByTestId("artifacts-demo-empty")).toBeInTheDocument();
    expect(screen.getByText(/no files on disk/i)).toBeInTheDocument();
  });
});
