import type { AgentState } from "../types";
import { EmptyState } from "./EmptyState";

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

export function AgentTable({
  agents,
  terminal = false,
}: {
  agents: Record<string, AgentState>;
  terminal?: boolean;
}) {
  const entries = Object.entries(agents);

  if (entries.length === 0) {
    return (
      <EmptyState
        title={
          terminal
            ? "No agent activity recorded for this run"
            : "Waiting for agents to join the run"
        }
        testId="agent-table-empty"
        className="empty-state"
      />
    );
  }

  const displayStatus = (status: AgentState["status"]) =>
    terminal && status === "working" ? "done" : status;

  return (
    <table className="agent-table">
      <thead>
        <tr>
          <th>Agent</th>
          <th>Status</th>
          <th>Model</th>
          <th>Task</th>
          <th>Done</th>
        </tr>
      </thead>
      <tbody>
        {entries.map(([role, agent]) => {
          const status = displayStatus(agent.status);
          return (
          <tr key={role} className={status === "working" ? "agent-row-active" : undefined}>
            <td className="agent-name">
              {ICONS[role] || "\ud83e\udd16"} {role.replace(/_/g, " ")}
            </td>
            <td className={STATUS_CLASS[status] || "status-idle"}>
              {STATUS_LABEL[status] || "○ IDLE"}
            </td>
            <td className="agent-model dim">{agent.model || "—"}</td>
            <td className="agent-task" title={agent.current_task}>
              {agent.current_task || (agent.status === "done" ? "(finished)" : "—")}
            </td>
            <td className="agent-done">{agent.tasks_completed}</td>
          </tr>
        );
        })}
      </tbody>
    </table>
  );
}
