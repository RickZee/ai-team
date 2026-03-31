import { useState } from "react";
import { ActivityLog } from "../components/ActivityLog";
import { AgentTable } from "../components/AgentTable";
import { MetricsCard } from "../components/MetricsCard";
import { PhasePipeline } from "../components/PhasePipeline";
import { postDemo, postEstimate } from "../hooks/useApi";
import { useRunWebSocket } from "../hooks/useWebSocket";
import type { CostEstimate } from "../types";

export function Run() {
  const [backend, setBackend] = useState("langgraph");
  const [profile, setProfile] = useState("full");
  const [description, setDescription] = useState("");
  const [complexity, setComplexity] = useState("medium");
  const [estimate, setEstimate] = useState<CostEstimate | null>(null);

  const { monitor, runId, status, startRun } = useRunWebSocket();

  const handleRun = () => {
    if (!description.trim()) return;
    startRun(backend, profile, description, complexity);
  };

  const handleEstimate = async () => {
    try {
      const est = await postEstimate(complexity);
      setEstimate(est);
    } catch (e) {
      console.error(e);
    }
  };

  const handleDemo = async () => {
    try {
      await postDemo();
    } catch (e) {
      console.error(e);
    }
  };

  return (
    <div className="run-page">
      <div className="run-form">
        <h2>Run Pipeline</h2>
        <div className="form-grid">
          <div className="form-group">
            <label>Backend</label>
            <select value={backend} onChange={(e) => setBackend(e.target.value)}>
              <option value="langgraph">LangGraph</option>
              <option value="crewai">CrewAI</option>
            </select>
          </div>
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
        <div className="form-actions">
          <button className="btn-primary" onClick={handleRun} disabled={status === "running"}>
            {status === "running" ? "Running..." : "Run"}
          </button>
          <button className="btn-secondary" onClick={handleEstimate}>
            Estimate Cost
          </button>
          <button className="btn-warning" onClick={handleDemo}>
            Demo
          </button>
        </div>
      </div>

      {estimate && (
        <div className="panel estimate-panel">
          <h3>Cost Estimate ({estimate.complexity})</h3>
          <table className="estimate-table">
            <thead>
              <tr>
                <th>Role</th>
                <th>Model</th>
                <th>Input Tokens</th>
                <th>Output Tokens</th>
                <th>Cost</th>
              </tr>
            </thead>
            <tbody>
              {estimate.rows.map((r) => (
                <tr key={r.role}>
                  <td>{r.role}</td>
                  <td>{r.model_id}</td>
                  <td>{r.input_tokens.toLocaleString()}</td>
                  <td>{r.output_tokens.toLocaleString()}</td>
                  <td>${r.cost_usd.toFixed(4)}</td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr>
                <td colSpan={4}>Total (with 20% buffer)</td>
                <td className={estimate.within_budget ? "green" : "red"}>${estimate.total_usd.toFixed(4)}</td>
              </tr>
            </tfoot>
          </table>
        </div>
      )}

      {monitor && (
        <div className="run-monitor">
          <PhasePipeline phase={monitor.phase} />
          <div className="run-monitor-grid">
            <div className="panel">
              <h3>Agents</h3>
              <AgentTable agents={monitor.agents} />
            </div>
            <div className="panel">
              <h3>Metrics</h3>
              <MetricsCard metrics={monitor.metrics} elapsed={monitor.elapsed} />
            </div>
          </div>
          <div className="panel">
            <h3>Activity Log</h3>
            <ActivityLog entries={monitor.log} />
          </div>
        </div>
      )}

      {status === "complete" && (
        <div className="run-complete">
          <span className="green">Run complete</span> {runId && <span className="dim">({runId})</span>}
        </div>
      )}
      {status === "error" && <div className="run-error">Run failed</div>}
    </div>
  );
}
