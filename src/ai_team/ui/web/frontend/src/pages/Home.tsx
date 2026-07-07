import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { AlertBanner } from "../components/AlertBanner";
import { ConfirmModal } from "../components/ConfirmModal";
import { HowItWorks } from "../components/HowItWorks";
import { RunList } from "../components/RunList";
import { deleteRun, getHealth, getRuns, postDemo } from "../hooks/useApi";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import type { RunInfo } from "../types";
import { sortRunsByDate } from "../utils/formatRun";

const POLL_ACTIVE_MS = 2000;
const POLL_IDLE_MS = 8000;

/** Home — run browser with launcher entry (IA-1). */
export function Home() {
  useDocumentTitle("Home — AI-Team");
  const navigate = useNavigate();
  const [runs, setRuns] = useState<RunInfo[]>([]);
  const [apiError, setApiError] = useState<string | null>(null);
  const [healthOk, setHealthOk] = useState<boolean | null>(null);
  const [demoLoading, setDemoLoading] = useState(false);
  const [deleteConfirmId, setDeleteConfirmId] = useState<string | null>(null);
  const [deleteLoading, setDeleteLoading] = useState(false);

  const hasActiveRuns = useMemo(
    () => runs.some((r) => r.status === "running" || r.status === "awaiting_human"),
    [runs],
  );

  const pollRuns = useCallback(async () => {
    try {
      const data = await getRuns();
      setRuns(sortRunsByDate(data.runs as RunInfo[]));
      setApiError(null);
    } catch (e) {
      setApiError(e instanceof Error ? e.message : "Cannot reach API");
    }
  }, []);

  useEffect(() => {
    getHealth()
      .then((h) => setHealthOk(h.status === "ok"))
      .catch(() => setHealthOk(false));
  }, []);

  useEffect(() => {
    void pollRuns();
    const tick = () => {
      if (!document.hidden) void pollRuns();
    };
    const ms = hasActiveRuns ? POLL_ACTIVE_MS : POLL_IDLE_MS;
    const id = setInterval(tick, ms);
    const onVisibility = () => {
      if (!document.hidden) void pollRuns();
    };
    document.addEventListener("visibilitychange", onVisibility);
    return () => {
      clearInterval(id);
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, [pollRuns, hasActiveRuns]);

  const handleDemo = async () => {
    setDemoLoading(true);
    try {
      const { run_id } = await postDemo();
      navigate(`/runs/${run_id}`);
    } catch (e) {
      setApiError(e instanceof Error ? e.message : "Demo failed");
    } finally {
      setDemoLoading(false);
    }
  };

  const handleDeleteRun = async () => {
    if (!deleteConfirmId) return;
    setDeleteLoading(true);
    try {
      await deleteRun(deleteConfirmId);
      setDeleteConfirmId(null);
      await pollRuns();
    } catch (e) {
      setApiError(e instanceof Error ? e.message : "Delete failed");
      setDeleteConfirmId(null);
    } finally {
      setDeleteLoading(false);
    }
  };

  return (
    <div className="home-page page-shell" data-testid="home-page">
      {healthOk === false && (
        <AlertBanner variant="warning" message="API unreachable — is ai-team-web running?" />
      )}
      {apiError && <AlertBanner message={apiError} onDismiss={() => setApiError(null)} />}

      <header className="page-header home-header">
        <div>
          <h2>Runs</h2>
          <p className="dim">Browse past and active runs. Select a run to monitor or review.</p>
        </div>
        <div className="home-actions btn-row">
          <Link to="/run" className="btn-primary" data-testid="home-new-run">
            New run
          </Link>
          <Link to="/compare" className="btn-secondary">
            Compare backends
          </Link>
          <button
            type="button"
            className="btn-link"
            onClick={handleDemo}
            disabled={demoLoading}
            data-testid="home-demo"
          >
            {demoLoading ? "Starting…" : "Play sample run"}
          </button>
        </div>
      </header>

      {runs.length === 0 ? (
        <div className="home-empty panel" data-testid="home-empty">
          <HowItWorks />
        </div>
      ) : (
        <div className="home-run-list panel">
          <RunList
            runs={runs}
            selectedRunId={null}
            onSelect={(id) => navigate(`/runs/${id}`)}
            onDelete={(id) => setDeleteConfirmId(id)}
            variant="home"
          />
        </div>
      )}

      <ConfirmModal
        open={deleteConfirmId !== null}
        title="Delete run?"
        message="Removes workspace files, output bundle, and registry entry. This cannot be undone."
        confirmLabel={deleteLoading ? "Deleting…" : "Delete run"}
        cancelLabel="Cancel"
        onConfirm={handleDeleteRun}
        onCancel={() => setDeleteConfirmId(null)}
      />
    </div>
  );
}
