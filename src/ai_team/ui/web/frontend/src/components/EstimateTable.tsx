import type { CostEstimate } from "../types";

interface EstimateTableProps {
  estimate: CostEstimate;
  /** Multiply single-run total for compare pre-flight (e.g. 3 backends). */
  runMultiplier?: number;
}

export function EstimateTable({ estimate, runMultiplier = 1 }: EstimateTableProps) {
  const total = estimate.total_usd * runMultiplier;

  return (
    <table className="estimate-table" data-testid="estimate-table">
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
          <td colSpan={4}>
            Total (with 20% buffer)
            {runMultiplier > 1 ? ` × ${runMultiplier} runs` : ""}
          </td>
          <td className={estimate.within_budget ? "green" : "red"}>${total.toFixed(4)}</td>
        </tr>
      </tfoot>
    </table>
  );
}
