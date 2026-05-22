import { useCallback, useMemo, useState } from "react";
import { AlertBanner } from "../components/AlertBanner";
import { CompareColumn } from "../components/CompareColumn";
import { ConfirmModal } from "../components/ConfirmModal";
import { EstimateTable } from "../components/EstimateTable";
import { useCatalog } from "../hooks/useCatalog";
import { postDemo, postEstimate } from "../hooks/useApi";
import { useMonitorWebSocket, useRunWebSocket } from "../hooks/useWebSocket";
import type { CostEstimate, MonitorState } from "../types";
import { bestColumnKey, parseElapsedSeconds } from "../utils/compareSummary";

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

export function Compare() {
  const { profileNames, error: catalogError } = useCatalog();
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

  const demoMonitors: Record<BackendKey, ReturnType<typeof useMonitorWebSocket>> = {
    crewai: crewaiDemo,
    langgraph: langgraphDemo,
    "claude-agent-sdk": claudeDemo,
  };

  const getColumnState = (key: BackendKey) => {
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
    crewai.startRun("crewai", profile, description, complexity);
    langgraph.startRun("langgraph", profile, description, complexity);
    claude.startRun("claude-agent-sdk", profile, description, complexity);
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
    const rows: { key: BackendKey; label: string; m: MonitorState }[] = [];
    for (const b of BACKENDS) {
      const col = getColumnState(b.key);
      if (col.monitor) rows.push({ key: b.key, label: b.title, m: col.monitor });
    }
    return rows;
  }, [
    demoMode,
    crewai.monitor,
    langgraph.monitor,
    claude.monitor,
    crewaiDemo.monitor,
    langgraphDemo.monitor,
    claudeDemo.monitor,
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

  const anyHitl = BACKENDS.some((b) => getColumnState(b.key).status === "awaiting_human");

  return (
    <div className="compare-page page-shell">
      {catalogError && <AlertBanner variant="warning" message={catalogError} />}
      {actionError && (
        <AlertBanner message={actionError} onDismiss={() => setActionError(null)} />
      )}
      {anyHitl && (
        <AlertBanner
          variant="warning"
          message="One or more backends are paused for human review. Resolve each column to continue."
        />
      )}

      <header className="page-header">
        <h2>Compare Backends</h2>
        <p className="dim">Benchmark CrewAI, LangGraph, and Claude Agent SDK on the same assignment.</p>
      </header>

      <div className="compare-form panel">
        <div className="form-grid">
          <div className="form-group">
            <label>Team Profile</label>
            {profileNames.length > 0 ? (
              <select
                value={profile}
                onChange={(e) => setProfile(e.target.value)}
                data-testid="compare-profile"
              >
                {profileNames.map((name) => (
                  <option key={name} value={name}>
                    {name}
                  </option>
                ))}
              </select>
            ) : (
              <input
                value={profile}
                onChange={(e) => setProfile(e.target.value)}
                placeholder="full"
                data-testid="compare-profile"
              />
            )}
          </div>
          <div className="form-group">
            <label>Complexity</label>
            <select
              value={complexity}
              onChange={(e) => setComplexity(e.target.value)}
              data-testid="compare-complexity"
            >
              <option value="simple">Simple</option>
              <option value="medium">Medium</option>
              <option value="complex">Complex</option>
            </select>
          </div>
        </div>
        <div className="form-group full-width">
          <label>Project Description</label>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Describe what to build..."
            rows={3}
            data-testid="compare-description"
          />
        </div>
        <div className="form-actions">
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
            className="btn-warning"
            onClick={handleCompareDemo}
            disabled={isRunning || demoLoading}
            data-testid="compare-demo"
          >
            {demoLoading ? "Starting demos…" : "Compare Demo ($0)"}
          </button>
          <button type="button" className="btn-secondary" onClick={handleEstimate}>
            Estimate Cost
          </button>
        </div>
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
                    <td>{row.label}</td>
                    {summaryRows.map((r) => {
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
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
