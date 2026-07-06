import type { MonitorState } from "../types";

interface RunStatStripProps {
  status: string;
  monitor: MonitorState;
}

/** Compact above-the-fold stats for the dashboard sticky header (Phase 2 U-2). */
export function RunStatStrip({ status, monitor }: RunStatStripProps) {
  const m = monitor.metrics;
  const testsTotal = m.tests_passed + m.tests_failed;
  const testsLabel =
    testsTotal > 0
      ? `${m.tests_passed}✓${m.tests_failed > 0 ? ` / ${m.tests_failed}✗` : ""}`
      : null;

  return (
    <div className="run-stat-strip" data-testid="run-stat-strip">
      <span className={`status-chip status-${status}`}>
        {status === "cancelling" ? "Cancelling…" : status}
      </span>
      <span className="run-stat-sep" aria-hidden>
        ·
      </span>
      <span className="run-stat-item" title="Phase">
        {monitor.phase}
      </span>
      <span className="run-stat-sep" aria-hidden>
        ·
      </span>
      <span className="run-stat-item" title="Elapsed" data-testid="stat-elapsed">
        {monitor.elapsed}
      </span>
      {monitor.cost_usd != null && (
        <>
          <span className="run-stat-sep" aria-hidden>
            ·
          </span>
          <span className="run-stat-item" title="Cost" data-testid="stat-cost">
            ${monitor.cost_usd.toFixed(4)}
          </span>
        </>
      )}
      {testsLabel && (
        <>
          <span className="run-stat-sep" aria-hidden>
            ·
          </span>
          <span className="run-stat-item" title="Tests" data-testid="stat-tests">
            {testsLabel}
          </span>
        </>
      )}
    </div>
  );
}
