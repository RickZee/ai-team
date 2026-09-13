import {
  ArrowDown,
  CircleCheck,
  CircleX,
  ClipboardList,
  FlaskConical,
  Laptop,
  Rocket,
  User,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

const PHASES = [
  "intake",
  "planning",
  "development",
  "testing",
  "deployment",
  "complete",
] as const;

const ICONS: Record<string, LucideIcon> = {
  intake: ArrowDown,
  planning: ClipboardList,
  development: Laptop,
  testing: FlaskConical,
  deployment: Rocket,
  complete: CircleCheck,
  awaiting_human: User,
  error: CircleX,
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

  const renderPhase = (p: string, cls: string, label: string) => {
    const Icon = ICONS[p] ?? ClipboardList;
    return (
      <span className={cls}>
        <Icon className="icon-sm" aria-hidden="true" /> {label}
      </span>
    );
  };

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
            {renderPhase(p, cls, p.toUpperCase())}
            {i < PHASES.length - 1 && <span className="phase-arrow"> → </span>}
          </span>
        );
      })}
      {showHuman && (
        <>
          <span className="phase-arrow"> → </span>
          {renderPhase("awaiting_human", "phase-step phase-active", "AWAITING HUMAN")}
        </>
      )}
      {phase === "error" && (
        <>
          <span className="phase-arrow"> → </span>
          {renderPhase("error", "phase-step phase-error", "ERROR")}
        </>
      )}
      {retries > 0 && phase !== "complete" && phase !== "error" && (
        <span className="phase-retry self-correct-badge" data-testid="phase-retry-badge">
          Self-corrected ×{retries}
        </span>
      )}
    </div>
  );
}
