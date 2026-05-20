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

export function getWsBase(): string {
  if (envWs) return envWs.replace(/\/$/, "");
  if (typeof window !== "undefined" && window.location) {
    const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
    return `${proto}//${window.location.host}`;
  }
  return "ws://localhost:8421";
}
