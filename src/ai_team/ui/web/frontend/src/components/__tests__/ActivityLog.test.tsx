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

const longEntries: LogEntry[] = Array.from({ length: 50 }, (_, i) => ({
  timestamp: `2026-06-01T10:${String(i % 60).padStart(2, "0")}:00Z`,
  agent: "langgraph",
  message: `This is a very long log message number ${i} that should not wrap on wide panels`,
  level: "info" as const,
}));

describe("ActivityLog", () => {
  it("filters by level toggles", async () => {
    const user = userEvent.setup();
    render(<ActivityLog entries={entries} ariaLive="polite" />);
    await user.click(screen.getByTestId("log-level-error"));
    expect(screen.queryByText("Test failed")).not.toBeInTheDocument();
    expect(screen.getByText("Starting intake")).toBeInTheDocument();
  });

  it("renders interrupt messages human-readably with raw in title", () => {
    render(
      <ActivityLog
        entries={[
          {
            timestamp: "2026-06-01T13:25:00Z",
            agent: "manager",
            message: "__interrupt__: (Interrupt(value='review')",
            level: "info",
          },
        ]}
      />,
    );
    expect(screen.getByText("⏸ paused for human review")).toBeInTheDocument();
  });

  it("keeps long entries on one line via ellipsis layout", () => {
    const { container } = render(<ActivityLog entries={longEntries} compact />);
    const lines = container.querySelectorAll(".log-line");
    expect(lines.length).toBe(50);
    lines.forEach((line) => {
      expect(line.querySelector(".log-msg")).toBeTruthy();
    });
    expect(container.querySelector(".activity-log")).toBeTruthy();
  });
});
