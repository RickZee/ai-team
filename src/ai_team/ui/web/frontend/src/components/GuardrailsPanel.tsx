import type { GuardrailEvent } from "../types";
import { EmptyState } from "./EmptyState";

const STATUS_ICON: Record<string, string> = {
  pass: "✓",
  fail: "✗",
  warn: "⚠",
};

const STATUS_CLASS: Record<string, string> = {
  pass: "gr-pass",
  fail: "gr-fail",
  warn: "gr-warn",
};

export function GuardrailsPanel({
  events,
  terminal = false,
}: {
  events: GuardrailEvent[];
  terminal?: boolean;
}) {
  if (events.length === 0) {
    return (
      <EmptyState
        title={
          terminal
            ? "No guardrail events recorded for this run"
            : "No guardrail checks yet"
        }
        hint={terminal ? undefined : "Checks appear as agents run."}
        testId="guardrails-empty"
        className="empty-state"
      />
    );
  }

  return (
    <div className="guardrails-panel">
      {events.map((evt, i) => {
        const ts = new Date(evt.timestamp).toLocaleTimeString();
        return (
          <div key={i} className={`gr-line ${STATUS_CLASS[evt.status]}`}>
            <span className="gr-ts">{ts}</span>
            <span className="gr-icon">{STATUS_ICON[evt.status]}</span>
            <span className="gr-cat">[{evt.category.slice(0, 3).toUpperCase()}]</span>
            <span className="gr-name">{evt.name}</span>
            {evt.message && evt.status !== "pass" && <span className="gr-msg"> — {evt.message}</span>}
          </div>
        );
      })}
    </div>
  );
}
