import { useMemo, useState } from "react";
import type { RunInfo } from "../types";
import { formatRunDate, groupRunsByDay } from "../utils/formatRun";

interface RunListProps {
  runs: RunInfo[];
  selectedRunId: string | null;
  onSelect: (runId: string) => void;
  onDelete?: (runId: string) => void;
}

const TERMINAL = new Set(["complete", "error", "cancelled"]);

/** Filterable, searchable run sidebar list grouped by day. */
export function RunList({ runs, selectedRunId, onSelect, onDelete }: RunListProps) {
  const [statusFilter, setStatusFilter] = useState("");
  const [search, setSearch] = useState("");
  const [expandedBrief, setExpandedBrief] = useState<string | null>(null);

  const filtered = useMemo(() => {
    const q = search.toLowerCase().trim();
    return runs.filter((r) => {
      if (statusFilter && r.status !== statusFilter) return false;
      if (q) {
        const hay = `${r.description} ${r.backend} ${r.run_id}`.toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });
  }, [runs, statusFilter, search]);

  const groups = useMemo(() => groupRunsByDay(filtered), [filtered]);

  return (
    <div className="run-list-panel" data-testid="run-list">
      <div className="run-list-controls">
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          aria-label="Filter by status"
          data-testid="run-list-status-filter"
        >
          <option value="">All statuses</option>
          <option value="running">Running</option>
          <option value="awaiting_human">Awaiting human</option>
          <option value="complete">Complete</option>
          <option value="error">Error</option>
          <option value="cancelled">Cancelled</option>
        </select>
        <input
          type="search"
          placeholder="Search runs…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          aria-label="Search runs"
          data-testid="run-list-search"
        />
      </div>
      {filtered.length === 0 ? (
        <p className="dim">No matching runs</p>
      ) : (
        groups.map((group) => (
          <div key={group.label} className="run-list-day-group">
            <h4 className="run-list-day-header">{group.label}</h4>
            <ul className="run-list">
              {group.runs.map((r) => (
                <li key={r.run_id}>
                  <div
                    className={`run-list-item-wrap ${r.run_id === selectedRunId ? "active" : ""}`}
                  >
                    <button
                      type="button"
                      className="run-list-item"
                      onClick={() => onSelect(r.run_id)}
                      data-testid={`run-item-${r.run_id}`}
                    >
                      <span className="run-list-date">{formatRunDate(r.started_at)}</span>
                      <span
                        className="run-list-assignment"
                        onClick={(e) => {
                          e.stopPropagation();
                          setExpandedBrief((prev) => (prev === r.run_id ? null : r.run_id));
                        }}
                        data-testid={`run-brief-${r.run_id}`}
                      >
                        {expandedBrief === r.run_id
                          ? r.description || "No assignment"
                          : (r.description || "No assignment").slice(0, 40) +
                            ((r.description?.length ?? 0) > 40 ? "…" : "")}
                      </span>
                      <span className="run-list-meta">
                        <span className={`status-chip status-${r.status}`}>{r.status}</span>
                        {r.is_sample && (
                          <span className="run-list-sample-tag" data-testid={`sample-tag-${r.run_id}`}>
                            Sample
                          </span>
                        )}
                        <span className="run-list-backend">{r.backend}</span>
                      </span>
                    </button>
                    {onDelete && TERMINAL.has(r.status) && (
                      <button
                        type="button"
                        className="btn-secondary btn-sm run-list-delete"
                        onClick={() => onDelete(r.run_id)}
                        aria-label={`Delete run ${r.run_id}`}
                        data-testid={`delete-run-${r.run_id}`}
                      >
                        Delete
                      </button>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          </div>
        ))
      )}
    </div>
  );
}
