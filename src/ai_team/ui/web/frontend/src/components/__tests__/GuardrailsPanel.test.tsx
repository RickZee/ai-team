import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { GuardrailsPanel } from "../GuardrailsPanel";
import type { GuardrailEvent } from "../../types";

const event: GuardrailEvent = {
  timestamp: "2026-06-01T10:00:00Z",
  category: "security",
  name: "path_traversal",
  status: "fail",
  message: "Blocked ../ escape",
};

describe("GuardrailsPanel", () => {
  it("shows live empty state with hint", () => {
    render(<GuardrailsPanel events={[]} />);
    expect(screen.getByTestId("guardrails-empty")).toHaveTextContent("No guardrail checks yet");
    expect(screen.getByText(/Checks appear as agents run/)).toBeInTheDocument();
  });

  it("shows terminal empty state without yet wording", () => {
    render(<GuardrailsPanel events={[]} terminal />);
    expect(screen.getByTestId("guardrails-empty")).toHaveTextContent(
      "No guardrail events recorded for this run",
    );
    expect(screen.queryByText(/yet/)).not.toBeInTheDocument();
  });

  it("renders guardrail events", () => {
    render(<GuardrailsPanel events={[event]} />);
    expect(screen.getByText("path_traversal")).toBeInTheDocument();
    expect(screen.getByText(/Blocked/)).toBeInTheDocument();
  });
});
