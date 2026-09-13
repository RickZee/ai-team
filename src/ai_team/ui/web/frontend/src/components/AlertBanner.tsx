import { X } from "lucide-react";

interface AlertBannerProps {
  variant?: "error" | "warning" | "info";
  message: string;
  onDismiss?: () => void;
  testId?: string;
  roleOverride?: "alert" | "status";
}

export function AlertBanner({
  variant = "error",
  message,
  onDismiss,
  testId,
  roleOverride,
}: AlertBannerProps) {
  if (!message) return null;
  const role = roleOverride ?? (variant === "error" ? "alert" : "status");
  return (
    <div
      className={`alert-banner alert-${variant}`}
      role={role}
      data-testid={testId ?? `alert-${variant}`}
    >
      <span>{message}</span>
      {onDismiss && (
        <button type="button" className="alert-dismiss" onClick={onDismiss} aria-label="Dismiss">
          <X className="icon-sm" aria-hidden="true" />
        </button>
      )}
    </div>
  );
}
