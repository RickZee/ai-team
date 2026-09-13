/** Same-origin API/WS bases for dev proxy, prod, and E2E. */

const envApi = import.meta.env.VITE_API_BASE as string | undefined;
const envWs = import.meta.env.VITE_WS_BASE as string | undefined;

function originBase(): string {
  if (typeof window !== "undefined" && window.location?.origin) {
    return window.location.origin;
  }
  return "";
}

export function getApiBase(): string {
  if (envApi) return envApi.replace(/\/$/, "");
  const origin = originBase();
  return origin ? `${origin}/api` : "/api";
}

export function getWebToken(): string {
  return ((import.meta.env.VITE_AI_TEAM_WEB_TOKEN as string | undefined) || "").trim();
}

export function authHeaders(extra?: HeadersInit): HeadersInit {
  const token = getWebToken();
  const headers = new Headers(extra);
  if (token) headers.set("X-AI-Team-Token", token);
  return headers;
}

export function withTokenQuery(url: string): string {
  const token = getWebToken();
  if (!token) return url;
  const join = url.includes("?") ? "&" : "?";
  return `${url}${join}token=${encodeURIComponent(token)}`;
}

export function getWsBase(): string {
  if (envWs) return envWs.replace(/\/$/, "");
  if (typeof window !== "undefined" && window.location) {
    const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
    return `${proto}//${window.location.host}`;
  }
  return "ws://localhost:8421";
}
