import type { GuardrailEvent, MonitorState } from "../types";

interface RunStatStripProps {
  status: string;
  monitor: MonitorState;
}

function guardrailsSummary(events: GuardrailEvent[]): string {
  if (events.length === 0) return "none yet";
  const passed = events.filter((e) => e.status === "pass").length;
  const failed = events.filter((e) => e.status === "fail").length;
  const warned = events.filter((e) => e.status === "warn").length;
  const parts: string[] = [];
  if (passed) parts.push(`✓ ${passed}`);
  if (failed) parts.push(`✗ ${failed}`);
  if (warned) parts.push(`⚠ ${warned}`);
  return parts.join(" · ") || "none yet";
}

/** Compact stats — sole source for status/phase/elapsed/cost/tests (IA-2, V-3). */
export function RunStatStrip({ status, monitor }: RunStatStripProps) {
  const m = monitor.metrics;
  const testsTotal = m.tests_passed + m.tests_failed;
  const testsLabel =
    testsTotal > 0
      ? `${m.tests_passed}✓${m.tests_failed > 0 ? ` / ${m.tests_failed}✗` : ""}`
      : null;
  const grLabel = guardrailsSummary(monitor.guardrail_events);

  return (
    <div className="run-stat-strip" data-testid="run-stat-strip">
      <span className={`chip chip-md status-chip status-${status}`}>
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
      <span className="run-stat-sep" aria-hidden>
        ·
      </span>
      <span className="run-stat-item run-stat-guardrails" title="Guardrails" data-testid="stat-guardrails">
        Guardrails: {grLabel}
      </span>
    </div>
  );
}
