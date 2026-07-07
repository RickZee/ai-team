import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ActivityLog } from "../components/ActivityLog";
import { AgentTable } from "../components/AgentTable";
import { AgentTimeline, AgentTimelineNote } from "../components/AgentTimeline";
import { AlertBanner } from "../components/AlertBanner";
import { ConfirmModal } from "../components/ConfirmModal";
import { EmptyState } from "../components/EmptyState";
import { GuardrailsPanel } from "../components/GuardrailsPanel";
import { HumanReviewPanel } from "../components/HumanReviewPanel";
import { LoadingState } from "../components/LoadingState";
import { MetricsCard } from "../components/MetricsCard";
import { PhasePipeline } from "../components/PhasePipeline";
import { RunArtifactsPanel } from "../components/RunArtifactsPanel";
import { RunStatStrip } from "../components/RunStatStrip";
import { RunSummaryCard } from "../components/RunSummaryCard";
import { TestResultsPanel } from "../components/TestResultsPanel";
import { ApiError, getHealth, getProjectTests, getRun, getRuns, postCancel } from "../hooks/useApi";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import { useMonitorWebSocket } from "../hooks/useWebSocket";
import type { MonitorState, RunInfo, TestsPanelData } from "../types";
import { formatRunDate, sortRunsByDate } from "../utils/formatRun";

type RunTab = "overview" | "activity" | "artifacts" | "tests";

const LOG_PREVIEW_LINES = 5;
const TERMINAL_STATUSES = new Set(["complete", "complete_approved", "error", "cancelled"]);

function tabFromHash(hash: string): RunTab {
  const h = hash.replace("#", "");
  if (h === "activity" || h === "artifacts" || h === "tests") return h;
  return "overview";
}

function runInfoFromDetail(data: Awaited<ReturnType<typeof getRun>>): RunInfo {
  const {
    run_id,
    backend,
    profile,
    description,
    status,
    started_at,
    finished_at,
    error,
    comparison_id,
    estimate_usd,
    complexity,
    is_sample,
  } = data;
  return {
    run_id,
    backend,
    profile,
    description,
    status,
    started_at: started_at ?? "",
    finished_at: finished_at ?? null,
    error: error ?? null,
    comparison_id: comparison_id ?? null,
    estimate_usd,
    complexity,
    is_sample,
  };
}

