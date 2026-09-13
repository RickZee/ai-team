import {
  Bar,
  BarChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { TestsPanelData } from "../types";
import { EmptyState } from "./EmptyState";
import { LoadingState } from "./LoadingState";

interface TestResultsPanelProps {
  data: TestsPanelData | null;
  loading: boolean;
}

export function TestResultsPanel({ data, loading }: TestResultsPanelProps) {
  if (loading) return <LoadingState label="Loading test results…" />;
  if (!data || data.source === "empty") {
    return (
      <EmptyState
        title="No structured test results found"
        hint="Run QA phase or check pytest.txt in the bundle."
      />
    );
  }

  const coveragePct = Math.round((data.coverage_line || 0) * 100);
  const chartData = (data.per_file_coverage || [])
    .filter((f) => f.path)
    .map((f) => ({
      name: f.path.split("/").pop() || f.path,
      coverage: Math.round(f.line_coverage * 100),
    }))
    .slice(0, 12);

  return (
    <div className="tests-panel" data-testid="tests-panel">
      <div className="test-badges">
        <span className="chip chip-md chip-success">{data.passed} passed</span>
        <span className="chip chip-md chip-danger">{data.failed} failed</span>
        {data.errors > 0 && <span className="chip chip-md chip-danger">{data.errors} errors</span>}
        {data.skipped > 0 && <span className="chip chip-md chip-warning">{data.skipped} skipped</span>}
        <span className="chip chip-md chip-accent">{coveragePct}% line coverage</span>
        {data.duration_seconds > 0 && (
          <span className="chip chip-md chip-neutral">{data.duration_seconds.toFixed(1)}s</span>
        )}
      </div>
      {data.source && <p className="artifact-source">Source: {data.source}</p>}

      {chartData.length > 0 && (
        <div
          className="coverage-chart"
          role="img"
          aria-label={`Per-file line coverage. Overall ${coveragePct} percent.`}
        >
          <h3 className="panel-header">Per-file coverage</h3>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={chartData} layout="vertical" margin={{ left: 8, right: 8 }}>
              <XAxis type="number" domain={[0, 100]} unit="%" stroke="var(--fg-muted)" tick={{ fill: "var(--fg-muted)", fontSize: "var(--text-xs)" }} />
              <YAxis type="category" dataKey="name" width={100} stroke="var(--fg-muted)" tick={{ fill: "var(--fg-muted)", fontSize: "var(--text-xs)" }} />
              <Tooltip
                contentStyle={{
                  background: "var(--bg-surface)",
                  border: "1px solid var(--border-default)",
                  color: "var(--fg-default)",
                }}
                itemStyle={{ color: "var(--fg-default)" }}
              />
              <Bar dataKey="coverage" fill="var(--intent-accent)" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {data.failures.length > 0 && (
        <div className="test-failures">
          <h3 className="panel-header">Failures</h3>
          {data.failures.map((f) => (
            <div key={f.test_name} className="failure-card">
              <div className="failure-title">{f.test_name}</div>
              {f.error && (
                <pre className="failure-error" tabIndex={0} aria-label="Failure error">
                  {f.error}
                </pre>
              )}
              {f.traceback && (
                <pre className="failure-trace" tabIndex={0} aria-label="Failure traceback">
                  {f.traceback}
                </pre>
              )}
              <p className="text-muted">Re-run from the CLI: uv run pytest</p>
            </div>
          ))}
        </div>
      )}

      {data.raw_pytest && (
        <details className="pytest-raw">
          <summary>pytest output</summary>
          <pre>{data.raw_pytest}</pre>
        </details>
      )}
    </div>
  );
}
