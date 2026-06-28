import { Link, useNavigate } from "react-router-dom";
import type { MonitorState, RunInfo } from "../types";

interface RunSummaryCardProps {
  run: RunInfo;
  monitor: MonitorState;
  artifactProjectId?: string | null;
  estimateUsd?: number | null;
}

export function RunSummaryCard({ run, monitor, artifactProjectId, estimateUsd }: RunSummaryCardProps) {
  const navigate = useNavigate();
  const projectId = artifactProjectId ?? run.run_id;
  const isDemo = run.backend === "demo";
  const isCancelled = run.status === "cancelled";
  const testsTotal = monitor.metrics.tests_passed + monitor.metrics.tests_failed;

  const actualCost = monitor.cost_usd;
  const hasEstimate = estimateUsd != null && !isDemo;
  const costDelta =
    hasEstimate && actualCost != null ? actualCost - estimateUsd : null;

  const handleRetry = () => {
    navigate("/run", {
      state: {
        prefill: {
          backend: run.backend,
          profile: run.profile,
          description: run.description,
          complexity: run.complexity ?? "medium",
        },
      },
    });
  };

  return (
    <div className="panel run-summary-card" data-testid="run-summary-card">
      <h3>Run summary</h3>
      <div className="run-summary-grid">
        <div>
          <span className="run-meta-label">Outcome</span>
          <p className={run.status === "complete" ? "green" : isCancelled ? "yellow" : "red"}>
            {run.status}
          </p>
        </div>
        <div>
          <span className="run-meta-label">Elapsed</span>
          <p>{monitor.elapsed}</p>
        </div>
        <div>
          <span className="run-meta-label">Backend</span>
          <p>{run.backend}</p>
        </div>
        <div>
          <span className="run-meta-label">Profile</span>
          <p>{run.profile}</p>
        </div>
        {/* T2: Estimate vs Actual cost */}
        {!isDemo && (
          <div>
            <span className="run-meta-label">Cost</span>
            {actualCost != null ? (
              <p>
                <span>Actual ${actualCost.toFixed(4)}</span>
                {hasEstimate && (
                  <>
                    <span className="dim"> · Est ${estimateUsd!.toFixed(4)}</span>
                    {costDelta != null && (
                      <span className={costDelta >= 0 ? "red" : "green"}>
                        {" "}({costDelta >= 0 ? "+" : ""}{costDelta.toFixed(4)})
                      </span>
                    )}
                  </>
                )}
              </p>
            ) : (
              <p>
                {hasEstimate ? (
                  <span>Est ${estimateUsd!.toFixed(4)} <span className="dim">(actual not recorded)</span></span>
                ) : (
                  <span className="dim">estimate not run</span>
                )}
              </p>
            )}
          </div>
        )}
        {isDemo && actualCost != null && (
          <div>
            <span className="run-meta-label">Cost</span>
            <p>${actualCost.toFixed(4)}</p>
          </div>
        )}
        {monitor.token_estimate != null && monitor.token_estimate > 0 && (
          <div>
            <span className="run-meta-label">Tokens (est.)</span>
            <p>{monitor.token_estimate.toLocaleString()}</p>
          </div>
        )}
        {testsTotal > 0 && (
          <div>
            <span className="run-meta-label">Tests</span>
            <p>
              <span className="green">{monitor.metrics.tests_passed} passed</span>
              {monitor.metrics.tests_failed > 0 && (
                <span className="red"> · {monitor.metrics.tests_failed} failed</span>
              )}
            </p>
          </div>
        )}
      </div>
      {run.error && <p className="run-summary-error">{run.error}</p>}
      <div className="run-summary-actions">
        {!isDemo && !isCancelled && (
          <Link
            to={`/artifacts?project=${encodeURIComponent(projectId)}`}
            className="btn-primary"
            data-testid="dashboard-view-artifacts"
          >
            View artifacts
          </Link>
        )}
        {isDemo && (
          <p className="dim run-summary-demo-note" data-testid="demo-artifacts-note">
            Demo runs do not write files to disk. Start a real run to browse artifacts.
          </p>
        )}
        {/* T3: Retry and Edit & rerun */}
        {(run.status === "error" || isCancelled) && !isDemo && (
          <>
            <button
              type="button"
              className="btn-primary"
              onClick={handleRetry}
              data-testid="retry-run-btn"
            >
              Retry
            </button>
            <button
              type="button"
              className="btn-secondary"
              onClick={handleRetry}
              data-testid="edit-rerun-btn"
            >
              Edit &amp; rerun
            </button>
          </>
        )}
        <Link to="/run" className="btn-secondary">
          Start another run
        </Link>
        {!isDemo && (
          <Link to="/compare" className="btn-secondary">
            Compare backends
          </Link>
        )}
      </div>
    </div>
  );
}
