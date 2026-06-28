import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ActivityLog } from "../components/ActivityLog";
import { AgentTable } from "../components/AgentTable";
import { AgentTimeline } from "../components/AgentTimeline";
import { AlertBanner } from "../components/AlertBanner";
import { ArtifactPreview } from "../components/ArtifactPreview";
import { ConfirmModal } from "../components/ConfirmModal";
import { GuardrailsPanel } from "../components/GuardrailsPanel";
import { HowItWorks } from "../components/HowItWorks";
import { HumanReviewPanel } from "../components/HumanReviewPanel";
import { LoadingState } from "../components/LoadingState";
import { MetricsCard } from "../components/MetricsCard";
import { PhasePipeline } from "../components/PhasePipeline";
import { RunList } from "../components/RunList";
import { RunSummaryCard } from "../components/RunSummaryCard";
import { deleteRun, getHealth, getRun, getRuns, postCancel, postDemo } from "../hooks/useApi";
import { useMonitorWebSocket } from "../hooks/useWebSocket";
import type { MonitorState, RunInfo } from "../types";
import { formatRunDate, sortRunsByDate } from "../utils/formatRun";

const DEFAULT_TITLE = "AI-Team Dashboard";

const POLL_ACTIVE_MS = 2000;
const POLL_IDLE_MS = 8000;

