import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getProjectArchitecture, getProjectTests } from "../hooks/useApi";
import type { ArchitecturePanelData, TestsPanelData } from "../types";

interface ArtifactPreviewProps {
  projectId: string;
  isDemo?: boolean;
}

export function ArtifactPreview({ projectId, isDemo }: ArtifactPreviewProps) {
  const [tests, setTests] = useState<TestsPanelData | null>(null);
  const [arch, setArch] = useState<ArchitecturePanelData | null>(null);
  const [fetchedFor, setFetchedFor] = useState<string | null>(null);

  useEffect(() => {
    if (!projectId || isDemo) return;
    let cancelled = false;
    Promise.all([getProjectTests(projectId), getProjectArchitecture(projectId)])
      .then(([t, a]) => {
        if (!cancelled) {
          setTests(t);
          setArch(a);
          setFetchedFor(projectId);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setTests(null);
          setArch(null);
          setFetchedFor(projectId);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [projectId, isDemo]);

  if (isDemo) return null;

  const loading = fetchedFor !== projectId;

  return (
    <div className="panel artifact-preview" data-testid="artifact-preview">
      <h3 className="panel-header">Artifacts preview</h3>
      {loading && <p className="text-muted">Loading artifact summary…</p>}
      {!loading && !tests && !arch?.system_overview && (
        <p className="text-muted">No artifact bundle found on disk for this run yet.</p>
      )}
      {tests && (
        <p>
          Tests: <span className="text-success">{tests.passed} passed</span>
          {tests.failed > 0 && <span className="text-danger"> · {tests.failed} failed</span>}
          {tests.skipped > 0 && <span className="text-muted"> · {tests.skipped} skipped</span>}
        </p>
      )}
      {arch?.system_overview && (
        <p className="artifact-preview-arch">
          {arch.system_overview.length > 200
            ? `${arch.system_overview.slice(0, 200)}…`
            : arch.system_overview}
        </p>
      )}
      <Link
        to={`/artifacts?project=${encodeURIComponent(projectId)}`}
        className="btn-secondary"
      >
        Open full artifact browser
      </Link>
    </div>
  );
}
