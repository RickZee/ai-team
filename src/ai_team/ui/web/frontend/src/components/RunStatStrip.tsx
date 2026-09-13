import type { GuardrailEvent, MonitorState } from "../types";
import { statusChipClassMd } from "../utils/statusIntent";

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
  if (passed) parts.push(`${passed} passed`);
  if (failed) parts.push(`${failed} failed`);
  if (warned) parts.push(`${warned} warned`);
  return parts.join(" · ") || "none yet";
}

/** Compact stats — sole source for status/phase/elapsed/cost/tests. */
export function RunStatStrip({ status, monitor }: RunStatStripProps) {
  const m = monitor.metrics;
  const testsTotal = m.tests_passed + m.tests_failed;
  const testsLabel =
    testsTotal > 0
      ? `${m.tests_passed} passed${m.tests_failed > 0 ? ` · ${m.tests_failed} failed` : ""}`
      : null;
  const grLabel = guardrailsSummary(monitor.guardrail_events);

  return (
    <div className="run-stat-strip" data-testid="run-stat-strip">
      <span className={statusChipClassMd(status)}>
        {status === "cancelling" ? "Cancelling…" : status}
      </span>
      <span className="run-stat-sep" aria-hidden>
        ·
      </span>
      <span className="run-stat-item">{monitor.phase}</span>
      <span className="run-stat-sep" aria-hidden>
        ·
      </span>
      <span className="run-stat-item" data-testid="stat-elapsed">
        {monitor.elapsed}
      </span>
      {monitor.cost_usd != null && (
        <>
          <span className="run-stat-sep" aria-hidden>
            ·
          </span>
          <span className="run-stat-item" data-testid="stat-cost">
            ${monitor.cost_usd.toFixed(4)}
          </span>
        </>
      )}
      {testsLabel && (
        <>
          <span className="run-stat-sep" aria-hidden>
            ·
          </span>
          <span className="run-stat-item" data-testid="stat-tests">
            {testsLabel}
          </span>
        </>
      )}
      <span className="run-stat-sep" aria-hidden>
        ·
      </span>
      <span className="run-stat-item run-stat-guardrails" data-testid="stat-guardrails">
        Guardrails: {grLabel}
      </span>
    </div>
  );
}
