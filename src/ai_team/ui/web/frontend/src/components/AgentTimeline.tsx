import type { AgentState, MonitorState } from "../types";

const PHASES = ["intake", "planning", "development", "testing", "deployment"] as const;

const AGENT_ICONS: Record<string, string> = {
  manager: "🎯",
  product_owner: "📋",
  architect: "🏗",
  backend_developer: "⚙",
  frontend_developer: "🎨",
  fullstack_developer: "🔧",
  qa_engineer: "🧪",
  devops: "🚀",
  cloud_engineer: "☁",
};

function statusLabel(status: AgentState["status"]): string {
  switch (status) {
    case "working":
      return "Active";
    case "done":
      return "Done";
    case "error":
      return "Error";
    default:
      return "Idle";
  }
}

interface AgentTimelineProps {
  monitor: MonitorState;
  showTable?: boolean;
  onToggleTable?: () => void;
}

/** Horizontal agent handoff timeline derived from monitor state. */
export function AgentTimeline({ monitor, showTable, onToggleTable }: AgentTimelineProps) {
  const agents = Object.values(monitor.agents);
  const currentPhaseIdx = PHASES.indexOf(monitor.phase as (typeof PHASES)[number]);
  const activeAgent = agents.find((a) => a.status === "working");

  return (
    <div className="agent-timeline panel" data-testid="agent-timeline">
      <div className="agent-timeline-header">
        <h3>Agent timeline</h3>
        {onToggleTable && (
          <button type="button" className="btn-secondary btn-sm" onClick={onToggleTable}>
            {showTable ? "Hide table" : "Show table"}
          </button>
        )}
      </div>
      <div className="agent-timeline-phases" aria-label="Pipeline phases">
        {PHASES.map((phase, i) => {
          let cls = "agent-timeline-phase";
          if (monitor.phase === phase) cls += " active";
          else if (currentPhaseIdx >= 0 && i < currentPhaseIdx) cls += " done";
          return (
            <span key={phase} className={cls}>
              {phase}
            </span>
          );
        })}
      </div>
      {monitor.metrics.retries > 0 && (
        <p className="self-correct-badge" data-testid="self-correct-badge">
          ✓ Self-corrected ×{monitor.metrics.retries}
        </p>
      )}
      {activeAgent && (
        <p className="agent-timeline-owner">
          Current owner: <strong>{activeAgent.role.replace(/_/g, " ")}</strong>
        </p>
      )}
      <ul className="agent-timeline-rows">
        {agents.length === 0 ? (
          <li className="dim">Waiting for agents…</li>
        ) : (
          agents.map((agent) => (
            <li
              key={agent.role}
              className={`agent-timeline-row status-${agent.status}`}
              data-testid={`timeline-agent-${agent.role}`}
            >
              <span className="agent-timeline-icon">{AGENT_ICONS[agent.role] ?? "🤖"}</span>
              <span className="agent-timeline-role">{agent.role.replace(/_/g, " ")}</span>
              <span className={`status-chip status-${agent.status}`}>{statusLabel(agent.status)}</span>
              {agent.current_task && (
                <span className="agent-timeline-task dim">{agent.current_task}</span>
              )}
            </li>
          ))
        )}
      </ul>
    </div>
  );
}