/** Run detail with internal tabs (IA-1). */
export function RunDetail() {
  const { runId } = useParams<{ runId: string }>();
  const [tab, setTab] = useState<RunTab>(() => tabFromHash(window.location.hash));
  const [runs, setRuns] = useState<RunInfo[]>([]);
  const [runDetail, setRunDetail] = useState<RunInfo | null>(null);
  const [staticMonitor, setStaticMonitor] = useState<MonitorState | null>(null);
  const [loadError, setLoadError] = useState<"not_found" | "disk_only" | null>(null);
  const [loading, setLoading] = useState(true);
  const [apiError, setApiError] = useState<string | null>(null);
  const [healthOk, setHealthOk] = useState<boolean | null>(null);
  const [showFullLog, setShowFullLog] = useState(false);
  const [showCancelConfirm, setShowCancelConfirm] = useState(false);
  const [cancelLoading, setCancelLoading] = useState(false);
  const [showAgentTable, setShowAgentTable] = useState(false);
  const [tests, setTests] = useState<TestsPanelData | null>(null);
  const [testsLoading, setTestsLoading] = useState(false);

  const activeRun = runs.find((r) => r.run_id === runId);
  const effectiveRun = activeRun ?? runDetail;
  const isLive =
    effectiveRun?.status === "running" || effectiveRun?.status === "awaiting_human";
  const isTerminal = effectiveRun?.status
    ? TERMINAL_STATUSES.has(effectiveRun.status)
    : false;

  const live = useMonitorWebSocket(isLive ? runId ?? null : null);
  const monitor: MonitorState | null = live.monitor ?? (isLive ? null : staticMonitor);
  const displayMonitor = monitor?.phase ? monitor : null;
  const hasAgents = displayMonitor ? Object.keys(displayMonitor.agents).length > 0 : false;
  const hasGuardrailEvents = (displayMonitor?.guardrail_events.length ?? 0) > 0;

  useDocumentTitle(
    effectiveRun
      ? `${effectiveRun.description?.slice(0, 40) || runId} — AI-Team`
      : "Run — AI-Team",
  );

  useEffect(() => {
    const onHash = () => setTab(tabFromHash(window.location.hash));
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  const selectTab = (t: RunTab) => {
    setTab(t);
    const hash = t === "overview" ? "" : `#${t}`;
    window.history.replaceState(null, "", `${window.location.pathname}${hash}`);
  };

  useEffect(() => {
    getHealth()
      .then((h) => setHealthOk(h.status === "ok"))
      .catch(() => setHealthOk(false));
    getRuns()
      .then((data) => setRuns(sortRunsByDate(data.runs as RunInfo[])))
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (!runId) return;
    let cancelled = false;
    setLoading(true);
    setLoadError(null);
    getRun(runId)
      .then((data) => {
        if (cancelled) return;
        setStaticMonitor(data.monitor ?? null);
        setRunDetail(runInfoFromDetail(data));
        setLoading(false);
      })
      .catch((e) => {
        if (cancelled) return;
        if (e instanceof ApiError && e.status === 404) {
          setLoadError("not_found");
        } else {
          setApiError(e instanceof Error ? e.message : "Failed to load run");
        }
        setStaticMonitor(null);
        setRunDetail(null);
        setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [runId]);

  useEffect(() => {
    if (!runId || !isTerminal || effectiveRun?.backend === "demo") return;
    setTestsLoading(true);
    getProjectTests(runId)
      .then(setTests)
      .catch(() => setTests(null))
      .finally(() => setTestsLoading(false));
  }, [runId, isTerminal, effectiveRun?.backend]);

  const handleCancel = async () => {
    if (!runId) return;
    setCancelLoading(true);
    try {
      await postCancel(runId);
      setShowCancelConfirm(false);
      const data = await getRun(runId);
      setRunDetail(runInfoFromDetail(data));
    } catch (e) {
      setApiError(e instanceof Error ? e.message : "Cancel failed");
      setShowCancelConfirm(false);
    } finally {
      setCancelLoading(false);
    }
  };

  const logEntries = displayMonitor?.log ?? [];
  const logPreview = logEntries.slice(-LOG_PREVIEW_LINES);
  const isAwaitingHuman = effectiveRun?.status === "awaiting_human";

  if (!runId) {
    return (
      <EmptyState
        title="No run selected"
        action={
          <Link to="/" className="btn-primary">
            Back to runs
          </Link>
        }
      />
    );
  }

  if (loading) {
    return <LoadingState label="Loading run…" />;
  }

  if (loadError === "not_found") {
    return (
      <div className="page-shell" data-testid="run-not-found">
        <EmptyState
          title="Run not found"
          hint="It may have been deleted or the server restarted."
          action={
            <Link to="/" className="btn-primary" data-testid="back-to-runs">
              Back to runs
            </Link>
          }
        />
      </div>
    );
  }

  if (!displayMonitor || !effectiveRun) {
    return <LoadingState label={isLive ? "Connecting to live run…" : "Loading run…"} />;
  }

  return (
    <div className="run-detail-page page-shell" data-testid="run-detail">
      {healthOk === false && (
        <AlertBanner variant="warning" message="API unreachable — is ai-team-web running?" />
      )}
      {apiError && <AlertBanner message={apiError} onDismiss={() => setApiError(null)} />}
      {live.errorMessage && <AlertBanner message={live.errorMessage} />}
      {isAwaitingHuman && (
        <AlertBanner
          variant="warning"
          message="This run is paused for human review — respond below to continue."
          testId="hitl-banner"
        />
      )}

      <header className="run-detail-header page-header">
        <div>
          <h2 className="run-detail-title" title={effectiveRun.description}>
            {effectiveRun.description?.slice(0, 80) || runId}
          </h2>
          <p className="dim run-detail-meta">
            {effectiveRun.backend} · {formatRunDate(effectiveRun.started_at)}
            {effectiveRun.comparison_id && (
              <>
                {" · "}
                <Link to="/compare" className="chip chip-sm run-list-comparison-chip">
                  ⚖ part of comparison
                </Link>
              </>
            )}
          </p>
        </div>
        <Link to="/" className="btn-secondary btn-sm" data-testid="nav-home-runs">
          All runs
        </Link>
      </header>

      <div className="run-detail-tabs" role="tablist">
        {(
          [
            ["overview", "Overview"],
            ["activity", "Activity"],
            ["artifacts", "Artifacts"],
            ["tests", "Tests"],
          ] as const
        ).map(([id, label]) => (
          <button
            key={id}
            type="button"
            role="tab"
            aria-selected={tab === id}
            className={`run-detail-tab ${tab === id ? "active" : ""}`}
            onClick={() => selectTab(id)}
            data-testid={`run-tab-${id}`}
          >
            {label}
          </button>
        ))}
      </div>

      <div className="dashboard-sticky-header run-detail-sticky">
        <PhasePipeline phase={displayMonitor.phase} retries={displayMonitor.metrics.retries} />
        <div className="dashboard-live-header">
          <RunStatStrip status={effectiveRun.status} monitor={displayMonitor} />
          {isLive && effectiveRun.status !== "cancelling" && (
            <button
              type="button"
              className="btn-secondary btn-sm"
              onClick={() => setShowCancelConfirm(true)}
              disabled={cancelLoading}
              data-testid="stop-run-btn"
            >
              Stop run
            </button>
          )}
        </div>
      </div>

      <ConfirmModal
        open={showCancelConfirm}
        title="Stop run?"
        message="The run will be cancelled after the current step completes. This cannot be undone."
        confirmLabel={cancelLoading ? "Stopping…" : "Stop run"}
        cancelLabel="Keep running"
        onConfirm={handleCancel}
        onCancel={() => setShowCancelConfirm(false)}
      />

      {tab === "overview" && (
        <div className="run-tab-overview" data-testid="run-tab-panel-overview">
          {isTerminal && (
            <RunSummaryCard
              run={effectiveRun}
              monitor={displayMonitor}
              artifactProjectId={effectiveRun.run_id}
              estimateUsd={effectiveRun.estimate_usd ?? null}
            />
          )}
          {!isTerminal && (
            <div className="dashboard-run-meta panel">
              <div className="run-meta-assignment">
                <span className="run-meta-label">Assignment</span>
                <p>{effectiveRun.description || "No assignment"}</p>
              </div>
            </div>
          )}
          {isAwaitingHuman && (
            <HumanReviewPanel
              runId={runId}
              payload={live.hitlPayload}
              backend={effectiveRun.backend}
              onResumed={async () => {
                live.clearHitl();
                try {
                  const [data, runsData] = await Promise.all([getRun(runId), getRuns()]);
                  setRuns(sortRunsByDate(runsData.runs as RunInfo[]));
                  setRunDetail({
                    run_id: data.run_id,
                    backend: data.backend,
                    profile: data.profile,
                    description: data.description,
                    status: data.status,
                    started_at: (data as RunInfo).started_at ?? "",
                    finished_at: (data as RunInfo).finished_at ?? null,
                    error: (data as RunInfo).error ?? null,
                    comparison_id: (data as RunInfo).comparison_id ?? null,
                  });
                  if (data.monitor) setStaticMonitor(data.monitor);
                } catch {
                  /* best-effort refresh */
                }
              }}
            />
          )}
          <div className="panel metrics">
            <h3 className="panel-header">Metrics</h3>
            <MetricsCard
              metrics={displayMonitor.metrics}
              tokenEstimate={displayMonitor.token_estimate}
              sessionId={displayMonitor.session_id}
            />
          </div>
        </div>
      )}

      {tab === "activity" && (
        <div className="run-tab-activity dashboard-grid grid-adaptive" data-testid="run-tab-panel-activity">
          {!hasAgents && <AgentTimelineNote terminal={isTerminal} />}
          {hasAgents && (
            <AgentTimeline
              monitor={displayMonitor}
              showTable={showAgentTable}
              onToggleTable={() => setShowAgentTable((v) => !v)}
              terminal={isTerminal}
            />
          )}
          {showAgentTable && hasAgents && (
            <div className="panel agents">
              <h3 className="panel-header">Agents</h3>
              <AgentTable agents={displayMonitor.agents} terminal={isTerminal} />
            </div>
          )}
          <div className="panel log">
            <div className="panel-header-row">
              <h3 className="panel-header">Activity Log</h3>
              {isLive && (
                <button
                  type="button"
                  className="btn-secondary btn-sm"
                  onClick={() => setShowFullLog((v) => !v)}
                >
                  {showFullLog ? "Collapse" : "Expand full log"}
                </button>
              )}
            </div>
            {isLive && !showFullLog ? (
              <>
                {logEntries.length > LOG_PREVIEW_LINES && (
                  <p className="dim log-preview-hint">
                    Showing last {LOG_PREVIEW_LINES} of {logEntries.length} lines
                  </p>
                )}
                <ActivityLog entries={logPreview} compact ariaLive="polite" />
              </>
            ) : (
              <ActivityLog key={runId} entries={logEntries} ariaLive="polite" />
            )}
          </div>
          {hasGuardrailEvents && (
            <div className="panel guardrails">
              <h3 className="panel-header">Guardrails</h3>
              <GuardrailsPanel events={displayMonitor.guardrail_events} terminal={isTerminal} />
            </div>
          )}
        </div>
      )}

      {tab === "artifacts" && (
        <div data-testid="run-tab-panel-artifacts">
          <RunArtifactsPanel projectId={runId} isDemo={effectiveRun.backend === "demo"} />
        </div>
      )}

      {tab === "tests" && (
        <div className="panel" data-testid="run-tab-panel-tests">
          <TestResultsPanel data={tests} loading={testsLoading} />
        </div>
      )}
    </div>
  );
}
