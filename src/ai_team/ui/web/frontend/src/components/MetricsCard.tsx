import type { Metrics } from "../types";

export function MetricsCard({
  metrics,
  tokenEstimate,
  sessionId,
}: {
  metrics: Metrics;
  tokenEstimate?: number;
  sessionId?: string | null;
}) {
  const grTotal = metrics.guardrails_passed + metrics.guardrails_failed + metrics.guardrails_warned;

  return (
    <div className="metrics-card">
      {tokenEstimate != null && tokenEstimate > 0 && (
        <div className="metric-row">
          <span className="metric-label">Tokens (est.)</span>
          <span className="metric-value">{tokenEstimate.toLocaleString()}</span>
        </div>
      )}
      {sessionId && (
        <div className="metric-row">
          <span className="metric-label">Session</span>
          <span className="metric-value dim text-truncate" title={sessionId}>
            {sessionId.slice(0, 12)}…
          </span>
        </div>
      )}
      <div className="metric-row">
        <span className="metric-label">Tasks completed</span>
        <span className="metric-value green">{metrics.tasks_completed}</span>
      </div>
      <div className="metric-row">
        <span className="metric-label">Tasks failed</span>
        <span className={`metric-value ${metrics.tasks_failed ? "red" : "dim"}`}>
          {metrics.tasks_failed}
        </span>
      </div>
      <div className="metric-row">
        <span className="metric-label">Retries</span>
        <span
          className={`metric-value ${metrics.retries ? "self-correct-text" : "dim"}`}
          data-testid="metrics-retries"
        >
          {metrics.retries > 0 ? `✓ Self-corrected ×${metrics.retries}` : metrics.retries}
        </span>
      </div>
      <div className="metric-row">
        <span className="metric-label">Files generated</span>
        <span className="metric-value blue">{metrics.files_generated}</span>
      </div>
      <div className="metric-divider" />
      <div className="metric-row">
        <span className="metric-label">Guardrails total</span>
        <span className="metric-value">{grTotal}</span>
      </div>
      <div className="metric-row">
        <span className="metric-label">&nbsp;&nbsp;✓ Passed</span>
        <span className="metric-value green">{metrics.guardrails_passed}</span>
      </div>
      <div className="metric-row">
        <span className="metric-label">&nbsp;&nbsp;✗ Failed</span>
        <span className={`metric-value ${metrics.guardrails_failed ? "red" : "dim"}`}>
          {metrics.guardrails_failed}
        </span>
      </div>
      <div className="metric-row">
        <span className="metric-label">&nbsp;&nbsp;⚠ Warned</span>
        <span className={`metric-value ${metrics.guardrails_warned ? "yellow" : "dim"}`}>
          {metrics.guardrails_warned}
        </span>
      </div>
    </div>
  );
}
