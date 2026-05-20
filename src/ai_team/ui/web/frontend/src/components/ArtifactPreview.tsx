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
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!projectId || isDemo) {
      setTests(null);
      setArch(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    Promise.all([getProjectTests(projectId), getProjectArchitecture(projectId)])
      .then(([t, a]) => {
        if (!cancelled) {
          setTests(t);
          setArch(a);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setTests(null);
          setArch(null);
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [projectId, isDemo]);

  if (isDemo) return null;

  return (
    <div className="panel artifact-preview" data-testid="artifact-preview">
      <h3>Artifacts preview</h3>
      {loading && <p className="dim">Loading artifact summary…</p>}
      {!loading && !tests && !arch?.system_overview && (
        <p className="dim">No artifact bundle found on disk for this run yet.</p>
      )}
      {tests && (
        <p>
          Tests: <span className="green">{tests.passed} passed</span>
          {tests.failed > 0 && <span className="red"> · {tests.failed} failed</span>}
          {tests.skipped > 0 && <span className="dim"> · {tests.skipped} skipped</span>}
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
