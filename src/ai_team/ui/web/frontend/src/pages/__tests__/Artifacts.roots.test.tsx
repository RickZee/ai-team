import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { Artifacts } from "../Artifacts";
import { getProjectTree } from "../../hooks/useApi";

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
        finished_at: "2026-05-20T10:05:00.000Z",
        source: "disk",
        has_disk_artifacts: true,
      },
    ],
    loading: false,
    error: null,
    refresh: vi.fn(),
  })),
  formatUnifiedRunLabel: (r: { run_id: string; backend: string; started_at: string; description?: string }) =>
    `${r.started_at} · ${r.backend} · ${r.description || r.run_id}`,
  formatUnifiedRunTooltip: (r: { run_id: string; description?: string }) =>
    r.description ? `${r.run_id} — ${r.description}` : r.run_id,
}));

vi.mock("../../hooks/useApi", () => ({
  getProjectTree: vi.fn(),
  getProjectFile: vi.fn(),
  getProjectTests: vi.fn().mockResolvedValue({ total: 0, passed: 0, failed: 0 }),
  getProjectArchitecture: vi.fn().mockResolvedValue({ system_overview: "" }),
}));

describe("Artifacts — root auto-switch", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("auto-switches to bundle when workspace tree is empty", async () => {
    vi.mocked(getProjectTree).mockImplementation(async (_pid, root) => {
      if (root === "workspace") return { tree: [] };
      return {
        tree: [
          {
            name: "manifest.json",
            path: "manifest.json",
            type: "file",
            children: [],
            size: 42,
          },
        ],
      };
    });

    render(
      <MemoryRouter initialEntries={["/artifacts?project=abc12345"]}>
        <Artifacts />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText(/Files \(bundle\)/i)).toBeInTheDocument();
    });
    expect(screen.getByTestId("tree-file-manifest.json")).toBeInTheDocument();
  });

  it("shows past-tense empty copy for terminal run with no files in either root", async () => {
    vi.mocked(getProjectTree).mockResolvedValue({ tree: [] });

    render(
      <MemoryRouter initialEntries={["/artifacts?project=abc12345"]}>
        <Artifacts />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("artifacts-no-files")).toBeInTheDocument();
    });
    expect(screen.getByTestId("artifacts-no-files")).toHaveTextContent(/No files found for this run/);
    expect(screen.getByTestId("artifacts-no-files")).not.toHaveTextContent(/yet/i);
  });
});
