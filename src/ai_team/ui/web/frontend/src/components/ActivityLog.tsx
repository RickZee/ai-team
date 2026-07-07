import { useEffect, useMemo, useRef, useState } from "react";
import type { LogEntry } from "../types";
import { formatLogMessage, formatLogTime } from "../utils/formatLogMessage";

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
  const scrollRef = useRef<HTMLDivElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const [agentFilter, setAgentFilter] = useState("");
  const [enabledLevels, setEnabledLevels] = useState<Set<string>>(
    () => new Set(LEVELS),
  );
  const [search, setSearch] = useState("");
  const [autoScroll, setAutoScroll] = useState(true);
  const [showJumpLatest, setShowJumpLatest] = useState(false);

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

  const handleScroll = () => {
    const el = scrollRef.current;
    if (!el) return;
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 48;
    setShowJumpLatest(!atBottom);
    if (atBottom) setAutoScroll(true);
  };

  useEffect(() => {
    if (autoScroll && !showJumpLatest) {
      bottomRef.current?.scrollIntoView?.({ behavior: "smooth" });
    }
  }, [filtered.length, autoScroll, showJumpLatest]);

  const jumpToLatest = () => {
    setShowJumpLatest(false);
    setAutoScroll(true);
    bottomRef.current?.scrollIntoView?.({ behavior: "smooth" });
  };

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
              onChange={(e) => {
                setAutoScroll(e.target.checked);
                if (e.target.checked) setShowJumpLatest(false);
              }}
            />
            Auto-scroll
          </label>
          <button type="button" className="btn-secondary btn-sm" onClick={jumpToGuardrail}>
            Last alert
          </button>
        </div>
      )}
      <div
        ref={scrollRef}
        className="activity-log"
        aria-live={ariaLive}
        aria-relevant="additions"
        onScroll={handleScroll}
      >
        {filtered.map((entry, i) => {
          const display = formatLogMessage(entry.message);
          const ts = formatLogTime(entry.timestamp);
          return (
            <div
              key={i}
              className={`log-line ${LEVEL_CLASS[entry.level] || "log-info"}`}
              title={entry.message}
            >
              <span className="log-ts">{ts}</span>
              <span className="log-sep" aria-hidden>
                ·
              </span>
              {entry.agent && (
                <>
                  <span className="log-agent-tag">{entry.agent}</span>
                  <span className="log-sep" aria-hidden>
                    ·
                  </span>
                </>
              )}
              <span className="log-msg">{display}</span>
            </div>
          );
        })}
        <div ref={bottomRef} />
      </div>
      {showJumpLatest && (
        <button
          type="button"
          className="btn-secondary btn-sm log-jump-latest"
          onClick={jumpToLatest}
          data-testid="log-jump-latest"
        >
          Jump to latest
        </button>
      )}
    </div>
  );
}
