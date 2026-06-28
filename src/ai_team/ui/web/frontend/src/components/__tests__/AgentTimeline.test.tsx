import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { AgentTimeline } from "../AgentTimeline";
import type { MonitorState } from "../../types";

const monitor: MonitorState = {
  phase: "development",
  elapsed: "2m",
  agents: {
    backend_developer: {
      role: "backend_developer",
      status: "working",
      current_task: "Implementing API",
      tasks_completed: 1,
      model: "test",
    },
    qa_engineer: {
      role: "qa_engineer",
      status: "done",
      current_task: "",
      tasks_completed: 1,
      model: "test",
    },
  },
  metrics: {
    tasks_completed: 2,
    tasks_failed: 0,
    retries: 1,
    files_generated: 2,
    guardrails_passed: 1,
    guardrails_failed: 0,
    guardrails_warned: 0,
    tests_passed: 0,
    tests_failed: 0,
  },
  log: [],
  guardrail_events: [],
};

describe("AgentTimeline", () => {
  it("renders agents and self-correct badge", () => {
    render(<AgentTimeline monitor={monitor} />);
    expect(screen.getByTestId("agent-timeline")).toBeInTheDocument();
    expect(screen.getByTestId("timeline-agent-backend_developer")).toBeInTheDocument();
    expect(screen.getByTestId("self-correct-badge")).toHaveTextContent("Self-corrected ×1");
    expect(screen.getByText(/Current owner/i)).toBeInTheDocument();
  });

  it("toggles agent table", async () => {
    const user = userEvent.setup();
    const onToggle = vi.fn();
    render(<AgentTimeline monitor={monitor} showTable={false} onToggleTable={onToggle} />);
    await user.click(screen.getByRole("button", { name: /Show table/i }));
    expect(onToggle).toHaveBeenCalled();
  });
});
