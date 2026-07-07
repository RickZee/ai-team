import { Navigate, useSearchParams } from "react-router-dom";

/** Redirect legacy /artifacts?project=X → /runs/X#artifacts (IA-1). */
export function ArtifactsRedirect() {
  const [params] = useSearchParams();
  const project = params.get("project");
  if (project) {
    return <Navigate to={`/runs/${encodeURIComponent(project)}#artifacts`} replace />;
  }
  return <Navigate to="/" replace />;
}
