import { useCallback, useEffect, useMemo, useState } from "react";
import { AlertBanner } from "../components/AlertBanner";
import { CompareColumn } from "../components/CompareColumn";
import { ConfirmModal } from "../components/ConfirmModal";
import { EstimateTable } from "../components/EstimateTable";
import { RunConfigForm } from "../components/RunConfigForm";
import { useCatalog } from "../hooks/useCatalog";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import { getComparison, getRun, postDemo, postEstimate } from "../hooks/useApi";
import { useMonitorWebSocket, useRunWebSocket } from "../hooks/useWebSocket";
import type { RunWsStatus } from "../hooks/useWebSocket";
import type { CostEstimate, MonitorState } from "../types";
import { bestColumnKey, buildCompareVerdict, directionHint, parseElapsedSeconds } from "../utils/compareSummary";

const BACKENDS = [
  { key: "crewai", title: "CrewAI", titleClass: "crewai-title", testId: "compare-crewai" },
  { key: "langgraph", title: "LangGraph", titleClass: "langgraph-title", testId: "compare-langgraph" },
  {
    key: "claude-agent-sdk",
    title: "Claude Agent SDK",
    titleClass: "claude-title",
    testId: "compare-claude",
  },
] as const;

type BackendKey = (typeof BACKENDS)[number]["key"];

const SKIP_PREFLIGHT_KEY = "ai-team-compare-skip-preflight";
// Survives a page reload: lets Compare re-attach to runs the server is still
// tracking instead of showing empty columns for genuinely in-flight backends.
const ACTIVE_COMPARE_KEY = "ai-team-compare-active";

interface StoredComparison {
  comparisonId: string;
  runIds: Record<BackendKey, string | null>;
}

