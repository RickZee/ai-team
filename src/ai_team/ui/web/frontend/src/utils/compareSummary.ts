import type { MonitorState } from "../types";

type MetricExtractor = (m: MonitorState) => number | string;

/** Lower is better for elapsed; higher is better for counts. */
export function bestColumnKey(
  rows: { key: string; m: MonitorState }[],
  extract: MetricExtractor,
  prefer: "min" | "max",
): string | null {
  if (rows.length === 0) return null;
  let best = rows[0];
  let bestVal = extract(best.m);
  for (const r of rows.slice(1)) {
    const v = extract(r.m);
    const cmp =
      prefer === "min"
        ? String(v).localeCompare(String(bestVal), undefined, { numeric: true })
        : String(bestVal).localeCompare(String(v), undefined, { numeric: true });
    if (prefer === "min" ? cmp > 0 : cmp < 0) {
      best = r;
      bestVal = v;
    }
  }
  return best.key;
}

export function parseElapsedSeconds(elapsed: string): number {
  const m = elapsed.match(/(\d+)m/);
  const s = elapsed.match(/(\d+)s/);
  return (m ? parseInt(m[1], 10) * 60 : 0) + (s ? parseInt(s[1], 10) : 0);
}
