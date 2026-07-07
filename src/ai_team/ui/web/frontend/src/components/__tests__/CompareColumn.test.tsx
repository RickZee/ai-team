import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { CompareColumn } from "../CompareColumn";
import { makeMonitor } from "../../test/fixtures/monitor";

describe("CompareColumn", () => {
  it("shows not-started empty state when idle with no footer", () => {
    render(
      <MemoryRouter>
        <CompareColumn
          title="LangGraph"
          titleClass="langgraph-title"
          monitor={null}
          status="idle"
          runId={null}
          errorMessage={null}
          testIdPrefix="compare-langgraph"
        />
      </MemoryRouter>,
    );
    expect(screen.getByTestId("compare-langgraph-empty")).toHaveTextContent("Not started");
    expect(screen.queryByTestId("compare-langgraph-open-run")).not.toBeInTheDocument();
    expect(screen.queryByTestId("compare-langgraph-complete")).not.toBeInTheDocument();
  });

  it("terminal reattach shows result card without contradictory placeholders", () => {
    render(
      <MemoryRouter>
        <CompareColumn
          title="CrewAI"
          titleClass="crewai-title"
          monitor={makeMonitor({ guardrail_events: [] })}
          status="complete"
          runId="run-1"
          errorMessage={null}
          testIdPrefix="compare-crewai"
        />
      </MemoryRouter>,
    );
    expect(screen.getByTestId("compare-crewai-terminal")).toBeInTheDocument();
    expect(screen.getByTestId("compare-crewai-open-run")).toHaveTextContent("Open run");
    expect(screen.queryByText("Not started")).not.toBeInTheDocument();
    expect(screen.queryByText(/Waiting for agents/i)).not.toBeInTheDocument();
  });

  it("shows error block with reason", () => {
    render(
      <MemoryRouter>
        <CompareColumn
          title="CrewAI"
          titleClass="crewai-title"
          monitor={null}
          status="error"
          runId="run-err"
          errorMessage="Model timeout"
          testIdPrefix="compare-crewai"
        />
      </MemoryRouter>,
    );
    expect(screen.getByTestId("compare-crewai-error-reason")).toHaveTextContent("Model timeout");
    expect(screen.queryByText("Not started")).not.toBeInTheDocument();
  });
});
