import { useEffect, useState } from "react";
import { ActivityLog } from "../components/ActivityLog";
import { AgentTable } from "../components/AgentTable";
import { GuardrailsPanel } from "../components/GuardrailsPanel";
import { MetricsCard } from "../components/MetricsCard";
import { PhasePipeline } from "../components/PhasePipeline";
import { useMonitorWebSocket } from "../hooks/useWebSocket";
import { getRuns } from "../hooks/useApi";
import type { MonitorState } from "../types";

export function Dashboard() {
  const [activeRunId, setActiveRunId] = useState<string | null>(null);
  const liveMonitor = useMonitorWebSocket(activeRunId);

  // Poll for active runs
  useEffect(() => {
    const poll = async () => {
      try {
        const data = await getRuns();
        const running = data.runs.find((r) => r.status === "running");
        if (running) setActiveRunId(running.run_id);
      } catch {
        // server not up yet
      }
    };
    poll();
    const id = setInterval(poll, 2000);
    return () => clearInterval(id);
  }, []);

  const monitor: MonitorState | null = liveMonitor;

  if (!monitor) {
    return (
      <div className="dashboard-empty">
        <h2>No Active Run</h2>
        <p>Start a run from the Run tab, or launch a demo to see the dashboard in action.</p>
      </div>
    );
  }

  return (
    <div className="dashboard">
      <div className="dashboard-header">
        <PhasePipeline phase={monitor.phase} />
      </div>
      <div className="dashboard-grid">
        <div className="panel agents">
          <h3>Agents</h3>
          <AgentTable agents={monitor.agents} />
        </div>
        <div className="panel metrics">
          <h3>Metrics</h3>
          <MetricsCard metrics={monitor.metrics} elapsed={monitor.elapsed} />
        </div>
        <div className="panel log">
          <h3>Activity Log</h3>
          <ActivityLog entries={monitor.log} />
        </div>
        <div className="panel guardrails">
          <h3>Guardrails</h3>
          <GuardrailsPanel events={monitor.guardrail_events} />
        </div>
      </div>
    </div>
  );
}
