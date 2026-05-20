import { describe, expect, it } from "vitest";
import { formatRunDate, sortRunsByDate } from "../formatRun";
import type { RunInfo } from "../../types";

describe("formatRunDate", () => {
  it("returns em dash for empty input", () => {
    expect(formatRunDate(null)).toBe("—");
    expect(formatRunDate(undefined)).toBe("—");
  });

  it("formats valid ISO timestamps", () => {
    const formatted = formatRunDate("2026-05-20T15:30:00.000Z");
    expect(formatted).not.toBe("—");
    expect(formatted.length).toBeGreaterThan(5);
  });

  it("returns raw string when date is invalid", () => {
    expect(formatRunDate("not-a-date")).toBe("not-a-date");
  });
});

describe("sortRunsByDate", () => {
  const mk = (id: string, started_at: string): RunInfo => ({
    run_id: id,
    backend: "demo",
    profile: "full",
    description: `Assignment ${id}`,
    status: "complete",
    started_at,
    finished_at: null,
    error: null,
  });

  it("orders newest started_at first", () => {
    const sorted = sortRunsByDate([
      mk("old", "2026-01-01T10:00:00"),
      mk("new", "2026-05-20T10:00:00"),
      mk("mid", "2026-03-01T10:00:00"),
    ]);
    expect(sorted.map((r) => r.run_id)).toEqual(["new", "mid", "old"]);
  });

  it("does not mutate the input array", () => {
    const input = [mk("a", "2026-01-01"), mk("b", "2026-02-01")];
    const copy = [...input];
    sortRunsByDate(input);
    expect(input).toEqual(copy);
  });
});
