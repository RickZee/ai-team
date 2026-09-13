import type { ReactNode } from "react";

interface EmptyStateProps {
  title: string;
  hint?: string;
  icon?: ReactNode;
  action?: ReactNode;
  testId?: string;
  className?: string;
}

/** Shared empty-state pattern: what happened, why, one next action. */
export function EmptyState({
  title,
  hint,
  icon,
  action,
  testId,
  className = "",
}: EmptyStateProps) {
  return (
    <div className={["empty-state-block", className].filter(Boolean).join(" ")} data-testid={testId}>
      {icon && (
        <span className="empty-state-icon" aria-hidden>
          {icon}
        </span>
      )}
      <p className="empty-state-title">{title}</p>
      {hint && <p className="empty-state-hint text-muted">{hint}</p>}
      {action && <div className="empty-state-action">{action}</div>}
    </div>
  );
}
