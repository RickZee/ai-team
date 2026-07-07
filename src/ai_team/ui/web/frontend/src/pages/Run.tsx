import { useEffect, useRef, useState } from "react";
import { Link, useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { AlertBanner } from "../components/AlertBanner";
import { HumanReviewPanel } from "../components/HumanReviewPanel";
import { RunConfigBackendField, RunConfigForm } from "../components/RunConfigForm";
import { RunLaunchStatus } from "../components/RunLaunchStatus";
import { useCatalog } from "../hooks/useCatalog";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import { postDemo, postEstimate } from "../hooks/useApi";
import { useRunWebSocket } from "../hooks/useWebSocket";
import type { CostEstimate } from "../types";

interface RunPrefill {
  backend?: string;
  profile?: string;
  description?: string;
  complexity?: string;
}

interface RunLocationState {
  prefill?: RunPrefill;
  autoStart?: boolean;
}

export function Run() {
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const routeState = (location.state as RunLocationState | null) ?? {};
  const prefill = routeState.prefill;
  const { backends, profileNames, loading: catalogLoading, error: catalogError } = useCatalog();
  const [backend, setBackend] = useState(prefill?.backend ?? "langgraph");
  const [profile, setProfile] = useState(prefill?.profile ?? "full");
  const [description, setDescription] = useState(prefill?.description ?? "");
  const [complexity, setComplexity] = useState(prefill?.complexity ?? "medium");
  const [estimate, setEstimate] = useState<CostEstimate | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const autoStarted = useRef(false);

  const { runId, projectId, status, errorMessage, hitlPayload, startRun } = useRunWebSocket();

  useDocumentTitle(status === "awaiting_human" ? null : "Run — AI-Team");

  const canRun =
    description.trim().length > 0 && status !== "running" && status !== "connecting";

  const backendOptions =
    backends.length > 0
      ? backends
      : [
          { name: "langgraph", label: "LangGraph", streaming: true, required_key: "OPENROUTER_API_KEY" },
          { name: "crewai", label: "CrewAI", streaming: false, required_key: "OPENROUTER_API_KEY" },
          {
            name: "claude-agent-sdk",
            label: "Claude Agent SDK",
            streaming: true,
            required_key: "ANTHROPIC_API_KEY",
          },
        ];

  useEffect(() => {
    if (runId && (status === "running" || status === "connecting")) {
      navigate(`/runs/${runId}`, { replace: true });
    }
  }, [runId, status, navigate]);

  useEffect(() => {
    if (searchParams.get("estimate") === "1") {
      void postEstimate(complexity)
        .then(setEstimate)
        .catch((e) => setActionError(e instanceof Error ? e.message : "Estimate failed"));
    }
  }, [searchParams, complexity]);

  useEffect(() => {
    if (routeState.autoStart && prefill?.description && !autoStarted.current && canRun) {
      autoStarted.current = true;
      startRun(
        prefill.backend ?? backend,
        prefill.profile ?? profile,
        prefill.description,
        prefill.complexity ?? complexity,
        estimate?.total_usd ?? null,
      );
    }
  }, [routeState.autoStart, prefill, canRun, startRun, backend, profile, complexity, estimate]);

  const handleRun = () => {
    if (!canRun) return;
    setActionError(null);
    startRun(backend, profile, description, complexity, estimate?.total_usd ?? null);
  };

  const handleEstimate = async () => {
    setActionError(null);
    try {
      setEstimate(await postEstimate(complexity));
    } catch (e) {
      setActionError(e instanceof Error ? e.message : "Estimate failed");
    }
  };

  const handleDemo = async () => {
    setActionError(null);
    try {
      const { run_id } = await postDemo();
      navigate(`/runs/${run_id}`);
    } catch (e) {
      setActionError(e instanceof Error ? e.message : "Demo failed");
    }
  };

  return (
    <div className="run-page page-shell">
      {catalogError && <AlertBanner variant="warning" message={catalogError} />}
      {actionError && (
        <AlertBanner message={actionError} onDismiss={() => setActionError(null)} />
      )}

      <header className="page-header">
        <h2>Run Pipeline</h2>
        <p className="dim">Configure and start a run — live monitoring opens on the run detail page.</p>
      </header>

      <div className="run-form panel">
        <RunConfigForm
          profile={profile}
          setProfile={setProfile}
          complexity={complexity}
          setComplexity={setComplexity}
          description={description}
          setDescription={setDescription}
          profileNames={profileNames}
          catalogLoading={catalogLoading}
          backendSlot={
            <RunConfigBackendField
              backend={backend}
              setBackend={setBackend}
              backendOptions={backendOptions}
              catalogLoading={catalogLoading}
            />
          }
          descriptionTestId="run-description"
          profileTestId="run-profile"
          complexityTestId="run-complexity"
          disabledHintTestId="run-disabled-hint"
          estimateHelperTestId="run-estimate-helper"
          disabledHintText="Enter a project description to run."
          showDisabledHint={!description.trim()}
          estimate={estimate}
          inlineEstimate
          onEstimate={handleEstimate}
          estimateButtonTestId="run-estimate"
          actions={
            <>
              <button
                className="btn-primary"
                onClick={handleRun}
                disabled={!canRun}
                data-testid="run-submit"
              >
                {status === "running" || status === "connecting" ? "Starting…" : "Run"}
              </button>
              <button type="button" className="btn-link" onClick={handleDemo} data-testid="run-demo">
                Play sample run
              </button>
            </>
          }
        />
        {estimate && !estimate.within_budget && (
          <p className="estimate-budget-warn yellow">
            Estimated cost exceeds default budget — review before running.
          </p>
        )}
      </div>

      <RunLaunchStatus status={status} runId={runId} errorMessage={errorMessage} />

      {status === "awaiting_human" && runId && (
        <HumanReviewPanel
          runId={runId}
          payload={hitlPayload}
          backend={backend}
          onResumed={() => navigate(`/runs/${runId}`)}
        />
      )}

      {status === "complete" && runId && (
        <div className="run-complete panel">
          <span className="green">Run complete</span>
          <Link to={`/runs/${runId}`} className="btn-primary" data-testid="run-open-dashboard">
            Open dashboard
          </Link>
          {(projectId ?? runId) && (
            <Link
              to={`/artifacts?project=${encodeURIComponent(projectId ?? runId)}`}
              className="btn-secondary"
              data-testid="view-artifacts"
            >
              View artifacts
            </Link>
          )}
        </div>
      )}
      {status === "error" && (
        <div className="run-error panel" data-testid="run-error">
          {errorMessage ?? "Run failed"}
        </div>
      )}
    </div>
  );
}
