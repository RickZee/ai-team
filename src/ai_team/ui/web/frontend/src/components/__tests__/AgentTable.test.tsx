import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { AgentTable } from "../AgentTable";

describe("AgentTable", () => {
  it("shows live empty state", () => {
    render(<AgentTable agents={{}} />);
    expect(screen.getByTestId("agent-table-empty")).toHaveTextContent(
      "Waiting for agents to join the run",
    );
  });

  it("shows terminal empty state", () => {
    render(<AgentTable agents={{}} terminal />);
    expect(screen.getByTestId("agent-table-empty")).toHaveTextContent(
      "No agent activity recorded for this run",
    );
  });

  it("downgrades working to done on terminal runs", () => {
    render(
      <AgentTable
        terminal
        agents={{
          backend_developer: {
            role: "backend_developer",
            status: "working",
            current_task: "Stale task",
            tasks_completed: 1,
            model: "test",
          },
        }}
      />,
    );
    expect(screen.getByText("● DONE")).toBeInTheDocument();
    expect(screen.queryByText("● ACTIVE")).not.toBeInTheDocument();
  });
});
