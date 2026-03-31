import { useEffect, useRef } from "react";
import type { LogEntry } from "../types";

const LEVEL_CLASS: Record<string, string> = {
  error: "log-error",
  warn: "log-warn",
  success: "log-success",
  info: "log-info",
};

export function ActivityLog({ entries }: { entries: LogEntry[] }) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [entries.length]);

  if (entries.length === 0) {
    return <div className="empty-state">Waiting for activity...</div>;
  }

  return (
    <div className="activity-log">
      {entries.map((entry, i) => {
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
  );
}
