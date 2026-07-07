import { describe, expect, it } from "vitest";
import { formatLogMessage, formatLogTime } from "../formatLogMessage";

describe("formatLogMessage", () => {
  it("maps retry_development → phase development", () => {
    expect(formatLogMessage("retry_development → phase development")).toBe(
      "retry → development",
    );
  });

  it("maps interrupt payloads", () => {
    expect(formatLogMessage("__interrupt__: (Interrupt(value='review')")).toBe(
      "⏸ paused for human review",
    );
  });

  it("passes through unknown messages", () => {
    expect(formatLogMessage("custom backend event")).toBe("custom backend event");
  });
});

describe("formatLogTime", () => {
  it("returns HH:MM without seconds", () => {
    const t = formatLogTime("2026-06-01T13:25:42Z");
    expect(t).toMatch(/^\d{1,2}:\d{2}$/);
  });
});
