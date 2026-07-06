import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { EmptyState } from "../EmptyState";

describe("EmptyState", () => {
  it("renders title and optional hint", () => {
    render(<EmptyState title="Nothing here" hint="Try again later." testId="empty" />);
    expect(screen.getByTestId("empty")).toBeInTheDocument();
    expect(screen.getByText("Nothing here")).toBeInTheDocument();
    expect(screen.getByText("Try again later.")).toBeInTheDocument();
  });

  it("renders action slot", () => {
    render(
      <EmptyState
        title="No runs"
        action={<button type="button">Start</button>}
        testId="empty-action"
      />,
    );
    expect(screen.getByRole("button", { name: "Start" })).toBeInTheDocument();
  });

  it("omits hint when not provided", () => {
    render(<EmptyState title="Past tense only" testId="empty-no-hint" />);
    expect(screen.getByTestId("empty-no-hint").querySelector(".empty-state-hint")).toBeNull();
  });
});
