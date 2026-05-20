interface LoadingStateProps {
  label?: string;
  testId?: string;
}

export function LoadingState({ label = "Loading…", testId = "loading-state" }: LoadingStateProps) {
  return (
    <div className="loading-state" data-testid={testId}>
      <span className="loading-spinner" aria-hidden />
      <span>{label}</span>
    </div>
  );
}
