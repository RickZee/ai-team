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

/** Time-of-day only for cards inside a day group (V-2). */
export function formatRunTimeOfDay(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
}

/** Newest runs first. */
export function sortRunsByDate(runs: RunInfo[]): RunInfo[] {
  return [...runs].sort((a, b) => {
    const ta = new Date(a.started_at).getTime();
    const tb = new Date(b.started_at).getTime();
    return (Number.isNaN(tb) ? 0 : tb) - (Number.isNaN(ta) ? 0 : ta);
  });
}

function dayHeaderLabel(date: Date): string {
  const today = new Date();
  const yesterday = new Date();
  yesterday.setDate(today.getDate() - 1);
  if (date.toDateString() === today.toDateString()) return "Today";
  if (date.toDateString() === yesterday.toDateString()) return "Yesterday";
  return date.toLocaleDateString(undefined, {
    weekday: "short",
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

/** Group runs by calendar day (newest day first). */
export function groupRunsByDay(runs: RunInfo[]): { label: string; runs: RunInfo[] }[] {
  const map = new Map<string, RunInfo[]>();
  for (const run of sortRunsByDate(runs)) {
    const d = new Date(run.started_at);
    const key = Number.isNaN(d.getTime()) ? "Unknown" : d.toDateString();
    if (!map.has(key)) map.set(key, []);
    map.get(key)!.push(run);
  }
  return [...map.entries()].map(([key, dayRuns]) => ({
    label: key === "Unknown" ? "Unknown" : dayHeaderLabel(new Date(key)),
    runs: dayRuns,
  }));
}
