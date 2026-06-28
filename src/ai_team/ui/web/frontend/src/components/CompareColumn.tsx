import { Link } from "react-router-dom";
import { ActivityLog } from "./ActivityLog";
import { AgentTable } from "./AgentTable";
import { GuardrailsPanel } from "./GuardrailsPanel";
import { HumanReviewPanel } from "./HumanReviewPanel";
import { MetricsCard } from "./MetricsCard";
import { PhasePipeline } from "./PhasePipeline";
import type { RunWsStatus } from "../hooks/useWebSocket";
import type { MonitorState } from "../types";

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

export function CompareColumn({
  title,
  titleClass,
  monitor,
  status,
  runId,
  projectId,
  errorMessage,
  hitlPayload,
  testIdPrefix,
}: CompareColumnProps) {
  const artifactId = projectId ?? runId;

  return (
    <div className="compare-col" data-testid={`${testIdPrefix}-col`}>
      <h3 className={`backend-title ${titleClass}`}>{title}</h3>
      {status === "awaiting_human" && runId && (
        <HumanReviewPanel runId={runId} payload={hitlPayload ?? null} backend={title} />
      )}
      {monitor ? (
        <>
          <PhasePipeline phase={monitor.phase} retries={monitor.metrics.retries} />
          <AgentTable agents={monitor.agents} />
          <MetricsCard
            metrics={monitor.metrics}
            elapsed={monitor.elapsed}
            costUsd={monitor.cost_usd}
            tokenEstimate={monitor.token_estimate}
          />
          <div className="panel">
            <h4>Activity Log</h4>
            <ActivityLog entries={monitor.log} compact />
          </div>
          <div className="panel">
            <h4>Guardrails</h4>
            <GuardrailsPanel events={monitor.guardrail_events} />
          </div>
        </>
      ) : (
        <div className="empty-state">
          {status === "running" || status === "connecting"
            ? "Starting…"
            : status === "awaiting_human"
              ? "Awaiting human review"
              : "Not started"}
        </div>
      )}
      {status === "complete" && (
        <div className="run-complete" data-testid={`${testIdPrefix}-complete`}>
          <span className="green">Complete</span>
          {runId && (
            <div className="run-complete-actions">
              <Link to={`/runs/${runId}`} className="btn-secondary btn-sm">
                Dashboard
              </Link>
              {artifactId && (
                <Link
                  to={`/artifacts?project=${encodeURIComponent(artifactId)}`}
                  className="btn-secondary btn-sm"
                >
                  Artifacts
                </Link>
              )}
            </div>
          )}
        </div>
      )}
      {status === "error" && (
        <div className="run-error compare-col-error" data-testid={`${testIdPrefix}-error`}>
          <span className="compare-col-error-label">Failed</span>
          <p className="compare-col-error-reason" data-testid={`${testIdPrefix}-error-reason`}>
            {errorMessage ?? "Run failed"}
          </p>
          {runId && (
            <Link to={`/runs/${runId}`} className="btn-secondary btn-sm">
              View run
            </Link>
          )}
        </div>
      )}
    </div>
  );
}
