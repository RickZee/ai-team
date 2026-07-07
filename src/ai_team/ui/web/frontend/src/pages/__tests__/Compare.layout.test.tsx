import { render } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { Compare } from "../Compare";

vi.mock("../../hooks/useCatalog", () => ({
  useCatalog: vi.fn(() => ({
    backends: [],
    profiles: {},
    profileNames: ["full"],
    loading: false,
    error: null,
  })),
}));

vi.mock("../../hooks/useApi", () => ({
  postEstimate: vi.fn(),
  postDemo: vi.fn(),
  getComparison: vi.fn(),
  getRun: vi.fn(),
}));

vi.mock("../../hooks/useWebSocket", () => ({
  useRunWebSocket: vi.fn(() => ({
    monitor: null,
    events: [],
    runId: null,
    projectId: null,
    status: "idle",
    errorMessage: null,
    hitlPayload: null,
    startRun: vi.fn(),
    disconnect: vi.fn(),
  })),
  useMonitorWebSocket: vi.fn(() => ({
    monitor: null,
    runStatus: null,
    hitlPayload: null,
    errorMessage: null,
    clearHitl: vi.fn(),
  })),
}));

import { useRunWebSocket } from "../../hooks/useWebSocket";

describe("Compare — responsive layout", () => {
  const widths = [1024, 1280, 1920];

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(useRunWebSocket).mockReturnValue({
      monitor: null,
      events: [],
      runId: null,
      projectId: null,
      status: "idle",
      errorMessage: null,
      hitlPayload: null,
      startRun: vi.fn(),
      disconnect: vi.fn(),
    });
  });

  it("uses auto-fit compare grid classes", () => {
    const { container } = render(
      <MemoryRouter>
        <Compare />
      </MemoryRouter>,
    );
    const grid = container.querySelector(".compare-grid.compare-grid-3");
    expect(grid).toBeTruthy();
    expect(container.querySelector(".compare-col")).toBeTruthy();
  });

  it.each(widths)("does not overflow the page width at %ipx", (width) => {
    Object.defineProperty(window, "innerWidth", {
      configurable: true,
      writable: true,
      value: width,
    });

    const host = document.createElement("div");
    host.style.width = `${width}px`;
    host.style.maxWidth = `${width}px`;
    host.style.overflow = "hidden";
    document.body.appendChild(host);

    try {
      render(
        <MemoryRouter>
          <Compare />
        </MemoryRouter>,
        { container: host },
      );
      expect(host.scrollWidth).toBeLessThanOrEqual(width + 1);
    } finally {
      document.body.removeChild(host);
    }
  });
});
