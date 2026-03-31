import { useState } from "react";
import { ActivityLog } from "../components/ActivityLog";
import { AgentTable } from "../components/AgentTable";
import { MetricsCard } from "../components/MetricsCard";
import { PhasePipeline } from "../components/PhasePipeline";
import { useRunWebSocket } from "../hooks/useWebSocket";

export function Compare() {
  const [description, setDescription] = useState("");
  const [profile, setProfile] = useState("full");
  const [complexity, setComplexity] = useState("medium");

  const crewai = useRunWebSocket();
  const langgraph = useRunWebSocket();

  const handleCompare = () => {
    if (!description.trim()) return;
    crewai.startRun("crewai", profile, description, complexity);
    langgraph.startRun("langgraph", profile, description, complexity);
  };

  const isRunning = crewai.status === "running" || langgraph.status === "running";

  return (
    <div className="compare-page">
      <div className="compare-form">
        <h2>Compare Backends</h2>
        <div className="form-grid">
          <div className="form-group">
            <label>Team Profile</label>
            <input value={profile} onChange={(e) => setProfile(e.target.value)} placeholder="full" />
          </div>
          <div className="form-group">
            <label>Complexity</label>
            <select value={complexity} onChange={(e) => setComplexity(e.target.value)}>
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
          />
        </div>
        <button className="btn-primary" onClick={handleCompare} disabled={isRunning}>
          {isRunning ? "Comparing..." : "Run Both Backends"}
        </button>
      </div>

      <div className="compare-grid">
        <div className="compare-col">
          <h3 className="backend-title crewai-title">CrewAI</h3>
          {crewai.monitor ? (
            <>
              <PhasePipeline phase={crewai.monitor.phase} />
              <AgentTable agents={crewai.monitor.agents} />
              <MetricsCard metrics={crewai.monitor.metrics} elapsed={crewai.monitor.elapsed} />
              <ActivityLog entries={crewai.monitor.log} />
            </>
          ) : (
            <div className="empty-state">
              {crewai.status === "running" ? "Starting..." : "Not started"}
            </div>
          )}
        </div>
        <div className="compare-col">
          <h3 className="backend-title langgraph-title">LangGraph</h3>
          {langgraph.monitor ? (
            <>
              <PhasePipeline phase={langgraph.monitor.phase} />
              <AgentTable agents={langgraph.monitor.agents} />
              <MetricsCard metrics={langgraph.monitor.metrics} elapsed={langgraph.monitor.elapsed} />
              <ActivityLog entries={langgraph.monitor.log} />
            </>
          ) : (
            <div className="empty-state">
              {langgraph.status === "running" ? "Starting..." : "Not started"}
            </div>
          )}
        </div>
      </div>

      {crewai.monitor && langgraph.monitor && (
        <div className="compare-summary panel">
          <h3>Comparison Summary</h3>
          <table className="summary-table">
            <thead>
              <tr>
                <th>Metric</th>
                <th>CrewAI</th>
                <th>LangGraph</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>Elapsed</td>
                <td>{crewai.monitor.elapsed}</td>
                <td>{langgraph.monitor.elapsed}</td>
              </tr>
              <tr>
                <td>Tasks completed</td>
                <td>{crewai.monitor.metrics.tasks_completed}</td>
                <td>{langgraph.monitor.metrics.tasks_completed}</td>
              </tr>
              <tr>
                <td>Files generated</td>
                <td>{crewai.monitor.metrics.files_generated}</td>
                <td>{langgraph.monitor.metrics.files_generated}</td>
              </tr>
              <tr>
                <td>Guardrails passed</td>
                <td>{crewai.monitor.metrics.guardrails_passed}</td>
                <td>{langgraph.monitor.metrics.guardrails_passed}</td>
              </tr>
              <tr>
                <td>Retries</td>
                <td>{crewai.monitor.metrics.retries}</td>
                <td>{langgraph.monitor.metrics.retries}</td>
              </tr>
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
