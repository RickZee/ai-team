const PHASES = [
  "intake",
  "planning",
  "development",
  "testing",
  "deployment",
  "complete",
] as const;

const ICONS: Record<string, string> = {
  intake: "\u2b07",
  planning: "\ud83d\udccb",
  development: "\ud83d\udcbb",
  testing: "\ud83e\uddea",
  deployment: "\ud83d\ude80",
  complete: "\u2705",
  awaiting_human: "\ud83d\udc64",
  error: "\u274c",
};

export function PhasePipeline({
  phase,
  retries = 0,
}: {
  phase: string;
  retries?: number;
}) {
  const idx = PHASES.indexOf(phase as (typeof PHASES)[number]);
  const showHuman = phase === "awaiting_human";

  return (
    <div className="phase-pipeline" data-testid="phase-pipeline">
      {PHASES.map((p, i) => {
        let cls = "phase-step";
        if (phase === "error") cls += " phase-dim";
        else if (showHuman) cls += " phase-dim";
        else if (p === phase && p !== "complete") cls += " phase-active";
        else if (i < idx || (p === "complete" && phase === "complete")) cls += " phase-done";
        else cls += " phase-dim";

        return (
          <span key={p}>
            <span className={cls}>
              {ICONS[p]} {p.toUpperCase()}
            </span>
            {i < PHASES.length - 1 && <span className="phase-arrow"> → </span>}
          </span>
        );
      })}
      {showHuman && (
        <>
          <span className="phase-arrow"> → </span>
          <span className="phase-step phase-active">
            {ICONS.awaiting_human} AWAITING HUMAN
          </span>
        </>
      )}
      {phase === "error" && (
        <>
          <span className="phase-arrow"> → </span>
          <span className="phase-step phase-error">{ICONS.error} ERROR</span>
        </>
      )}
      {retries > 0 && phase !== "complete" && phase !== "error" && (
        <span className="phase-retry self-correct-badge" data-testid="phase-retry-badge">
          ✓ Self-corrected ×{retries}
        </span>
      )}
    </div>
  );
}
