import {
  Bot,
  Building2,
  ClipboardList,
  Cloud,
  FlaskConical,
  Palette,
  Rocket,
  Settings,
  Target,
  Wrench,
} from "lucide-react";
import type { AgentState } from "../types";
import { EmptyState } from "./EmptyState";

const AGENT_ICONS: Record<string, typeof Bot> = {
  manager: Target,
  product_owner: ClipboardList,
  architect: Building2,
  backend_developer: Settings,
  frontend_developer: Palette,
  fullstack_developer: Wrench,
  qa_engineer: FlaskConical,
  devops: Rocket,
  cloud_engineer: Cloud,
};

const STATUS_CLASS: Record<string, string> = {
  working: "status-active",
  done: "status-done",
  error: "status-error",
  idle: "status-idle",
};

const STATUS_LABEL: Record<string, string> = {
  working: "Active",
  done: "Done",
  error: "Error",
  idle: "Idle",
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
          const Icon = AGENT_ICONS[role] ?? Bot;
          return (
          <tr key={role} className={status === "working" ? "agent-row-active" : undefined}>
            <td className="agent-name">
              <Icon className="icon-sm" aria-hidden="true" /> {role.replace(/_/g, " ")}
            </td>
            <td className={STATUS_CLASS[status] || "status-idle"}>
              {STATUS_LABEL[status] || "Idle"}
            </td>
            <td className="agent-model text-muted">{agent.model || "—"}</td>
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
