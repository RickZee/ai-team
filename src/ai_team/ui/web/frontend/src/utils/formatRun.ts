import type { RunInfo } from "../types";

/** Format ISO timestamp for run list and detail headers. */
export function formatRunDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/** Newest runs first. */
export function sortRunsByDate(runs: RunInfo[]): RunInfo[] {
  return [...runs].sort((a, b) => {
    const ta = new Date(a.started_at).getTime();
    const tb = new Date(b.started_at).getTime();
    return (Number.isNaN(tb) ? 0 : tb) - (Number.isNaN(ta) ? 0 : ta);
  });
}
