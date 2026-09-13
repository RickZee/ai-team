import { Children, cloneElement, isValidElement, useId, type ReactElement, type ReactNode } from "react";
import { AutoGrowTextarea } from "./AutoGrowTextarea";
import { EstimateTable } from "./EstimateTable";
import type { BackendInfo, CostEstimate } from "../types";

export interface RunConfigFormProps {
  profile: string;
  setProfile: (v: string) => void;
  complexity: string;
  setComplexity: (v: string) => void;
  description: string;
  setDescription: (v: string) => void;
  profileNames: string[];
  catalogLoading?: boolean;
  /** Run page only — backend selector block rendered above the shared fields. */
  backendSlot?: ReactNode;
  /** Page-specific action buttons (exactly one should be btn-primary). */
  actions: ReactNode;
  descriptionTestId: string;
  profileTestId: string;
  complexityTestId?: string;
  complexityHelperTestId?: string;
  disabledHintTestId: string;
  estimateHelperTestId: string;
  disabledHintText: string;
  showDisabledHint?: boolean;
  estimate?: CostEstimate | null;
  estimateMultiplier?: number;
  onEstimate?: () => void;
  estimateButtonTestId?: string;
  inlineEstimate?: boolean;
}

/** Shared run configuration fields for Run and Compare. */
export function RunConfigForm({
  profile,
  setProfile,
  complexity,
  setComplexity,
  description,
  setDescription,
  profileNames,
  catalogLoading = false,
  backendSlot,
  actions,
  descriptionTestId,
  profileTestId,
  complexityTestId,
  complexityHelperTestId = "complexity-helper",
  disabledHintTestId,
  estimateHelperTestId,
  disabledHintText,
  showDisabledHint = false,
  estimate,
  estimateMultiplier = 1,
  onEstimate,
  estimateButtonTestId,
  inlineEstimate = false,
}: RunConfigFormProps) {
  const uid = useId();
  const profileId = `${uid}-profile`;
  const complexityId = `${uid}-complexity`;
  const descriptionId = `${uid}-description`;
  const complexityHelpId = `${uid}-complexity-help`;
  const estimateHelpId = `${uid}-estimate-help`;
  const disabledHintId = `${uid}-disabled-hint`;

  const describedPrimary = [
    estimateHelpId,
    showDisabledHint ? disabledHintId : null,
  ]
    .filter(Boolean)
    .join(" ");

  const wiredActions = Children.map(actions, (child) => {
    if (!isValidElement(child)) return child;
    const el = child as ReactElement<{ className?: string; "aria-describedby"?: string }>;
    if (typeof el.props.className === "string" && el.props.className.includes("btn-primary")) {
      return cloneElement(el, { "aria-describedby": describedPrimary || undefined });
    }
    return child;
  });

  return (
    <div className="run-config-form">
      {backendSlot}
      <div className="form-grid">
        <div className="form-group">
          <label htmlFor={profileId}>Team Profile</label>
          {profileNames.length > 0 ? (
            <select
              id={profileId}
              value={profile}
              onChange={(e) => setProfile(e.target.value)}
              data-testid={profileTestId}
              disabled={catalogLoading}
            >
              {profileNames.map((name) => (
                <option key={name} value={name}>
                  {name}
                </option>
              ))}
            </select>
          ) : (
            <input
              id={profileId}
              value={profile}
              onChange={(e) => setProfile(e.target.value)}
              placeholder="full"
              data-testid={profileTestId}
              disabled={catalogLoading}
            />
          )}
        </div>
        <div className="form-group">
          <label htmlFor={complexityId}>Complexity</label>
          <select
            id={complexityId}
            value={complexity}
            onChange={(e) => setComplexity(e.target.value)}
            data-testid={complexityTestId}
            aria-describedby={complexityHelpId}
          >
            <option value="simple">Simple</option>
            <option value="medium">Medium</option>
            <option value="complex">Complex</option>
          </select>
          <p className="text-muted form-helper" id={complexityHelpId} data-testid={complexityHelperTestId}>
            Sets the cost/token estimate tier — it does not change agent behavior.
          </p>
        </div>
      </div>
      <div className="form-group full-width">
        <label htmlFor={descriptionId}>Project Description</label>
        <AutoGrowTextarea
          id={descriptionId}
          aria-describedby={estimateHelpId}
          value={description}
          onChange={setDescription}
          placeholder="Describe what to build..."
          data-testid={descriptionTestId}
        />
      </div>
      <div className="form-actions form-actions-primary">
        {wiredActions}
        {onEstimate && (
          <button
            type="button"
            className="btn-link"
            onClick={onEstimate}
            data-testid={estimateButtonTestId}
          >
            Estimate cost by complexity
          </button>
        )}
      </div>
      {showDisabledHint && (
        <p className="text-muted form-helper" id={disabledHintId} data-testid={disabledHintTestId}>
          {disabledHintText}
        </p>
      )}
      <p className="text-muted estimate-helper" id={estimateHelpId} data-testid={estimateHelperTestId}>
        Estimates are based on the complexity tier and team profile, not your description.
      </p>
      {inlineEstimate && estimate && (
        <div className="estimate-inline panel-section" data-testid="estimate-inline">
          <EstimateTable estimate={estimate} runMultiplier={estimateMultiplier} />
        </div>
      )}
    </div>
  );
}

/** Backend selector block for the Run page (passed as backendSlot). */
export function RunConfigBackendField({
  backend,
  setBackend,
  backendOptions,
  catalogLoading,
}: {
  backend: string;
  setBackend: (v: string) => void;
  backendOptions: BackendInfo[];
  catalogLoading?: boolean;
}) {
  const uid = useId();
  const backendId = `${uid}-backend`;
  const hintId = `${uid}-backend-hint`;
  const selected = backendOptions.find((b) => b.name === backend);
  return (
    <div className="form-grid form-grid-backend">
      <div className="form-group">
        <label htmlFor={backendId}>Backend</label>
        <select
          id={backendId}
          value={backend}
          onChange={(e) => setBackend(e.target.value)}
          data-testid="run-backend"
          disabled={catalogLoading}
          aria-describedby={selected?.required_key ? hintId : undefined}
        >
          {backendOptions.map((b) => (
            <option key={b.name} value={b.name} disabled={b.configured === false}>
              {b.label}
              {b.streaming ? " (streaming)" : ""}
              {b.configured === false ? " — key missing" : ""}
            </option>
          ))}
        </select>
        {selected?.required_key && (
          <p className="text-muted backend-key-hint" id={hintId} data-testid="backend-key-hint">
            Requires <code>{selected.required_key}</code>
            {selected.configured === false && (
              <span className="text-warning"> — not configured on server</span>
            )}
          </p>
        )}
      </div>
    </div>
  );
}
