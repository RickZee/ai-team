import type { AgentState } from "../types";

const ICONS: Record<string, string> = {
  manager: "\ud83d\udc54",
  product_owner: "\ud83d\udcdd",
  architect: "\ud83c\udfd7\ufe0f",
  backend_developer: "\u2699\ufe0f",
  frontend_developer: "\ud83c\udfa8",
  fullstack_developer: "\ud83d\udd28",
  devops: "\ud83d\udd27",
  cloud_engineer: "\u2601\ufe0f",
  qa_engineer: "\ud83d\udd0d",
};

const STATUS_CLASS: Record<string, string> = {
  working: "status-active",
  done: "status-done",
  error: "status-error",
  idle: "status-idle",
};

const STATUS_LABEL: Record<string, string> = {
  working: "● ACTIVE",
  done: "● DONE",
  error: "● ERROR",
  idle: "○ IDLE",
};

export function AgentTable({ agents }: { agents: Record<string, AgentState> }) {
  const entries = Object.entries(agents);

  if (entries.length === 0) {
    return <div className="empty-state">Waiting for agents...</div>;
  }

  return (
    <table className="agent-table">
      <thead>
        <tr>
          <th>Agent</th>
          <th>Status</th>
          <th>Task</th>
          <th>Done</th>
        </tr>
      </thead>
      <tbody>
        {entries.map(([role, agent]) => (
          <tr key={role}>
            <td className="agent-name">
              {ICONS[role] || "\ud83e\udd16"} {role.replace(/_/g, " ")}
            </td>
            <td className={STATUS_CLASS[agent.status] || "status-idle"}>
              {STATUS_LABEL[agent.status] || "○ IDLE"}
            </td>
            <td className="agent-task">{agent.current_task || "\u2014"}</td>
            <td className="agent-done">{agent.tasks_completed}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
