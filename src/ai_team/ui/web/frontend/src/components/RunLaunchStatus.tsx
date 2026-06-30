import { Link } from "react-router-dom";
import type { RunWsStatus } from "../hooks/useWebSocket";

interface RunLaunchStatusProps {
  status: RunWsStatus;
  runId: string | null;
  errorMessage: string | null;
}

const STATUS_LABEL: Record<RunWsStatus, string> = {
  idle: "",
  connecting: "Connecting…",
  running: "Run started — opening dashboard…",
  awaiting_human: "Paused for human review",
  complete: "Run complete",
  cancelled: "Run cancelled",
  error: "Run failed",
};

export function RunLaunchStatus({ status, runId, errorMessage }: RunLaunchStatusProps) {
  if (status === "idle") return null;

  return (
    <div className="panel run-launch-status" data-testid="run-launch-status">
      <p className={status === "error" ? "red" : status === "complete" ? "green" : ""}>
        {STATUS_LABEL[status]}
        {runId && status !== "connecting" && <span className="dim"> ({runId})</span>}
      </p>
      {errorMessage && <p className="red">{errorMessage}</p>}
      {runId && (status === "running" || status === "connecting" || status === "awaiting_human") && (
        <Link to={`/runs/${runId}`} className="btn-primary" data-testid="run-open-dashboard">
          Open dashboard
        </Link>
      )}
    </div>
  );
}
