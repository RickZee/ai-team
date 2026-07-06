import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { RunList } from "../RunList";
import type { RunInfo } from "../../types";

const runs: RunInfo[] = [
  {
    run_id: "run-a",
    backend: "langgraph",
    profile: "full",
    description: "Alpha project",
    status: "complete",
    started_at: "2026-06-01T10:00:00Z",
    finished_at: "2026-06-01T10:05:00Z",
    error: null,
  },
  {
    run_id: "run-b",
    backend: "crewai",
    profile: "full",
    description: "Beta API",
    status: "error",
    started_at: "2026-06-02T10:00:00Z",
    finished_at: "2026-06-02T10:02:00Z",
    error: "failed",
  },
];

describe("RunList", () => {
  it("filters by status", async () => {
    const user = userEvent.setup();
    render(
      <RunList runs={runs} selectedRunId={null} onSelect={vi.fn()} />,
    );

    await user.selectOptions(screen.getByTestId("run-list-status-filter"), "error");
    expect(screen.getByTestId("run-item-run-b")).toBeInTheDocument();
    expect(screen.queryByTestId("run-item-run-a")).not.toBeInTheDocument();

    await user.selectOptions(screen.getByTestId("run-list-status-filter"), "");
    expect(screen.getByTestId("run-item-run-a")).toBeInTheDocument();
    expect(screen.getByTestId("run-item-run-b")).toBeInTheDocument();
  });

  it("shows filtered empty state with clear action", async () => {
    const user = userEvent.setup();
    render(
      <RunList runs={runs} selectedRunId={null} onSelect={vi.fn()} />,
    );

    await user.type(screen.getByTestId("run-list-search"), "nonexistent");
    expect(screen.getByTestId("run-list-empty-filtered")).toHaveTextContent("No runs match");
    expect(screen.getByTestId("run-list-clear-filters")).toBeInTheDocument();
  });

  it("caps visible runs per day group with show all", async () => {
    const user = userEvent.setup();
    const todayIso = new Date().toISOString();
    const manyRuns: RunInfo[] = Array.from({ length: 25 }, (_, i) => ({
      run_id: `run-${i}`,
      backend: "langgraph",
      profile: "full",
      description: `Project ${i}`,
      status: "complete",
      started_at: todayIso,
      finished_at: todayIso,
      error: null,
    }));

    render(
      <RunList runs={manyRuns} selectedRunId={null} onSelect={vi.fn()} />,
    );

    expect(screen.getByTestId("run-list-show-all-Today")).toBeInTheDocument();
    await user.click(screen.getByTestId("run-list-show-all-Today"));
    expect(screen.getByTestId("run-item-run-24")).toBeInTheDocument();
  });
});
