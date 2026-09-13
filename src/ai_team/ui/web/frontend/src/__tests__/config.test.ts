import { afterEach, describe, expect, it, vi } from "vitest";

describe("config", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.resetModules();
  });

  it("getApiBase uses VITE_API_BASE when set", async () => {
    vi.stubEnv("VITE_API_BASE", "http://test.example/api");
    const { getApiBase } = await import("../config");
    expect(getApiBase()).toBe("http://test.example/api");
  });

  it("getApiBase falls back to same-origin /api", async () => {
    vi.stubGlobal("window", {
      location: { origin: "http://127.0.0.1:59999", protocol: "http:", host: "127.0.0.1:59999" },
    });
    const { getApiBase } = await import("../config");
    expect(getApiBase()).toBe("http://127.0.0.1:59999/api");
  });

  it("getWsBase uses wss on https pages", async () => {
    vi.stubGlobal("window", {
      location: { origin: "https://app.example", protocol: "https:", host: "app.example" },
    });
    const { getWsBase } = await import("../config");
    expect(getWsBase()).toBe("wss://app.example");
  });

  it("authHeaders attaches the token when configured", async () => {
    vi.stubEnv("VITE_AI_TEAM_WEB_TOKEN", "sekrit");
    const { authHeaders } = await import("../config");
    const headers = new Headers(authHeaders());
    expect(headers.get("X-AI-Team-Token")).toBe("sekrit");
  });

  it("authHeaders omits the token when unset", async () => {
    vi.stubEnv("VITE_AI_TEAM_WEB_TOKEN", "");
    const { authHeaders } = await import("../config");
    const headers = new Headers(authHeaders());
    expect(headers.get("X-AI-Team-Token")).toBeNull();
  });
});
