import { useId, useRef } from "react";
import { useFocusTrap } from "../hooks/useFocusTrap";

interface ConfirmModalProps {
  open: boolean;
  title: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  tone?: "default" | "danger";
  onConfirm: () => void;
  onCancel: () => void;
}

export function ConfirmModal({
  open,
  title,
  message,
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  tone = "default",
  onConfirm,
  onCancel,
}: ConfirmModalProps) {
  const cardRef = useRef<HTMLDivElement>(null);
  const titleId = useId();
  const descId = useId();
  useFocusTrap(open, cardRef, onCancel);

  if (!open) return null;

  return (
    <div
      className="modal-overlay"
      data-overlay
      role="dialog"
      aria-modal="true"
      aria-labelledby={titleId}
      aria-describedby={descId}
    >
      <div ref={cardRef} className="modal-card panel">
        <h2 id={titleId}>{title}</h2>
        <p className="modal-message" id={descId}>
          {message}
        </p>
        <div className="modal-actions">
          <button type="button" className="btn-secondary" onClick={onCancel}>
            {cancelLabel}
          </button>
          <button
            type="button"
            className={tone === "danger" ? "btn-danger" : "btn-primary"}
            onClick={onConfirm}
            data-testid="confirm-modal-ok"
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