function loadStoredComparison(): StoredComparison | null {
  try {
    const raw = localStorage.getItem(ACTIVE_COMPARE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as StoredComparison;
    if (!parsed.comparisonId || !parsed.runIds) return null;
    return parsed;
  } catch {
    return null;
  }
}

function saveStoredComparison(v: StoredComparison) {
  localStorage.setItem(ACTIVE_COMPARE_KEY, JSON.stringify(v));
}

function clearStoredComparison() {
  localStorage.removeItem(ACTIVE_COMPARE_KEY);
}

function toRunWsStatus(status: string): RunWsStatus {
  switch (status) {
    case "pending":
      return "connecting";
    case "running":
    case "cancelling":
      return "running";
    case "awaiting_human":
      return "awaiting_human";
    case "complete":
      return "complete";
    case "complete_approved":
      return "complete_approved";
    case "cancelled":
      return "cancelled";
    case "error":
      return "error";
    default:
      return "idle";
  }
}

const TERMINAL_STATUSES = new Set(["complete", "complete_approved", "error", "cancelled"]);

export function Compare() {
  const { profileNames, error: catalogError } = useCatalog();
  useDocumentTitle("Compare — AI-Team");
  const [description, setDescription] = useState("");
  const [profile, setProfile] = useState("full");
  const [complexity, setComplexity] = useState("medium");
  const [estimate, setEstimate] = useState<CostEstimate | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [showPreflight, setShowPreflight] = useState(false);
  const [demoMode, setDemoMode] = useState(false);
  const [demoRunIds, setDemoRunIds] = useState<Record<BackendKey, string | null>>({
    crewai: null,
    langgraph: null,
    "claude-agent-sdk": null,
  });
  const [demoLoading, setDemoLoading] = useState(false);
  const [activeComparisonId, setActiveComparisonId] = useState<string | null>(null);
  const [formCollapsed, setFormCollapsed] = useState(false);

  const crewai = useRunWebSocket();
  const langgraph = useRunWebSocket();
  const claude = useRunWebSocket();

  const crewaiDemo = useMonitorWebSocket(demoMode ? demoRunIds.crewai : null);
  const langgraphDemo = useMonitorWebSocket(demoMode ? demoRunIds.langgraph : null);
  const claudeDemo = useMonitorWebSocket(demoMode ? demoRunIds["claude-agent-sdk"] : null);

  const liveColumns: Record<BackendKey, ReturnType<typeof useRunWebSocket>> = {
    crewai,
    langgraph,
    "claude-agent-sdk": claude,
  };

  // Persist run_ids as each /ws/run connection reports run_started, so a
  // reload mid-run has something to reattach to (run state otherwise lives
  // only in this component's React state and is wiped on refresh).
  useEffect(() => {
    if (!activeComparisonId) return;
    saveStoredComparison({
      comparisonId: activeComparisonId,
      runIds: { crewai: crewai.runId, langgraph: langgraph.runId, "claude-agent-sdk": claude.runId },
    });
  }, [activeComparisonId, crewai.runId, langgraph.runId, claude.runId]);

  const demoMonitors: Record<BackendKey, ReturnType<typeof useMonitorWebSocket>> = {
    crewai: crewaiDemo,
    langgraph: langgraphDemo,
    "claude-agent-sdk": claudeDemo,
  };

  // Reattachment: restored from localStorage on mount so a page reload during
  // a genuinely in-flight (or just-finished) Compare run doesn't fall back to
  // empty columns. `reattachRunIds` drives useMonitorWebSocket re-connects to
  // /ws/monitor/{run_id} (survives the page that started the run closing);
  // `reattachSeed` holds one-shot GET /api/runs/{id} snapshots for runs that
  // were already terminal by the time we checked, so they render immediately
  // without waiting on a socket that would just report "Run not found" churn.
  const [reattaching, setReattaching] = useState(false);
  const [reattachRunIds, setReattachRunIds] = useState<Record<BackendKey, string | null>>({
    crewai: null,
    langgraph: null,
    "claude-agent-sdk": null,
  });
  const [reattachSeed, setReattachSeed] = useState<
    Record<BackendKey, { monitor: MonitorState | null; status: string; error: string | null } | null>
  >({ crewai: null, langgraph: null, "claude-agent-sdk": null });

  useEffect(() => {
    const stored = loadStoredComparison();
    if (!stored) return;
    let cancelled = false;
    setReattaching(true);
    (async () => {
      try {
        const { runs } = await getComparison(stored.comparisonId);
        if (cancelled) return;
        const byBackend = new Map(runs.map((r) => [r.backend, r]));
        const nextRunIds: Record<BackendKey, string | null> = {
          crewai: null,
          langgraph: null,
          "claude-agent-sdk": null,
        };
        const nextSeed: typeof reattachSeed = {
          crewai: null,
          langgraph: null,
          "claude-agent-sdk": null,
        };
        for (const b of BACKENDS) {
          const row = byBackend.get(b.key);
          const runId = row?.run_id ?? stored.runIds[b.key];
          if (!runId) continue;
          nextRunIds[b.key] = runId;
          if (row && TERMINAL_STATUSES.has(row.status)) {
            // Terminal already — seed directly, no need to open a socket.
            const detail = await getRun(runId).catch(() => null);
            nextSeed[b.key] = {
              monitor: detail?.monitor ?? null,
              status: row.status,
              error: row.error,
            };
          }
        }
        if (!cancelled) {
          setReattachRunIds(nextRunIds);
          setReattachSeed(nextSeed);
          setFormCollapsed(true);
        }
      } catch {
        // Comparison no longer resolvable (server restarted without
        // persistence, or the id expired) — drop it rather than getting
        // stuck trying to reattach forever.
        clearStoredComparison();
      } finally {
        if (!cancelled) setReattaching(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const reattachMonitors: Record<BackendKey, ReturnType<typeof useMonitorWebSocket>> = {
    crewai: useMonitorWebSocket(reattachSeed.crewai ? null : reattachRunIds.crewai),
    langgraph: useMonitorWebSocket(reattachSeed.langgraph ? null : reattachRunIds.langgraph),
    "claude-agent-sdk": useMonitorWebSocket(
      reattachSeed["claude-agent-sdk"] ? null : reattachRunIds["claude-agent-sdk"],
    ),
  };

  const isReattached = (key: BackendKey) =>
    !demoMode && liveColumns[key].status === "idle" && reattachRunIds[key] != null;

  const getColumnState = (key: BackendKey) => {
    if (isReattached(key)) {
      const runId = reattachRunIds[key];
      const seed = reattachSeed[key];
      if (seed) {
        return {
          monitor: seed.monitor,
          status: toRunWsStatus(seed.status),
          runId,
          errorMessage: seed.error,
          hitlPayload: null,
          projectId: runId,
        };
      }
      const m = reattachMonitors[key];
      return {
        monitor: m.monitor,
        status: m.runStatus ? toRunWsStatus(m.runStatus) : ("running" as const),
        runId,
        errorMessage: m.errorMessage,
        hitlPayload: m.hitlPayload,
        projectId: runId,
      };
    }
    if (demoMode) {
      const d = demoMonitors[key];
      const runId = demoRunIds[key];
      const status = runId
        ? d.runStatus === "awaiting_human"
          ? ("awaiting_human" as const)
          : d.runStatus === "complete"
            ? ("complete" as const)
            : d.runStatus === "error"
              ? ("error" as const)
              : ("running" as const)
        : ("idle" as const);
      return {
        monitor: d.monitor,
        status,
        runId,
        errorMessage: d.errorMessage,
        hitlPayload: d.hitlPayload,
        projectId: runId,
      };
    }
    const col = liveColumns[key];
    return {
      monitor: col.monitor,
      status: col.status,
      runId: col.runId,
      errorMessage: col.errorMessage,
      hitlPayload: col.hitlPayload,
      projectId: col.projectId,
    };
  };

  const startLiveCompare = () => {
    if (!description.trim()) return;
    setActionError(null);
    setDemoMode(false);
    // A fresh compare supersedes anything we were reattaching to.
    clearStoredComparison();
    setReattachRunIds({ crewai: null, langgraph: null, "claude-agent-sdk": null });
    setReattachSeed({ crewai: null, langgraph: null, "claude-agent-sdk": null });
    // Shared across the 3 independent /ws/run connections below so the
    // server can persist and later look up this comparison's 3 backend runs
    // together (GET /api/comparisons/{comparisonId}), even after a restart.
    const comparisonId = crypto.randomUUID();
    setActiveComparisonId(comparisonId);
    setFormCollapsed(true);
    crewai.startRun("crewai", profile, description, complexity, null, comparisonId);
    langgraph.startRun("langgraph", profile, description, complexity, null, comparisonId);
    claude.startRun("claude-agent-sdk", profile, description, complexity, null, comparisonId);
  };

  const handleCompareClick = () => {
    if (!description.trim()) return;
    const skipUntil = sessionStorage.getItem(SKIP_PREFLIGHT_KEY);
    if (skipUntil && Date.now() < parseInt(skipUntil, 10)) {
      startLiveCompare();
      return;
    }
    setShowPreflight(true);
  };

  const handlePreflightConfirm = (skipFuture: boolean) => {
    if (skipFuture) {
      sessionStorage.setItem(SKIP_PREFLIGHT_KEY, String(Date.now() + 24 * 60 * 60 * 1000));
    }
    setShowPreflight(false);
    startLiveCompare();
  };

  const handleCompareDemo = async () => {
    setActionError(null);
    setDemoLoading(true);
    try {
      const [a, b, c] = await Promise.all([postDemo(), postDemo(), postDemo()]);
      setDemoRunIds({
        crewai: a.run_id,
        langgraph: b.run_id,
        "claude-agent-sdk": c.run_id,
      });
      setDemoMode(true);
      setFormCollapsed(true);
    } catch (e) {
      setActionError(e instanceof Error ? e.message : "Demo compare failed");
    } finally {
      setDemoLoading(false);
    }
  };

  const isRunning =
    !demoMode &&
    (crewai.status === "running" ||
      langgraph.status === "running" ||
      claude.status === "running" ||
      crewai.status === "connecting" ||
      langgraph.status === "connecting" ||
      claude.status === "connecting");

  const handleEstimate = async () => {
    try {
      setEstimate(await postEstimate(complexity));
    } catch (e) {
      setActionError(e instanceof Error ? e.message : "Estimate failed");
    }
  };

  const summaryRows = useMemo(() => {
    const rows: { key: BackendKey; label: string; m: MonitorState; failed?: boolean; failReason?: string }[] = [];
    for (const b of BACKENDS) {
      const col = getColumnState(b.key);
      if (col.monitor) {
        rows.push({ key: b.key, label: b.title, m: col.monitor, failed: col.status === "error", failReason: col.errorMessage ?? undefined });
      } else if (col.status === "error") {
        // No monitor snapshot yet but still failed — include as failed row
        rows.push({
          key: b.key,
          label: b.title,
          m: {
            phase: "error",
            elapsed: "—",
            agents: {},
            metrics: { tasks_completed: 0, tasks_failed: 0, retries: 0, files_generated: 0, guardrails_passed: 0, guardrails_failed: 0, guardrails_warned: 0, tests_passed: 0, tests_failed: 0 },
            log: [],
            guardrail_events: [],
          },
          failed: true,
          failReason: col.errorMessage ?? "Run failed",
        });
      }
    }
    return rows;
  }, [
    demoMode,
    crewai.monitor, crewai.status, crewai.errorMessage,
    langgraph.monitor, langgraph.status, langgraph.errorMessage,
    claude.monitor, claude.status, claude.errorMessage,
    crewaiDemo.monitor, crewaiDemo.runStatus, crewaiDemo.errorMessage,
    langgraphDemo.monitor, langgraphDemo.runStatus, langgraphDemo.errorMessage,
    claudeDemo.monitor, claudeDemo.runStatus, claudeDemo.errorMessage,
    reattachRunIds, reattachSeed,
    reattachMonitors.crewai.monitor, reattachMonitors.crewai.runStatus, reattachMonitors.crewai.errorMessage,
    reattachMonitors.langgraph.monitor, reattachMonitors.langgraph.runStatus, reattachMonitors.langgraph.errorMessage,
    reattachMonitors["claude-agent-sdk"].monitor, reattachMonitors["claude-agent-sdk"].runStatus, reattachMonitors["claude-agent-sdk"].errorMessage,
  ]);

  const preflightMessage = estimate
    ? `This will start 3 paid LLM runs (CrewAI, LangGraph, Claude Agent SDK). Estimated total: $${(estimate.total_usd * 3).toFixed(4)} (with buffer).`
    : "This will start 3 paid LLM runs in parallel. Run Estimate Cost first for a total budget hint.";

  const metricRows = useMemo(
    () =>
      [
        {
          label: "Elapsed",
          fn: (m: MonitorState) => m.elapsed,
          prefer: "min" as const,
          numeric: (m: MonitorState) => parseElapsedSeconds(m.elapsed),
        },
        {
          label: "Phase",
          fn: (m: MonitorState) => m.phase,
          prefer: null,
        },
        {
          label: "Cost (USD)",
          fn: (m: MonitorState) =>
            m.cost_usd != null ? `$${m.cost_usd.toFixed(4)}` : "—",
          prefer: "min" as const,
          numeric: (m: MonitorState) => m.cost_usd ?? 999999,
        },
        {
          label: "Tokens (est.)",
          fn: (m: MonitorState) =>
            m.token_estimate ? m.token_estimate.toLocaleString() : "—",
          prefer: "max" as const,
          numeric: (m: MonitorState) => m.token_estimate ?? 0,
        },
        {
          label: "Tasks completed",
          fn: (m: MonitorState) => m.metrics.tasks_completed,
          prefer: "max" as const,
          numeric: (m: MonitorState) => m.metrics.tasks_completed,
        },
        {
          label: "Tasks failed",
          fn: (m: MonitorState) => m.metrics.tasks_failed,
          prefer: "min" as const,
          numeric: (m: MonitorState) => m.metrics.tasks_failed,
        },
        {
          label: "Files generated",
          fn: (m: MonitorState) => m.metrics.files_generated,
          prefer: "max" as const,
          numeric: (m: MonitorState) => m.metrics.files_generated,
        },
        {
          label: "Guardrails passed",
          fn: (m: MonitorState) => m.metrics.guardrails_passed,
          prefer: "max" as const,
          numeric: (m: MonitorState) => m.metrics.guardrails_passed,
        },
        {
          label: "Guardrails failed",
          fn: (m: MonitorState) => m.metrics.guardrails_failed,
          prefer: "min" as const,
          numeric: (m: MonitorState) => m.metrics.guardrails_failed,
        },
        {
          label: "Tests passed",
          fn: (m: MonitorState) => m.metrics.tests_passed,
          prefer: "max" as const,
          numeric: (m: MonitorState) => m.metrics.tests_passed,
        },
        {
          label: "Tests failed",
          fn: (m: MonitorState) => m.metrics.tests_failed,
          prefer: "min" as const,
          numeric: (m: MonitorState) => m.metrics.tests_failed,
        },
        {
          label: "Retries",
          fn: (m: MonitorState) => m.metrics.retries,
          prefer: "min" as const,
          numeric: (m: MonitorState) => m.metrics.retries,
        },
      ] as const,
    [],
  );

  const bestForRow = useCallback(
    (row: (typeof metricRows)[number]) => {
      if (!row.prefer || !("numeric" in row) || !row.numeric) return null;
      return bestColumnKey(
        summaryRows,
        row.numeric,
        row.prefer,
      );
    },
    [summaryRows],
  );

  const verdictLine = useMemo(
    () =>
      buildCompareVerdict(summaryRows, [
        { label: "cost", prefer: "min", numeric: (m) => m.cost_usd ?? 999999 },
        { label: "tests passed", prefer: "max", numeric: (m) => m.metrics.tests_passed },
        { label: "elapsed", prefer: "min", numeric: (m) => parseElapsedSeconds(m.elapsed) },
      ]),
    [summaryRows],
  );

  const anyHitl = BACKENDS.some((b) => getColumnState(b.key).status === "awaiting_human");

  const failedColumns = BACKENDS.filter((b) => getColumnState(b.key).status === "error").map(
    (b) => ({ key: b.key, title: b.title, reason: getColumnState(b.key).errorMessage ?? "Run failed" }),
  );

  const hasReattachedComparison = BACKENDS.some((b) => reattachRunIds[b.key] != null);
  const allReattachedTerminal =
    hasReattachedComparison &&
    !demoMode &&
    !isRunning &&
    BACKENDS.every((b) => {
      const col = getColumnState(b.key);
      return !col.runId || TERMINAL_STATUSES.has(col.status);
    });

  const handleClearComparison = () => {
    clearStoredComparison();
    setReattachRunIds({ crewai: null, langgraph: null, "claude-agent-sdk": null });
    setReattachSeed({ crewai: null, langgraph: null, "claude-agent-sdk": null });
    setActiveComparisonId(null);
    setDemoMode(false);
    setDemoRunIds({ crewai: null, langgraph: null, "claude-agent-sdk": null });
    setFormCollapsed(false);
  };

  return (
    <div className="compare-page page-shell">
      {catalogError && <AlertBanner variant="warning" message={catalogError} />}
      {reattaching && (
        <AlertBanner variant="warning" message="Reconnecting to your last comparison…" />
      )}
      {allReattachedTerminal && (
        <div className="compare-finished-banner" data-testid="compare-finished-banner">
          <span>Last comparison (finished)</span>
          <button
            type="button"
            className="btn-secondary btn-sm"
            data-testid="compare-clear"
            onClick={handleClearComparison}
          >
            New comparison
          </button>
        </div>
      )}
      {actionError && (
        <AlertBanner message={actionError} onDismiss={() => setActionError(null)} />
      )}
      {anyHitl && (
        <AlertBanner
          variant="warning"
          message="One or more backends are paused for human review. Resolve each column to continue."
        />
      )}
      {failedColumns.length > 0 && (
        <div className="compare-failures-banner" data-testid="compare-failures-banner">
          <span className="compare-failures-heading">
            {failedColumns.length === 1
              ? `${failedColumns[0].title} failed`
              : `${failedColumns.length} backends failed`}
            {" — "}remaining backends continue.
          </span>
          <ul className="compare-failures-list">
            {failedColumns.map((f) => (
              <li key={f.key} data-testid={`compare-failure-${f.key}`}>
                <strong>{f.title}:</strong> {f.reason}
              </li>
            ))}
          </ul>
        </div>
      )}

      <header className="page-header">
        <h2>Compare Backends</h2>
        <p className="dim">Benchmark CrewAI, LangGraph, and Claude Agent SDK on the same assignment.</p>
      </header>

      <div
        className={`compare-form panel ${formCollapsed ? "compare-form-collapsed" : ""}`}
        data-testid="compare-form"
      >
        {formCollapsed ? (
          <button
            type="button"
            className="compare-form-summary btn-link"
            onClick={() => setFormCollapsed(false)}
            data-testid="compare-form-expand"
          >
            ⚖ {profile} · {complexity} · &apos;{(description || "…").slice(0, 48)}
            {(description?.length ?? 0) > 48 ? "…" : ""}&apos; — Edit &amp; rerun
          </button>
        ) : (
          <RunConfigForm
          profile={profile}
          setProfile={setProfile}
          complexity={complexity}
          setComplexity={setComplexity}
          description={description}
          setDescription={setDescription}
          profileNames={profileNames}
          descriptionTestId="compare-description"
          profileTestId="compare-profile"
          complexityTestId="compare-complexity"
          disabledHintTestId="compare-disabled-hint"
          estimateHelperTestId="compare-estimate-helper"
          disabledHintText="Enter a project description to compare."
          showDisabledHint={!description.trim()}
          estimate={estimate}
          estimateMultiplier={3}
          onEstimate={handleEstimate}
          estimateButtonTestId="compare-estimate"
          actions={
            <>
              <button
                className="btn-primary"
                onClick={handleCompareClick}
                disabled={isRunning || demoLoading || !description.trim()}
                data-testid="compare-submit"
              >
                {isRunning ? "Comparing…" : "Run All Backends"}
              </button>
              <button
                type="button"
                className="btn-link"
                onClick={handleCompareDemo}
                disabled={isRunning || demoLoading}
                data-testid="compare-demo"
              >
                {demoLoading ? "Starting demos…" : "Play sample runs (free · no files)"}
              </button>
            </>
          }
        />
        )}
      </div>

      {estimate && (
        <div className="panel estimate-panel">
          <h3>Cost Estimate ({estimate.complexity}) — per backend</h3>
          <EstimateTable estimate={estimate} runMultiplier={3} />
        </div>
      )}

      <ConfirmModal
        open={showPreflight}
        title="Start 3 paid runs?"
        message={preflightMessage}
        confirmLabel="Start comparison"
        onConfirm={() => handlePreflightConfirm(true)}
        onCancel={() => setShowPreflight(false)}
      />

      <div className="compare-grid compare-grid-3">
        {BACKENDS.map((b) => {
          const col = getColumnState(b.key);
          return (
            <CompareColumn
              key={b.key}
              title={b.title}
              titleClass={b.titleClass}
              monitor={col.monitor}
              status={col.status}
              runId={col.runId}
              projectId={col.projectId}
              errorMessage={col.errorMessage}
              hitlPayload={col.hitlPayload}
              testIdPrefix={b.testId}
            />
          );
        })}
      </div>

      {summaryRows.length > 0 && (
        <div className="compare-summary panel" data-testid="compare-summary">
          <h3>Comparison Summary</h3>
          {verdictLine && (
            <p className="compare-verdict" data-testid="compare-verdict">
              {verdictLine}
            </p>
          )}
          <table className="summary-table">
            <thead>
              <tr>
                <th>Metric</th>
                {summaryRows.map((r) => (
                  <th key={r.key}>{r.label}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {metricRows.map((row) => {
                const bestKey = bestForRow(row);
                return (
                  <tr key={row.label}>
                    <td>
                      {row.label}
                      {row.prefer != null && (
                        <span className="summary-direction dim" data-testid={`direction-${row.label}`}>
                          {" "}
                          {directionHint(row.prefer)}
                        </span>
                      )}
                    </td>
                    {summaryRows.map((r) => {
                      if (r.failed) {
                        return (
                          <td key={r.key} className="summary-failed">
                            —
                          </td>
                        );
                      }
                      const val = String(row.fn(r.m));
                      const isBest = bestKey === r.key && row.prefer != null;
                      return (
                        <td key={r.key} className={isBest ? "summary-best" : undefined}>
                          {val}
                        </td>
                      );
                    })}
                  </tr>
                );
              })}
              {summaryRows.some((r) => r.failed) && (
                <tr className="summary-failure-reason-row">
                  <td>Failure reason</td>
                  {summaryRows.map((r) => (
                    <td key={r.key} className={r.failed ? "summary-failed summary-failed-reason" : undefined} data-testid={r.failed ? `summary-reason-${r.key}` : undefined}>
                      {r.failed ? r.failReason : "—"}
                    </td>
                  ))}
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
