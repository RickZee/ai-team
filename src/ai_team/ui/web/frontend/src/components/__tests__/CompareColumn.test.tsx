import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { CompareColumn } from "../CompareColumn";
import { makeMonitor } from "../../test/fixtures/monitor";

describe("CompareColumn", () => {
  it("shows not-started empty state when idle", () => {
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
    expect(screen.getByText(/Run a comparison/)).toBeInTheDocument();
  });

  it("renders backend title with tooltip attribute", () => {
    render(
      <MemoryRouter>
        <CompareColumn
          title="Claude Agent SDK"
          titleClass="claude-title"
          monitor={null}
          status="idle"
          runId={null}
          errorMessage={null}
          testIdPrefix="compare-claude"
        />
      </MemoryRouter>,
    );
    expect(screen.getByTitle("Claude Agent SDK")).toBeInTheDocument();
  });

  it("shows terminal guardrails empty copy", () => {
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
    expect(screen.getByTestId("guardrails-empty")).toHaveTextContent(
      "No guardrail events recorded for this run",
    );
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
  });
});
