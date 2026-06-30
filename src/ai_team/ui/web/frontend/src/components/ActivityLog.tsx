import { useEffect, useMemo, useRef, useState } from "react";
import type { LogEntry } from "../types";

const LEVEL_CLASS: Record<string, string> = {
  error: "log-error",
  warn: "log-warn",
  success: "log-success",
  info: "log-info",
};

const LEVELS = ["info", "success", "warn", "error"] as const;

export function ActivityLog({
  entries,
  compact = false,
  ariaLive,
}: {
  entries: LogEntry[];
  compact?: boolean;
  ariaLive?: "polite" | "off";
}) {
  const bottomRef = useRef<HTMLDivElement>(null);
  const [agentFilter, setAgentFilter] = useState("");
  const [enabledLevels, setEnabledLevels] = useState<Set<string>>(
    () => new Set(LEVELS),
  );
  const [search, setSearch] = useState("");
  const [autoScroll, setAutoScroll] = useState(true);

  const agents = useMemo(
    () => [...new Set(entries.map((e) => e.agent).filter(Boolean))].sort(),
    [entries],
  );

  const toggleLevel = (level: string) => {
    setEnabledLevels((prev) => {
      const next = new Set(prev);
      if (next.has(level)) next.delete(level);
      else next.add(level);
      return next;
    });
  };

  const filtered = useMemo(() => {
    return entries.filter((e) => {
      if (agentFilter && e.agent !== agentFilter) return false;
      if (!enabledLevels.has(e.level)) return false;
      if (search.trim()) {
        const q = search.toLowerCase();
        if (
          !e.message.toLowerCase().includes(q) &&
          !e.agent.toLowerCase().includes(q)
        ) {
          return false;
        }
      }
      return true;
    });
  }, [entries, agentFilter, enabledLevels, search]);

  useEffect(() => {
    if (autoScroll) bottomRef.current?.scrollIntoView?.({ behavior: "smooth" });
  }, [filtered.length, autoScroll]);

  const jumpToGuardrail = () => {
    const idx = [...filtered].reverse().findIndex((e) => e.level === "warn" || e.level === "error");
    if (idx < 0) return;
    const el = document.querySelectorAll(".activity-log .log-line")[filtered.length - 1 - idx];
    el?.scrollIntoView({ behavior: "smooth", block: "center" });
  };

  if (entries.length === 0) {
    return <div className="empty-state">Waiting for agent activity…</div>;
  }

  return (
    <div className={`activity-log-wrap ${compact ? "compact" : ""}`}>
      {!compact && (
        <div className="log-toolbar">
          <select
            value={agentFilter}
            onChange={(e) => setAgentFilter(e.target.value)}
            aria-label="Filter by agent"
          >
            <option value="">All agents</option>
            {agents.map((a) => (
              <option key={a} value={a}>
                {a}
              </option>
            ))}
          </select>
          <div className="log-level-toggles" role="group" aria-label="Filter by level">
            {LEVELS.map((level) => (
              <button
                key={level}
                type="button"
                className={`btn-secondary btn-sm log-level-toggle ${enabledLevels.has(level) ? "active" : ""}`}
                aria-pressed={enabledLevels.has(level)}
                onClick={() => toggleLevel(level)}
                data-testid={`log-level-${level}`}
              >
                {level}
              </button>
            ))}
          </div>
          <input
            type="search"
            placeholder="Search log…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            aria-label="Search activity log"
            data-testid="log-search"
          />
          <label className="log-autoscroll">
            <input
              type="checkbox"
              checked={autoScroll}
              onChange={(e) => setAutoScroll(e.target.checked)}
            />
            Auto-scroll
          </label>
          <button type="button" className="btn-secondary btn-sm" onClick={jumpToGuardrail}>
            Last alert
          </button>
        </div>
      )}
      <div
        className="activity-log"
        aria-live={ariaLive}
        aria-relevant="additions"
      >
        {filtered.map((entry, i) => {
          const ts = new Date(entry.timestamp).toLocaleTimeString();
          return (
            <div key={i} className={`log-line ${LEVEL_CLASS[entry.level] || "log-info"}`}>
              <span className="log-ts">{ts}</span>
              <span className="log-agent">{entry.agent}</span>
              <span className="log-msg">{entry.message}</span>
            </div>
          );
        })}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
