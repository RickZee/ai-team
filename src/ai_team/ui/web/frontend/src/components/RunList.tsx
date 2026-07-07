import { useMemo, useState, type ReactNode } from "react";
import type { RunInfo } from "../types";
import { formatRunTimeOfDay, groupRunsByDay } from "../utils/formatRun";
import { EmptyState } from "./EmptyState";

const INITIAL_CAP = 20;

interface RunListProps {
  runs: RunInfo[];
  selectedRunId: string | null;
  onSelect: (runId: string) => void;
  onDelete?: (runId: string) => void;
  /** Full-width home layout vs compact sidebar */
  variant?: "sidebar" | "home";
}

const TERMINAL = new Set(["complete", "error", "cancelled", "complete_approved"]);

/** Filterable run list grouped by day (V-2 card layout). */
export function RunList({
  runs,
  selectedRunId,
  onSelect,
  onDelete,
  variant = "sidebar",
}: RunListProps) {
  const [statusFilter, setStatusFilter] = useState("");
  const [search, setSearch] = useState("");
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(new Set());
  const [expandedComparisons, setExpandedComparisons] = useState<Set<string>>(new Set());

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

  const comparisonIds = useMemo(() => {
    const counts = new Map<string, number>();
    for (const r of filtered) {
      if (r.comparison_id) {
        counts.set(r.comparison_id, (counts.get(r.comparison_id) ?? 0) + 1);
      }
    }
    return new Set([...counts.entries()].filter(([, n]) => n > 1).map(([id]) => id));
  }, [filtered]);

  const renderCard = (r: RunInfo, inComparison?: boolean) => (
    <li key={r.run_id} className={inComparison ? "run-list-comparison-member" : undefined}>
      <div
        className={`run-list-item-wrap ${r.run_id === selectedRunId ? "active" : ""} ${inComparison ? "run-list-comparison-accent" : ""}`}
      >
        <button
          type="button"
          className="run-list-item"
          onClick={() => onSelect(r.run_id)}
          data-testid={`run-item-${r.run_id}`}
        >
          <div className="run-list-row1">
            <span className="run-list-time">{formatRunTimeOfDay(r.started_at)}</span>
            <span className={`chip chip-sm status-chip status-${r.status}`}>{r.status}</span>
            {r.comparison_id && comparisonIds.has(r.comparison_id) && (
              <span className="chip chip-sm run-list-comparison-chip" data-testid={`comparison-chip-${r.run_id}`}>
                ⚖ comparison
              </span>
            )}
            {r.is_sample && (
              <span className="chip chip-sm run-list-sample-tag" data-testid={`sample-tag-${r.run_id}`}>
                Sample
              </span>
            )}
            <span className="chip chip-sm run-list-backend">{r.backend}</span>
          </div>
          <p className="run-list-description" title={r.description || "No assignment"}>
            {r.description || "No assignment"}
          </p>
        </button>
        {onDelete && TERMINAL.has(r.status) && (
          <button
            type="button"
            className="run-list-delete-icon"
            onClick={() => onDelete(r.run_id)}
            aria-label={`Delete run ${r.run_id}`}
            data-testid={`delete-run-${r.run_id}`}
          >
            ✕
          </button>
        )}
      </div>
    </li>
  );

  const renderRuns = (dayRuns: RunInfo[]) => {
    const byComparison = new Map<string, RunInfo[]>();
    const singles: RunInfo[] = [];
    const seenComparisons = new Set<string>();

    for (const r of dayRuns) {
      if (r.comparison_id && comparisonIds.has(r.comparison_id)) {
        if (!byComparison.has(r.comparison_id)) byComparison.set(r.comparison_id, []);
        byComparison.get(r.comparison_id)!.push(r);
      } else {
        singles.push(r);
      }
    }

    const items: ReactNode[] = [];

    for (const [cid, members] of byComparison) {
      const expanded = expandedComparisons.has(cid);
      const preview = expanded ? members : members.slice(0, 1);
      items.push(
        <li key={`cmp-${cid}`} className="run-list-comparison-group">
          <button
            type="button"
            className="run-list-comparison-toggle btn-link"
            onClick={() =>
              setExpandedComparisons((prev) => {
                const next = new Set(prev);
                if (next.has(cid)) next.delete(cid);
                else next.add(cid);
                return next;
              })
            }
            data-testid={`comparison-group-${cid}`}
          >
            ⚖ Comparison · {members.length} backends {expanded ? "▾" : "▸"}
          </button>
          <ul className="run-list run-list-comparison-members">
            {preview.map((r) => renderCard(r, true))}
          </ul>
        </li>,
      );
      seenComparisons.add(cid);
    }

    for (const r of singles) {
      if (r.comparison_id && seenComparisons.has(r.comparison_id)) continue;
      items.push(renderCard(r));
    }

    return items;
  };

  return (
    <div className={`run-list-panel ${variant === "home" ? "run-list-home" : ""}`} data-testid="run-list">
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
      {runs.length === 0 ? (
        <EmptyState title="No runs yet" testId="run-list-empty" className="empty-state" />
      ) : filtered.length === 0 ? (
        <EmptyState
          title="No runs match"
          testId="run-list-empty-filtered"
          className="empty-state"
          action={
            <button
              type="button"
              className="btn-link"
              data-testid="run-list-clear-filters"
              onClick={() => {
                setStatusFilter("");
                setSearch("");
              }}
            >
              Clear filters
            </button>
          }
        />
      ) : (
        groups.map((group) => {
          const expanded = expandedGroups.has(group.label);
          const visibleRuns = expanded ? group.runs : group.runs.slice(0, INITIAL_CAP);
          const hiddenCount = group.runs.length - visibleRuns.length;
          return (
            <div key={group.label} className="run-list-day-group">
              <h4 className="run-list-day-header">{group.label}</h4>
              <ul className="run-list">{renderRuns(visibleRuns)}</ul>
              {hiddenCount > 0 && (
                <button
                  type="button"
                  className="btn-link run-list-show-all"
                  data-testid={`run-list-show-all-${group.label}`}
                  onClick={() => setExpandedGroups((prev) => new Set(prev).add(group.label))}
                >
                  Show all ({group.runs.length})
                </button>
              )}
            </div>
          );
        })
      )}
    </div>
  );
}
