import { describe, expect, it } from "vitest";
import { deriveCompareColumnVariant } from "../compareColumnState";
import { makeMonitor } from "../../test/fixtures/monitor";

describe("deriveCompareColumnVariant", () => {
  it("idle when status is idle", () => {
    expect(deriveCompareColumnVariant("idle", null, null, null).kind).toBe("idle");
  });

  it("terminal when complete with monitor even if monitor would show placeholders elsewhere", () => {
    const v = deriveCompareColumnVariant("complete", makeMonitor(), "r1", null);
    expect(v.kind).toBe("terminal");
  });

  it("starting when running without monitor", () => {
    expect(deriveCompareColumnVariant("running", null, "r1", null).kind).toBe("starting");
  });
});
