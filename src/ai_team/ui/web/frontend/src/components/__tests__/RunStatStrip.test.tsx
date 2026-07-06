import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { RunStatStrip } from "../RunStatStrip";
import { makeMonitor } from "../../test/fixtures/monitor";

describe("RunStatStrip", () => {
  it("shows status, phase, elapsed, cost, and tests", () => {
    const monitor = makeMonitor({
      phase: "testing",
      elapsed: "4m 10s",
      cost_usd: 0.1234,
      metrics: {
        tasks_completed: 1,
        tasks_failed: 0,
        retries: 0,
        files_generated: 0,
        guardrails_passed: 0,
        guardrails_failed: 0,
        guardrails_warned: 0,
        tests_passed: 5,
        tests_failed: 2,
      },
    });

    render(<RunStatStrip status="running" monitor={monitor} />);

    expect(screen.getByTestId("run-stat-strip")).toBeInTheDocument();
    expect(screen.getByText("running")).toBeInTheDocument();
    expect(screen.getByText("testing")).toBeInTheDocument();
    expect(screen.getByTestId("stat-elapsed")).toHaveTextContent("4m 10s");
    expect(screen.getByTestId("stat-cost")).toHaveTextContent("$0.1234");
    expect(screen.getByTestId("stat-tests")).toHaveTextContent("5✓ / 2✗");
  });

  it("omits cost and tests when not available", () => {
    const monitor = makeMonitor({
      cost_usd: undefined,
      metrics: {
        tasks_completed: 0,
        tasks_failed: 0,
        retries: 0,
        files_generated: 0,
        guardrails_passed: 0,
        guardrails_failed: 0,
        guardrails_warned: 0,
        tests_passed: 0,
        tests_failed: 0,
      },
    });

    render(<RunStatStrip status="connecting" monitor={monitor} />);

    expect(screen.queryByTestId("stat-cost")).not.toBeInTheDocument();
    expect(screen.queryByTestId("stat-tests")).not.toBeInTheDocument();
  });
});
