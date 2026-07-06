import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { RunConfigBackendField, RunConfigForm } from "../RunConfigForm";
import { sampleEstimate } from "../../test/fixtures/monitor";

describe("RunConfigForm", () => {
  const defaults = {
    profile: "full",
    setProfile: vi.fn(),
    complexity: "medium",
    setComplexity: vi.fn(),
    description: "",
    setDescription: vi.fn(),
    profileNames: ["full", "minimal"],
    descriptionTestId: "test-description",
    profileTestId: "test-profile",
    disabledHintTestId: "test-disabled-hint",
    estimateHelperTestId: "test-estimate-helper",
    disabledHintText: "Description required.",
    actions: <button type="button" className="btn-primary" data-testid="primary-action">Submit</button>,
  };

  it("renders profile, complexity, description, and helper copy", () => {
    render(<RunConfigForm {...defaults} />);
    expect(screen.getByTestId("test-profile")).toBeInTheDocument();
    expect(screen.getByTestId("test-description")).toBeInTheDocument();
    expect(screen.getByTestId("test-estimate-helper")).toHaveTextContent(
      /complexity tier and team profile/,
    );
    expect(screen.getByTestId("complexity-helper")).toBeInTheDocument();
  });

  it("shows disabled hint when requested", () => {
    render(<RunConfigForm {...defaults} showDisabledHint />);
    expect(screen.getByTestId("test-disabled-hint")).toHaveTextContent("Description required.");
  });

  it("calls onEstimate from link button", async () => {
    const user = userEvent.setup();
    const onEstimate = vi.fn();
    render(
      <RunConfigForm
        {...defaults}
        onEstimate={onEstimate}
        estimateButtonTestId="test-estimate"
      />,
    );
    await user.click(screen.getByTestId("test-estimate"));
    expect(onEstimate).toHaveBeenCalledOnce();
  });

  it("renders inline estimate table when enabled", () => {
    render(
      <RunConfigForm
        {...defaults}
        estimate={sampleEstimate}
        inlineEstimate
      />,
    );
    expect(screen.getByTestId("estimate-inline")).toBeInTheDocument();
    expect(screen.getByTestId("estimate-table")).toBeInTheDocument();
  });

  it("has exactly one primary action in the actions slot", () => {
    render(<RunConfigForm {...defaults} />);
    expect(screen.getAllByRole("button", { name: "Submit" })).toHaveLength(1);
    expect(screen.getByTestId("primary-action")).toHaveClass("btn-primary");
  });
});

describe("RunConfigBackendField", () => {
  it("renders backend options and key hint for unconfigured backend", () => {
    render(
      <RunConfigBackendField
        backend="crewai"
        setBackend={vi.fn()}
        backendOptions={[
          { name: "langgraph", label: "LangGraph", streaming: true, required_key: "OPENROUTER_API_KEY" },
          { name: "crewai", label: "CrewAI", streaming: false, configured: false, required_key: "OPENROUTER_API_KEY" },
        ]}
      />,
    );
    expect(screen.getByTestId("run-backend")).toBeInTheDocument();
    expect(screen.getByTestId("backend-key-hint")).toHaveTextContent("OPENROUTER_API_KEY");
    expect(screen.getByText(/not configured on server/)).toBeInTheDocument();
  });
});
