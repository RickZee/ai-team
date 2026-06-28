import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { RunSummaryCard } from "../RunSummaryCard";
import type { MonitorState, RunInfo } from "../../types";

const mockNavigate = vi.fn();
vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual("react-router-dom");
  return { ...actual, useNavigate: () => mockNavigate };
});

const baseRun: RunInfo = {
  run_id: "test-1",
  backend: "langgraph",
  profile: "full",
  description: "Build a todo API",
  status: "complete",
  started_at: "2026-06-01T10:00:00Z",
  finished_at: "2026-06-01T10:05:00Z",
  error: null,
};

const baseMonitor: MonitorState = {
  phase: "complete",
  elapsed: "5m 0s",
  agents: {},
  metrics: {
    tasks_completed: 3,
    tasks_failed: 0,
    retries: 0,
    files_generated: 3,
    guardrails_passed: 2,
    guardrails_failed: 0,
    guardrails_warned: 0,
    tests_passed: 5,
    tests_failed: 0,
  },
  log: [],
  guardrail_events: [],
  cost_usd: 0.0512,
  token_estimate: 10000,
};

describe("RunSummaryCard — T2: estimate vs actual cost", () => {
  it("shows actual only when no estimate", () => {
    render(
      <MemoryRouter>
        <RunSummaryCard run={baseRun} monitor={baseMonitor} />
      </MemoryRouter>,
    );
    expect(screen.getByText(/Actual \$0\.0512/)).toBeInTheDocument();
    expect(screen.queryByText(/Est \$/)).not.toBeInTheDocument();
  });

  it("shows estimated and actual with delta when estimate provided", () => {
    render(
      <MemoryRouter>
        <RunSummaryCard run={baseRun} monitor={baseMonitor} estimateUsd={0.04} />
      </MemoryRouter>,
    );
    expect(screen.getByText(/Actual \$0\.0512/)).toBeInTheDocument();
    expect(screen.getByText(/Est \$0\.0400/)).toBeInTheDocument();
    // delta = 0.0512 - 0.04 = +0.0112 → positive → red
    expect(screen.getByText(/\+0\.0112/)).toBeInTheDocument();
  });

  it("shows 'estimate not run' when no estimate and no actual for non-demo", () => {
    const monitorNoCost: MonitorState = { ...baseMonitor, cost_usd: null };
    render(
      <MemoryRouter>
        <RunSummaryCard run={baseRun} monitor={monitorNoCost} />
      </MemoryRouter>,
    );
    expect(screen.getByText(/estimate not run/)).toBeInTheDocument();
  });

  it("demo run does not show misleading cost delta", () => {
    const demoRun: RunInfo = { ...baseRun, backend: "demo" };
    render(
      <MemoryRouter>
        <RunSummaryCard run={demoRun} monitor={baseMonitor} estimateUsd={0.05} />
      </MemoryRouter>,
    );
    // Demo: no estimate/delta shown
    expect(screen.queryByText(/Est \$/)).not.toBeInTheDocument();
    expect(screen.queryByText(/estimate not run/)).not.toBeInTheDocument();
  });
});

describe("RunSummaryCard — T3: retry and edit-and-rerun", () => {
  it("shows Retry and Edit & rerun buttons on error run", () => {
    const errorRun: RunInfo = { ...baseRun, status: "error", error: "backend failed" };
    render(
      <MemoryRouter>
        <RunSummaryCard run={errorRun} monitor={baseMonitor} />
      </MemoryRouter>,
    );
    expect(screen.getByTestId("retry-run-btn")).toBeInTheDocument();
    expect(screen.getByTestId("edit-rerun-btn")).toBeInTheDocument();
  });

  it("shows Retry and Edit & rerun buttons on cancelled run", () => {
    const cancelledRun: RunInfo = { ...baseRun, status: "cancelled" };
    render(
      <MemoryRouter>
        <RunSummaryCard run={cancelledRun} monitor={baseMonitor} />
      </MemoryRouter>,
    );
    expect(screen.getByTestId("retry-run-btn")).toBeInTheDocument();
    expect(screen.getByTestId("edit-rerun-btn")).toBeInTheDocument();
  });

  it("does not show retry buttons on complete run", () => {
    render(
      <MemoryRouter>
        <RunSummaryCard run={baseRun} monitor={baseMonitor} />
      </MemoryRouter>,
    );
    expect(screen.queryByTestId("retry-run-btn")).not.toBeInTheDocument();
  });

  it("Retry navigates to /run with prefilled config", async () => {
    const user = userEvent.setup();
    const errorRun: RunInfo = {
      ...baseRun,
      status: "error",
      complexity: "simple",
    };
    render(
      <MemoryRouter>
        <RunSummaryCard run={errorRun} monitor={baseMonitor} />
      </MemoryRouter>,
    );
    await user.click(screen.getByTestId("retry-run-btn"));
    expect(mockNavigate).toHaveBeenCalledWith("/run", {
      state: {
        prefill: {
          backend: "langgraph",
          profile: "full",
          description: "Build a todo API",
          complexity: "simple",
        },
        autoStart: true,
      },
    });
  });

  it("cancelled run has yellow outcome, not red", () => {
    const cancelledRun: RunInfo = { ...baseRun, status: "cancelled" };
    render(
      <MemoryRouter>
        <RunSummaryCard run={cancelledRun} monitor={baseMonitor} />
      </MemoryRouter>,
    );
    const outcome = screen.getByText("cancelled");
    expect(outcome).toHaveClass("yellow");
  });

  it("Edit & rerun navigates to /run with prefilled config", async () => {
    const user = userEvent.setup();
    const errorRun: RunInfo = {
      ...baseRun,
      status: "error",
      complexity: "complex",
    };
    render(
      <MemoryRouter>
        <RunSummaryCard run={errorRun} monitor={baseMonitor} />
      </MemoryRouter>,
    );
    await user.click(screen.getByTestId("edit-rerun-btn"));
    expect(mockNavigate).toHaveBeenCalledWith("/run", {
      state: {
        prefill: {
          backend: "langgraph",
          profile: "full",
          description: "Build a todo API",
          complexity: "complex",
        },
      },
    });
  });

  it("original failed run stays — retry creates new run (no mutation of passed run)", () => {
    const errorRun: RunInfo = { ...baseRun, status: "error", run_id: "orig-1" };
    render(
      <MemoryRouter>
        <RunSummaryCard run={errorRun} monitor={baseMonitor} />
      </MemoryRouter>,
    );
    // run_id should still be the original (not mutated)
    expect(screen.getByText(/Outcome/)).toBeInTheDocument();
    expect(errorRun.run_id).toBe("orig-1");
  });

  it("demo cancelled run shows no Retry buttons", () => {
    const demoCancelled: RunInfo = { ...baseRun, backend: "demo", status: "cancelled" };
    render(
      <MemoryRouter>
        <RunSummaryCard run={demoCancelled} monitor={baseMonitor} />
      </MemoryRouter>,
    );
    expect(screen.queryByTestId("retry-run-btn")).not.toBeInTheDocument();
    expect(screen.queryByTestId("edit-rerun-btn")).not.toBeInTheDocument();
  });
});
