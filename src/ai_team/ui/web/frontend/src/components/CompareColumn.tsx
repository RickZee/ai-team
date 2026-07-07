import { Link } from "react-router-dom";
import { ActivityLog } from "./ActivityLog";
import { AgentTable } from "./AgentTable";
import { EmptyState } from "./EmptyState";
import { GuardrailsPanel } from "./GuardrailsPanel";
import { HumanReviewPanel } from "./HumanReviewPanel";
import { MetricsCard } from "./MetricsCard";
import { PhasePipeline } from "./PhasePipeline";
import type { RunWsStatus } from "../hooks/useWebSocket";
import type { MonitorState } from "../types";
import { deriveCompareColumnVariant } from "../utils/compareColumnState";

interface CompareColumnProps {
  title: string;
  titleClass: string;
  monitor: MonitorState | null;
  status: RunWsStatus;
  runId: string | null;
  projectId?: string | null;
  errorMessage: string | null;
  hitlPayload?: Record<string, unknown> | null;
  testIdPrefix: string;
}

function TerminalResultCard({
  monitor,
  status,
  runId,
  testIdPrefix,
}: {
  monitor: MonitorState;
  status: RunWsStatus;
  runId: string;
  testIdPrefix: string;
}) {
  const m = monitor.metrics;
  const statusLabel =
    status === "complete"
      ? "Complete"
      : status === "complete_approved"
        ? "Approved"
        : status === "cancelled"
          ? "Cancelled"
          : "Failed";

  return (
    <div className="compare-terminal-card" data-testid={`${testIdPrefix}-terminal`}>
      <span className={`chip chip-md status-chip status-${status}`}>{statusLabel}</span>
      <div className="compare-terminal-stats">
        <span>{monitor.elapsed}</span>
        {monitor.cost_usd != null && <span>${monitor.cost_usd.toFixed(4)}</span>}
        {(m.tests_passed > 0 || m.tests_failed > 0) && (
          <span>
            {m.tests_passed}✓{m.tests_failed > 0 ? ` / ${m.tests_failed}✗` : ""} tests
          </span>
        )}
        {m.files_generated > 0 && <span>{m.files_generated} files</span>}
      </div>
      <Link to={`/runs/${runId}`} className="btn-secondary btn-sm" data-testid={`${testIdPrefix}-open-run`}>
        Open run
      </Link>
    </div>
  );
}

export function CompareColumn({
  title,
  titleClass,
  monitor,
  status,
  runId,
  errorMessage,
  hitlPayload,
  testIdPrefix,
}: CompareColumnProps) {
  const variant = deriveCompareColumnVariant(status, monitor, runId, errorMessage);

  return (
    <div className="compare-col panel-inner" data-testid={`${testIdPrefix}-col`}>
      <h3 className={`backend-title ${titleClass}`} title={title}>
        {title}
      </h3>

      {variant.kind === "idle" && (
        <EmptyState
          title="Not started"
          hint="Run a comparison from the form above to start all three backends."
          testId={`${testIdPrefix}-empty`}
          className="empty-state compare-col-placeholder"
        />
      )}

      {variant.kind === "starting" && (
        <EmptyState
          title="Starting…"
          testId={`${testIdPrefix}-starting`}
          className="empty-state compare-col-placeholder"
        />
      )}

      {variant.kind === "awaiting_human" && (
        <>
          <HumanReviewPanel
            runId={variant.runId}
            payload={hitlPayload ?? null}
            backend={title}
          />
          {variant.monitor && (
            <>
              <PhasePipeline phase={variant.monitor.phase} retries={variant.monitor.metrics.retries} />
              <AgentTable agents={variant.monitor.agents} terminal={false} />
              <MetricsCard metrics={variant.monitor.metrics} tokenEstimate={variant.monitor.token_estimate} sessionId={variant.monitor.session_id} />
            </>
          )}
        </>
      )}

      {variant.kind === "live" && (
        <>
          <PhasePipeline phase={variant.monitor.phase} retries={variant.monitor.metrics.retries} />
          <AgentTable agents={variant.monitor.agents} terminal={false} />
          <MetricsCard
            metrics={variant.monitor.metrics}
            tokenEstimate={variant.monitor.token_estimate}
            sessionId={variant.monitor.session_id}
          />
          <div className="panel">
            <h4 className="panel-header">Activity Log</h4>
            <ActivityLog entries={variant.monitor.log} compact />
          </div>
          {variant.monitor.guardrail_events.length > 0 && (
            <div className="panel">
              <h4 className="panel-header">Guardrails</h4>
              <GuardrailsPanel events={variant.monitor.guardrail_events} terminal={false} />
            </div>
          )}
        </>
      )}

      {variant.kind === "terminal" && variant.runId && (
        <TerminalResultCard
          monitor={variant.monitor}
          status={variant.status}
          runId={variant.runId}
          testIdPrefix={testIdPrefix}
        />
      )}

      {variant.kind === "error" && (
        <div className="run-error compare-col-error" data-testid={`${testIdPrefix}-error`}>
          <span className="compare-col-error-label">Failed</span>
          <p className="compare-col-error-reason" data-testid={`${testIdPrefix}-error-reason`}>
            {variant.errorMessage}
          </p>
          {variant.runId && (
            <Link to={`/runs/${variant.runId}`} className="btn-secondary btn-sm" data-testid={`${testIdPrefix}-open-run`}>
              Open run
            </Link>
          )}
        </div>
      )}
    </div>
  );
}
