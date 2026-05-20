import { useEffect, useRef, useState } from "react";
import { postResume } from "../hooks/useApi";
import { AlertBanner } from "./AlertBanner";

interface HumanReviewPanelProps {
  runId: string;
  payload: Record<string, unknown> | null;
  backend?: string;
  onResumed?: () => void;
}

function payloadText(payload: Record<string, unknown> | null, key: string): string | null {
  if (!payload) return null;
  const v = payload[key];
  if (v == null) return null;
  return typeof v === "string" ? v : JSON.stringify(v);
}

export function HumanReviewPanel({ runId, payload, backend, onResumed }: HumanReviewPanelProps) {
  const [feedback, setFeedback] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showRaw, setShowRaw] = useState(false);
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    panelRef.current?.querySelector<HTMLTextAreaElement>("textarea")?.focus();
  }, [runId]);

  const applyPreset = (text: string) => setFeedback(text);

  const handleSubmit = async () => {
    const text = feedback.trim();
    if (!text) return;
    setSubmitting(true);
    setError(null);
    try {
      await postResume(runId, text);
      setFeedback("");
      onResumed?.();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Resume failed");
    } finally {
      setSubmitting(false);
    }
  };

  const phase = payloadText(payload, "phase") ?? payloadText(payload, "current_phase");
  const reason =
    payloadText(payload, "reason") ??
    payloadText(payload, "message") ??
    payloadText(payload, "review_reason");
  const threadId = payloadText(payload, "thread_id");

  const pauseCopy =
    backend === "langgraph"
      ? "LangGraph paused at a checkpoint for your decision."
      : "This run is paused and waiting for your review.";

  return (
    <div
      ref={panelRef}
      className="panel hitl-panel"
      data-testid="hitl-panel"
      role="region"
      aria-label="Human review"
    >
      <h3>Human review required</h3>
      <p className="dim">{pauseCopy}</p>

      <div className="hitl-context">
        {phase && (
          <p>
            <span className="run-meta-label">Phase</span> {phase}
          </p>
        )}
        {reason && (
          <p>
            <span className="run-meta-label">Reason</span> {reason}
          </p>
        )}
        {threadId && (
          <p className="dim">
            <span className="run-meta-label">Thread</span> {threadId}
          </p>
        )}
      </div>

      <div className="hitl-presets">
        <button
          type="button"
          className="btn-secondary btn-sm"
          onClick={() => applyPreset("Approved. Proceed with the current plan.")}
          data-testid="hitl-approve"
        >
          Approve
        </button>
        <button
          type="button"
          className="btn-secondary btn-sm"
          onClick={() =>
            applyPreset("Request changes: please revise the approach before continuing.")
          }
          data-testid="hitl-changes"
        >
          Request changes
        </button>
        <button
          type="button"
          className="btn-secondary btn-sm"
          onClick={() => applyPreset("Rejected. Stop and summarize blockers.")}
          data-testid="hitl-reject"
        >
          Reject
        </button>
      </div>

      <textarea
        value={feedback}
        onChange={(e) => setFeedback(e.target.value)}
        placeholder="Enter approval, changes, or guidance…"
        rows={3}
        data-testid="hitl-feedback"
      />
      <button
        type="button"
        className="btn-primary"
        onClick={handleSubmit}
        disabled={submitting || !feedback.trim()}
        data-testid="hitl-submit"
      >
        {submitting ? "Resuming…" : "Submit & Resume"}
      </button>
      {error && <AlertBanner message={error} onDismiss={() => setError(null)} />}

      {payload && (
        <details className="hitl-raw-details">
          <summary>Advanced: raw payload</summary>
          <button
            type="button"
            className="btn-secondary btn-sm"
            onClick={() => setShowRaw((v) => !v)}
          >
            {showRaw ? "Hide" : "Show"} JSON
          </button>
          {showRaw && <pre className="hitl-payload">{JSON.stringify(payload, null, 2)}</pre>}
        </details>
      )}
    </div>
  );
}
