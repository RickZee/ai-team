import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { RunDetail } from "../RunDetail";
import { ApiError, getRun, getRuns } from "../../hooks/useApi";

vi.mock("../../hooks/useApi", () => ({
  ApiError: class ApiError extends Error {
    status: number;
    constructor(message: string, status: number) {
      super(message);
      this.status = status;
      this.name = "ApiError";
    }
  },
  getHealth: vi.fn().mockResolvedValue({ status: "ok" }),
  getRuns: vi.fn().mockResolvedValue({ runs: [] }),
  getRun: vi.fn(),
  getProjectTests: vi.fn().mockResolvedValue({ total: 0, passed: 0, failed: 0, source: "empty" }),
  postCancel: vi.fn(),
}));

vi.mock("../../hooks/useWebSocket", () => ({
  useMonitorWebSocket: vi.fn(() => ({
    monitor: null,
    runStatus: null,
    hitlPayload: null,
    errorMessage: null,
    clearHitl: vi.fn(),
  })),
}));

describe("RunDetail — V-4 not found", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows error state for 404 without infinite spinner", async () => {
    vi.mocked(getRun).mockRejectedValue(new ApiError("Run not found", 404));

    render(
      <MemoryRouter initialEntries={["/runs/missing-run"]}>
        <Routes>
          <Route path="/runs/:runId" element={<RunDetail />} />
        </Routes>
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("run-not-found")).toBeInTheDocument();
    });
    expect(screen.getByTestId("back-to-runs")).toHaveAttribute("href", "/");
    expect(screen.queryByText(/Loading run/i)).not.toBeInTheDocument();
  });
});
