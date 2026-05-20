import { useState } from "react";
import { Clipboard, Download, ExternalLink } from "lucide-react";
import { projectDownloadZipUrl } from "../hooks/useApi";
import type { ArtifactRoot, ArtifactTreeNode } from "../types";

function flattenPaths(nodes: ArtifactTreeNode[], prefix = ""): string[] {
  const out: string[] = [];
  for (const n of nodes) {
    const p = prefix ? `${prefix}/${n.name}` : n.name;
    if (n.type === "file") out.push(p);
    else out.push(...flattenPaths(n.children, p));
  }
  return out;
}

interface DownloadPanelProps {
  projectId: string;
  workspaceTree: ArtifactTreeNode[];
  selectedPath: string | null;
  fileRoot: ArtifactRoot;
}

export function DownloadPanel({
  projectId,
  workspaceTree,
  selectedPath,
  fileRoot,
}: DownloadPanelProps) {
  const [copied, setCopied] = useState(false);

  const zipUrl = projectDownloadZipUrl(projectId);

  const copyStructure = async () => {
    const paths = flattenPaths(workspaceTree);
    const text = paths.length ? paths.join("\n") : "(no files)";
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const fileDownloadUrl =
    selectedPath && projectId
      ? `${projectDownloadZipUrl(projectId).replace("/download.zip", "/file")}?path=${encodeURIComponent(selectedPath)}&root=${fileRoot}`
      : null;

  return (
    <div className="download-panel" data-testid="download-panel">
      <div className="download-actions">
        <a href={zipUrl} className="btn-primary" download data-testid="download-zip">
          <Download size={16} /> Download workspace ZIP
        </a>
        <button type="button" className="btn-secondary" onClick={copyStructure}>
          <Clipboard size={16} />
          {copied ? "Copied" : "Copy file tree"}
        </button>
        <button
          type="button"
          className="btn-secondary"
          disabled
          title="Requires GitHub token integration (coming soon)"
        >
          <ExternalLink size={16} /> Open in GitHub
        </button>
      </div>
      {selectedPath && fileDownloadUrl && (
        <p className="download-hint">
          Current file: <code>{selectedPath}</code> — open via Files tab or{" "}
          <a href={fileDownloadUrl} target="_blank" rel="noreferrer">
            view raw
          </a>
        </p>
      )}
      <p className="download-note text-dim">
        Re-running individual failed tests requires the CLI (<code>ai-team</code>) against the
        workspace directory.
      </p>
    </div>
  );
}