export function Dashboard() {
  const { runId: routeRunId } = useParams<{ runId?: string }>();
  const navigate = useNavigate();
  const [runs, setRuns] = useState<RunInfo[]>([]);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(routeRunId ?? null);
  const [staticMonitor, setStaticMonitor] = useState<MonitorState | null>(null);
  const [apiError, setApiError] = useState<string | null>(null);
  const [healthOk, setHealthOk] = useState<boolean | null>(null);
  const [demoLoading, setDemoLoading] = useState(false);
  const [showGuardrails, setShowGuardrails] = useState(false);
  const [showFullLog, setShowFullLog] = useState(true);
  const [showCancelConfirm, setShowCancelConfirm] = useState(false);
  const [cancelLoading, setCancelLoading] = useState(false);
  const [showAgentTable, setShowAgentTable] = useState(false);
  const [deleteConfirmId, setDeleteConfirmId] = useState<string | null>(null);
  const [deleteLoading, setDeleteLoading] = useState(false);

  const activeRun = runs.find((r) => r.run_id === selectedRunId);
  const isLive =
    activeRun?.status === "running" || activeRun?.status === "awaiting_human";
  const isTerminal =
    activeRun?.status === "complete" ||
    activeRun?.status === "error" ||
    activeRun?.status === "cancelled";

  const live = useMonitorWebSocket(isLive ? selectedRunId : null);

  useEffect(() => {
    if (routeRunId) setSelectedRunId(routeRunId);
  }, [routeRunId]);

  const hasActiveRuns = useMemo(
    () => runs.some((r) => r.status === "running" || r.status === "awaiting_human"),
    [runs],
  );

  const pollRuns = useCallback(async () => {
    try {
      const data = await getRuns();
      const list = sortRunsByDate(data.runs as RunInfo[]);
      setRuns(list);
      setApiError(null);
      if (!selectedRunId && list.length > 0) {
        const running = list.find((r) => r.status === "running");
        const awaiting = list.find((r) => r.status === "awaiting_human");
        const pick = running ?? awaiting ?? list[0];
        setSelectedRunId(pick.run_id);
        if (!routeRunId) {
          navigate(`/runs/${pick.run_id}`, { replace: true });
        }
      }
    } catch (e) {
      setApiError(e instanceof Error ? e.message : "Cannot reach API");
    }
  }, [selectedRunId, routeRunId, navigate]);

  useEffect(() => {
    getHealth()
      .then((h) => setHealthOk(h.status === "ok"))
      .catch(() => setHealthOk(false));
  }, []);

  useEffect(() => {
    const tick = () => {
      if (document.hidden) return;
      pollRuns();
    };
    tick();
    const ms = hasActiveRuns ? POLL_ACTIVE_MS : POLL_IDLE_MS;
    const id = setInterval(tick, ms);
    return () => clearInterval(id);
  }, [pollRuns, hasActiveRuns]);

  useEffect(() => {
    if (!selectedRunId) {
      setStaticMonitor(null);
      return;
    }
    let cancelled = false;
    getRun(selectedRunId)
      .then((data) => {
        if (!cancelled) setStaticMonitor(data.monitor ?? null);
      })
      .catch(() => {
        if (!cancelled) setStaticMonitor(null);
      });
    return () => {
      cancelled = true;
    };
  }, [selectedRunId]);

  const monitor: MonitorState | null =
    isLive && live.monitor ? live.monitor : staticMonitor ?? live.monitor;

  const displayMonitor = monitor?.phase ? monitor : null;
  const hasMonitor = displayMonitor !== null;
  const runStatus = isLive ? live.runStatus : activeRun?.status ?? null;

  const isAwaitingHuman =
    activeRun?.status === "awaiting_human" || runStatus === "awaiting_human";

  useEffect(() => {
    if (isAwaitingHuman) {
      document.title = "⏸ Action needed — AI-Team";
    } else {
      document.title = DEFAULT_TITLE;
    }
    return () => {
      document.title = DEFAULT_TITLE;
    };
  }, [isAwaitingHuman]);

  useEffect(() => {
    if (isLive) {
      setShowGuardrails(false);
      setShowFullLog(true);
    }
    if (displayMonitor?.guardrail_events?.some((e) => e.status === "fail")) {
      setShowGuardrails(true);
    }
  }, [isLive, displayMonitor?.guardrail_events?.length]);

  const selectRun = (id: string) => {
    setSelectedRunId(id);
    navigate(`/runs/${id}`, { replace: true });
  };

  const handleDemo = async () => {
    setDemoLoading(true);
    try {
      const { run_id } = await postDemo();
      setSelectedRunId(run_id);
      navigate(`/runs/${run_id}`);
    } catch (e) {
      setApiError(e instanceof Error ? e.message : "Demo failed");
    } finally {
      setDemoLoading(false);
    }
  };

  const handleCancel = async () => {
    if (!selectedRunId) return;
    setCancelLoading(true);
    try {
      await postCancel(selectedRunId);
      setShowCancelConfirm(false);
      await pollRuns();
    } catch (e) {
      setApiError(e instanceof Error ? e.message : "Cancel failed");
      setShowCancelConfirm(false);
    } finally {
      setCancelLoading(false);
    }
  };

  const handleDeleteRun = async () => {
    if (!deleteConfirmId) return;
    setDeleteLoading(true);
    try {
      await deleteRun(deleteConfirmId);
      setDeleteConfirmId(null);
      if (selectedRunId === deleteConfirmId) {
        setSelectedRunId(null);
        navigate("/", { replace: true });
      }
      await pollRuns();
    } catch (e) {
      setApiError(e instanceof Error ? e.message : "Delete failed");
      setDeleteConfirmId(null);
    } finally {
      setDeleteLoading(false);
    }
  };

  const alerts = (
    <>
      {healthOk === false && (
        <AlertBanner variant="warning" message="API unreachable — is ai-team-web running?" />
      )}
      {apiError && <AlertBanner message={apiError} onDismiss={() => setApiError(null)} />}
      {live.errorMessage && <AlertBanner message={live.errorMessage} />}
    </>
  );

  return (
    <div className="dashboard-page">
      {isAwaitingHuman && (
        <AlertBanner
          variant="warning"
          message="This run is paused for human review — respond below to continue."
          testId="hitl-banner"
        />
      )}
      {(healthOk === false || apiError || live.errorMessage) && (
        <div className="dashboard-alerts" role="status">
          {alerts}
        </div>
      )}

      <div className="dashboard-layout">
        <aside className="run-sidebar panel" aria-label="Run history">
          <h3>Runs</h3>
          {runs.length === 0 ? (
            <p className="dim">No runs yet</p>
          ) : (
            <RunList
              runs={runs}
              selectedRunId={selectedRunId}
              onSelect={selectRun}
              onDelete={(id) => setDeleteConfirmId(id)}
            />
          )}
        </aside>

        <div className="dashboard-main">
          {!selectedRunId ? (
            <div className="dashboard-empty" data-testid="dashboard-empty">
              <h2>No Active Run</h2>
              <HowItWorks />
              <div className="empty-actions">
                <button
                  type="button"
                  className="btn-warning"
                  onClick={handleDemo}
                  disabled={demoLoading}
                  data-testid="dashboard-demo"
                >
                  {demoLoading ? "Starting…" : "Play sample run (free · no files)"}
                </button>
                <Link to="/run" className="btn-primary">
                  Go to Run
                </Link>
              </div>
            </div>
          ) : !hasMonitor ? (
            <LoadingState
              label={isLive ? "Connecting to live run…" : "Loading run…"}
            />
          ) : (
            <div className="dashboard" data-testid="dashboard-active">
              <div className="dashboard-sticky-header">
                <PhasePipeline
                  phase={displayMonitor.phase}
                  retries={displayMonitor.metrics.retries}
                />
                <div className="run-meta-row">
                  {activeRun && (
                    <>
                      <span className="dim">Run {activeRun.run_id}</span>
                      <span className={`status-chip status-${activeRun.status}`}>
                        {activeRun.status === "cancelling" ? "Cancelling…" : activeRun.status}
                      </span>
                      <span className="dim">{displayMonitor.elapsed}</span>
                      {displayMonitor.cost_usd != null && (
                        <span className="dim">${displayMonitor.cost_usd.toFixed(4)}</span>
                      )}
                      {isLive && activeRun.status !== "cancelling" && (
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
                    </>
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
              <ConfirmModal
                open={deleteConfirmId !== null}
                title="Delete run?"
                message="Removes workspace files, output bundle, and registry entry. This cannot be undone."
                confirmLabel={deleteLoading ? "Deleting…" : "Delete run"}
                cancelLabel="Cancel"
                onConfirm={handleDeleteRun}
                onCancel={() => setDeleteConfirmId(null)}
              />

              {isTerminal && activeRun && (
                <RunSummaryCard
                  run={activeRun}
                  monitor={displayMonitor}
                  artifactProjectId={activeRun.run_id}
                  estimateUsd={activeRun.estimate_usd ?? null}
                />
              )}

              {!isTerminal && activeRun && (
                <div className="dashboard-run-meta panel">
                  <p className="run-meta-date">
                    Started {formatRunDate(activeRun.started_at)}
                  </p>
                  <div className="run-meta-assignment">
                    <span className="run-meta-label">Assignment</span>
                    <p>{activeRun.description || "No assignment"}</p>
                  </div>
                </div>
              )}

              {isTerminal && activeRun && activeRun.backend !== "demo" && (
                <ArtifactPreview projectId={activeRun.run_id} isDemo={false} />
              )}

              {(runStatus === "awaiting_human" || live.hitlPayload) && selectedRunId && (
                <HumanReviewPanel
                  runId={selectedRunId}
                  payload={live.hitlPayload}
                  backend={activeRun?.backend}
                  onResumed={pollRuns}
                />
              )}

              {!isTerminal && (
                <div className="dashboard-grid">
                  <AgentTimeline
                    monitor={displayMonitor}
                    showTable={showAgentTable}
                    onToggleTable={() => setShowAgentTable((v) => !v)}
                  />
                  {showAgentTable && (
                    <div className="panel agents">
                      <h3>Agents</h3>
                      <AgentTable agents={displayMonitor.agents} />
                    </div>
                  )}
                  <div className="panel metrics">
                    <h3>Metrics</h3>
                    <MetricsCard
                      metrics={displayMonitor.metrics}
                      elapsed={displayMonitor.elapsed}
                      costUsd={displayMonitor.cost_usd}
                      tokenEstimate={displayMonitor.token_estimate}
                      sessionId={displayMonitor.session_id}
                    />
                  </div>
                  <div className="panel log">
                    <div className="panel-toolbar">
                      <h3>Activity Log</h3>
                      <button
                        type="button"
                        className="btn-secondary btn-sm"
                        onClick={() => setShowFullLog((v) => !v)}
                      >
                        {showFullLog ? "Collapse" : "Expand"}
                      </button>
                    </div>
                    {showFullLog && (
                      <ActivityLog
                        key={selectedRunId}
                        entries={displayMonitor.log}
                        ariaLive="polite"
                      />
                    )}
                  </div>
                  <div className="panel guardrails">
                    <div className="panel-toolbar">
                      <h3>Guardrails</h3>
                      {!showGuardrails && isLive && (
                        <button
                          type="button"
                          className="btn-secondary btn-sm"
                          onClick={() => setShowGuardrails(true)}
                        >
                          Show
                        </button>
                      )}
                    </div>
                    {(showGuardrails || !isLive) && (
                      <GuardrailsPanel events={displayMonitor.guardrail_events} />
                    )}
                    {!showGuardrails && isLive && (
                      <p className="dim panel-collapsed-hint">
                        Guardrails hidden — click Show or wait for a failure.
                      </p>
                    )}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
