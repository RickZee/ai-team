const API_BASE = `http://${window.location.hostname}:8421/api`;

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, init);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export function getHealth() {
  return fetchJson<{ status: string }>("/health");
}

export function getProfiles() {
  return fetchJson<Record<string, { agents: string[]; phases: string[] }>>("/profiles");
}

export function getBackends() {
  return fetchJson<{ backends: { name: string; label: string; streaming: boolean }[] }>("/backends");
}

export function postEstimate(complexity: string) {
  return fetchJson<{
    complexity: string;
    rows: { role: string; model_id: string; input_tokens: number; output_tokens: number; cost_usd: number }[];
    total_usd: number;
    within_budget: boolean;
  }>("/estimate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ complexity }),
  });
}

export function getRuns() {
  return fetchJson<{ runs: { run_id: string; status: string; backend: string; description: string; started_at: string }[] }>("/runs");
}

export function getRun(runId: string) {
  return fetchJson<Record<string, unknown>>(`/runs/${runId}`);
}

export function postDemo() {
  return fetchJson<{ run_id: string }>("/demo", { method: "POST" });
}
