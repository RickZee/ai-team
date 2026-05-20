import { Link } from "react-router-dom";
import type { MonitorState, RunInfo } from "../types";

interface RunSummaryCardProps {
  run: RunInfo;
  monitor: MonitorState;
  artifactProjectId?: string | null;
}

export function RunSummaryCard({ run, monitor, artifactProjectId }: RunSummaryCardProps) {
  const projectId = artifactProjectId ?? run.run_id;
  const isDemo = run.backend === "demo";
  const testsTotal = monitor.metrics.tests_passed + monitor.metrics.tests_failed;

  return (
    <div className="panel run-summary-card" data-testid="run-summary-card">
      <h3>Run summary</h3>
      <div className="run-summary-grid">
        <div>
          <span className="run-meta-label">Outcome</span>
          <p className={run.status === "complete" ? "green" : "red"}>{run.status}</p>
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
        {monitor.cost_usd != null && (
          <div>
            <span className="run-meta-label">Cost</span>
            <p>${monitor.cost_usd.toFixed(4)}</p>
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
        {!isDemo && (
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
