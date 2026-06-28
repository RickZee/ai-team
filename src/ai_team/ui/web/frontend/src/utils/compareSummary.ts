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
    const vn = Number(v);
    const bn = Number(bestVal);
    let better: boolean;
    if (!Number.isNaN(vn) && !Number.isNaN(bn)) {
      better = prefer === "min" ? vn < bn : vn > bn;
    } else {
      const cmp = String(v).localeCompare(String(bestVal), undefined, { numeric: true });
      better = prefer === "min" ? cmp < 0 : cmp > 0;
    }
    if (better) {
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

export interface VerdictMetric {
  label: string;
  prefer: "min" | "max";
  numeric: (m: MonitorState) => number;
}

/** Build a one-line auto verdict from summary rows and metrics. */
export function buildCompareVerdict(
  rows: { key: string; label: string; m: MonitorState; failed?: boolean }[],
  metrics: VerdictMetric[],
): string {
  const active = rows.filter((r) => !r.failed);
  if (active.length === 0) return "";
  const parts: string[] = [];
  for (const metric of metrics) {
    const bestKey = bestColumnKey(active, metric.numeric, metric.prefer);
    if (!bestKey) continue;
    const winner = active.find((r) => r.key === bestKey);
    if (winner) {
      const direction = metric.prefer === "min" ? "lowest" : "highest";
      parts.push(`${winner.label}: ${direction} ${metric.label.toLowerCase()}`);
    }
  }
  return parts.join("; ");
}

export function directionHint(prefer: "min" | "max" | null): string {
  if (prefer === "min") return "▼ lower is better";
  if (prefer === "max") return "▲ higher is better";
  return "";
}
