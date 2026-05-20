import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { HumanReviewPanel } from "../HumanReviewPanel";

vi.mock("../../hooks/useApi", () => ({
  postResume: vi.fn(),
}));

import { postResume } from "../../hooks/useApi";

describe("HumanReviewPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders payload and disables submit until feedback entered", () => {
    render(
      <HumanReviewPanel runId="abc" payload={{ phase: "awaiting_human" }} />,
    );
    expect(screen.getByTestId("hitl-panel")).toBeInTheDocument();
    expect(screen.getByText(/awaiting_human/)).toBeInTheDocument();
    expect(screen.getByTestId("hitl-submit")).toBeDisabled();
  });

  it("calls postResume and onResumed on submit", async () => {
    const user = userEvent.setup();
    const onResumed = vi.fn();
    vi.mocked(postResume).mockResolvedValue({ run_id: "abc", status: "complete" });

    render(
      <HumanReviewPanel
        runId="abc"
        payload={null}
        onResumed={onResumed}
      />,
    );

    await user.type(screen.getByTestId("hitl-feedback"), "Approved");
    await user.click(screen.getByTestId("hitl-submit"));

    await waitFor(() => {
      expect(postResume).toHaveBeenCalledWith("abc", "Approved");
      expect(onResumed).toHaveBeenCalled();
    });
  });
});
