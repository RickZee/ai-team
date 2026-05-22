import {
  Bar,
  BarChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { TestsPanelData } from "../types";

interface TestResultsPanelProps {
  data: TestsPanelData | null;
  loading: boolean;
}

export function TestResultsPanel({ data, loading }: TestResultsPanelProps) {
  if (loading) return <div className="empty-state">Loading test results…</div>;
  if (!data || data.source === "empty") {
    return (
      <div className="empty-state">
        No structured test results found. Run QA phase or check pytest.txt in the bundle.
      </div>
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
        <span className="badge badge-pass">{data.passed} passed</span>
        <span className="badge badge-fail">{data.failed} failed</span>
        {data.errors > 0 && <span className="badge badge-fail">{data.errors} errors</span>}
        {data.skipped > 0 && <span className="badge badge-warn">{data.skipped} skipped</span>}
        <span className="badge badge-info">{coveragePct}% line coverage</span>
        {data.duration_seconds > 0 && (
          <span className="badge badge-dim">{data.duration_seconds.toFixed(1)}s</span>
        )}
      </div>
      {data.source && <p className="artifact-source">Source: {data.source}</p>}

      {chartData.length > 0 && (
        <div className="coverage-chart">
          <h4>Per-file coverage</h4>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={chartData} layout="vertical" margin={{ left: 8, right: 8 }}>
              <XAxis type="number" domain={[0, 100]} unit="%" />
              <YAxis type="category" dataKey="name" width={100} tick={{ fontSize: 11 }} />
              <Tooltip />
              <Bar dataKey="coverage" fill="#58a6ff" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {data.failures.length > 0 && (
        <div className="test-failures">
          <h4>Failures</h4>
          {data.failures.map((f) => (
            <div key={f.test_name} className="failure-card">
              <div className="failure-title">{f.test_name}</div>
              {f.error && <pre className="failure-error">{f.error}</pre>}
              {f.traceback && <pre className="failure-trace">{f.traceback}</pre>}
              <button type="button" className="btn-secondary btn-sm" disabled title="Re-run requires CLI">
                Re-run (CLI)
              </button>
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
