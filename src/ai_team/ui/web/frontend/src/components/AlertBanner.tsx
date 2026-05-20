interface AlertBannerProps {
  variant?: "error" | "warning" | "info";
  message: string;
  onDismiss?: () => void;
  testId?: string;
}

export function AlertBanner({
  variant = "error",
  message,
  onDismiss,
  testId,
}: AlertBannerProps) {
  if (!message) return null;
  return (
    <div className={`alert-banner alert-${variant}`} data-testid={testId ?? `alert-${variant}`}>
      <span>{message}</span>
      {onDismiss && (
        <button type="button" className="alert-dismiss" onClick={onDismiss} aria-label="Dismiss">
          ×
        </button>
      )}
    </div>
  );
}
