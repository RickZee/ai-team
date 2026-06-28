import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { ActivityLog } from "../ActivityLog";
import type { LogEntry } from "../../types";

const entries: LogEntry[] = [
  { timestamp: "2026-06-01T10:00:00Z", agent: "manager", message: "Starting intake", level: "info" },
  { timestamp: "2026-06-01T10:01:00Z", agent: "qa", message: "Test failed", level: "error" },
  { timestamp: "2026-06-01T10:02:00Z", agent: "qa", message: "Retry succeeded", level: "success" },
];

describe("ActivityLog", () => {
  it("filters by level toggles", async () => {
    const user = userEvent.setup();
    render(<ActivityLog entries={entries} ariaLive="polite" />);
    await user.click(screen.getByTestId("log-level-error"));
    expect(screen.queryByText("Test failed")).not.toBeInTheDocument();
    expect(screen.getByText("Starting intake")).toBeInTheDocument();
  });

  it("filters by text search", async () => {
    const user = userEvent.setup();
    render(<ActivityLog entries={entries} ariaLive="polite" />);
    await user.type(screen.getByTestId("log-search"), "Retry");
    expect(screen.getByText("Retry succeeded")).toBeInTheDocument();
    expect(screen.queryByText("Starting intake")).not.toBeInTheDocument();
  });

  it("resets filters when remounted for a different run", async () => {
    const user = userEvent.setup();
    const { rerender } = render(
      <ActivityLog entries={entries} ariaLive="polite" key="run-a" />,
    );
    await user.click(screen.getByTestId("log-level-info"));
    rerender(<ActivityLog entries={entries} ariaLive="polite" key="run-b" />);
    expect(screen.getByText("Starting intake")).toBeInTheDocument();
  });
});
