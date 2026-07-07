import { useCallback, useEffect, useState } from "react";
import { getRegistryRuns, getRuns } from "./useApi";
import type { RegistryRun, RunInfo } from "../types";
import { formatRunDate, sortRunsByDate } from "../utils/formatRun";

export type UnifiedRunSource = "session" | "disk" | "both";

export interface UnifiedRun {
  run_id: string;
  backend: string;
  profile: string;
  description: string;
  status: string;
  started_at: string;
  finished_at: string | null;
  source: UnifiedRunSource;
  has_disk_artifacts: boolean;
}

function registryToUnified(r: RegistryRun): UnifiedRun {
  return {
    run_id: r.run_id,
    backend: r.backend ?? "unknown",
    profile: r.team_profile ?? "—",
    description: r.description ?? "",
    status: r.status ?? "disk",
    started_at: r.started_at ?? r.completed_at ?? "",
    finished_at: r.completed_at ?? null,
    source: "disk",
    has_disk_artifacts: true,
  };
}

function sessionToUnified(r: RunInfo): UnifiedRun {
  return {
    run_id: r.run_id,
    backend: r.backend,
    profile: r.profile,
    description: r.description,
    status: r.status,
    started_at: r.started_at,
    finished_at: r.finished_at,
    source: "session",
    has_disk_artifacts: r.backend !== "demo",
  };
}

/** Merge in-memory session runs with disk registry runs for pickers. */
export function useUnifiedRuns() {
  const [runs, setRuns] = useState<UnifiedRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const [session, registry] = await Promise.all([
        getRuns().catch(() => ({ runs: [] as RunInfo[] })),
        getRegistryRuns().catch(() => ({ runs: [] as RegistryRun[] })),
      ]);
      const byId = new Map<string, UnifiedRun>();
      for (const r of registry.runs) {
        byId.set(r.run_id, registryToUnified(r));
      }
      for (const r of sortRunsByDate(session.runs as RunInfo[])) {
        const existing = byId.get(r.run_id);
        if (existing) {
          byId.set(r.run_id, {
            ...existing,
            ...sessionToUnified(r),
            source: "both",
            has_disk_artifacts: true,
          });
        } else {
          byId.set(r.run_id, sessionToUnified(r));
        }
      }
      const merged = [...byId.values()].sort((a, b) => {
        const ta = new Date(a.started_at).getTime();
        const tb = new Date(b.started_at).getTime();
        return (Number.isNaN(tb) ? 0 : tb) - (Number.isNaN(ta) ? 0 : ta);
      });
      setRuns(merged);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load runs");
      setRuns([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return { runs, loading, error, refresh };
}

/** Label for run select options (Phase 1 P1-5). */
export function formatUnifiedRunLabel(r: UnifiedRun): string {
  const date = formatRunDate(r.started_at);
  const title = r.description?.trim() || r.run_id;
  const shortTitle = title.length > 48 ? `${title.slice(0, 48)}…` : title;
  return `${date} · ${r.backend} · ${shortTitle}`;
}

/** Full label for option tooltip. */
export function formatUnifiedRunTooltip(r: UnifiedRun): string {
  return r.description?.trim() ? `${r.run_id} — ${r.description}` : r.run_id;
}
