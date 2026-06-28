import { getApiBase } from "../config";

const API_BASE = getApiBase();

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, init);
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(text || `API error: ${res.status}`);
  }
  return res.json();
}

export function getHealth() {
  return fetchJson<{ status: string; timestamp?: string }>("/health");
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
    rows: {
      role: string;
      model_id: string;
      input_tokens: number;
      output_tokens: number;
      cost_usd: number;
    }[];
    total_usd: number;
    within_budget: boolean;
  }>("/estimate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ complexity }),
  });
}

export function getRuns() {
  return fetchJson<{
    runs: {
      run_id: string;
      status: string;
      backend: string;
      profile: string;
      description: string;
      started_at: string;
      finished_at?: string | null;
      error?: string | null;
    }[];
  }>("/runs");
}

export function getRun(runId: string) {
  return fetchJson<{
    run_id: string;
    status: string;
    backend: string;
    profile: string;
    description: string;
    monitor: import("../types").MonitorState | null;
    hitl_payload?: Record<string, unknown> | null;
    thread_id?: string | null;
  }>(`/runs/${runId}`);
}

export function postDemo() {
  return fetchJson<{ run_id: string }>("/demo", { method: "POST" });
}

export function getRegistryRuns() {
  return fetchJson<{ runs: import("../types").RegistryRun[] }>("/registry/runs");
}

export function getProjectTree(projectId: string, root: import("../types").ArtifactRoot) {
  const q = new URLSearchParams({ root });
  return fetchJson<{
    project_id: string;
    root: import("../types").ArtifactRoot;
    tree: import("../types").ArtifactTreeNode[];
  }>(`/projects/${encodeURIComponent(projectId)}/tree?${q}`);
}

export function getProjectFile(
  projectId: string,
  path: string,
  root: import("../types").ArtifactRoot,
) {
  const q = new URLSearchParams({ path, root });
  return fetchJson<import("../types").ArtifactFileContent>(
    `/projects/${encodeURIComponent(projectId)}/file?${q}`,
  );
}

export function getProjectTests(projectId: string) {
  return fetchJson<import("../types").TestsPanelData>(
    `/projects/${encodeURIComponent(projectId)}/tests`,
  );
}

export function getProjectArchitecture(projectId: string) {
  return fetchJson<import("../types").ArchitecturePanelData>(
    `/projects/${encodeURIComponent(projectId)}/architecture`,
  );
}

export function projectDownloadZipUrl(projectId: string) {
  return `${API_BASE}/projects/${encodeURIComponent(projectId)}/download.zip`;
}

export function postResume(runId: string, feedback: string) {
  return fetchJson<{ run_id: string; status: string }>(`/runs/${runId}/resume`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ feedback }),
  });
}

export function postCancel(runId: string) {
  return fetchJson<{ run_id: string; status: string }>(`/runs/${runId}/cancel`, {
    method: "POST",
  });
}
