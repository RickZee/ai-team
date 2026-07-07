import type { AgentState, MonitorState } from "../types";

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
  terminal?: boolean;
}

/** Agent activity lanes — phase pipeline lives in the sticky header (IA-2). */
export function AgentTimeline({
  monitor,
  showTable,
  onToggleTable,
  terminal = false,
}: AgentTimelineProps) {
  const agents = Object.values(monitor.agents);
  const activeAgent = terminal ? undefined : agents.find((a) => a.status === "working");

  if (agents.length === 0) {
    return null;
  }

  return (
    <div className="agent-timeline panel" data-testid="agent-timeline">
      <div className="agent-timeline-header panel-header-row">
        <h3 className="panel-header">Agent timeline</h3>
        {onToggleTable && (
          <button type="button" className="btn-secondary btn-sm" onClick={onToggleTable}>
            {showTable ? "Hide table" : "Show table"}
          </button>
        )}
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
        {agents.map((agent) => (
          <li
            key={agent.role}
            className={`agent-timeline-row status-${agent.status}`}
            data-testid={`timeline-agent-${agent.role}`}
          >
            <span className="agent-timeline-icon">{AGENT_ICONS[agent.role] ?? "🤖"}</span>
            <span className="agent-timeline-role">{agent.role.replace(/_/g, " ")}</span>
            <span className={`chip chip-sm status-chip status-${agent.status}`}>
              {statusLabel(agent.status)}
            </span>
            {agent.current_task && (
              <span className="agent-timeline-task dim">{agent.current_task}</span>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}

/** One-line note when no agents are reported (V-3). */
export function AgentTimelineNote({ terminal }: { terminal?: boolean }) {
  return (
    <p className="agent-timeline-note dim" data-testid="agent-timeline-note">
      {terminal
        ? "No agent activity recorded for this run"
        : "No agent activity reported by this backend"}
    </p>
  );
}
