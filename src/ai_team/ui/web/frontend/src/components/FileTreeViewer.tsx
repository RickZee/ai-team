import { useState } from "react";
import { ChevronDown, ChevronRight, File, Folder } from "lucide-react";
import type { ArtifactTreeNode } from "../types";

function fileIcon(name: string) {
  const ext = name.includes(".") ? name.split(".").pop()?.toLowerCase() : "";
  return ext || "file";
}

function formatSize(bytes: number | null | undefined) {
  if (bytes == null) return "";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

interface TreeRowProps {
  node: ArtifactTreeNode;
  depth: number;
  selectedPath: string | null;
  onSelect: (path: string) => void;
}

function TreeRow({ node, depth, selectedPath, onSelect }: TreeRowProps) {
  const [open, setOpen] = useState(depth < 2);
  const isDir = node.type === "dir";
  const selected = selectedPath === node.path;

  return (
    <div className="tree-row-wrap">
      <button
        type="button"
        className={`tree-row ${selected ? "tree-row-selected" : ""}`}
        style={{ paddingLeft: `${depth * 12 + 8}px` }}
        onClick={() => {
          if (isDir) setOpen((o) => !o);
          else onSelect(node.path);
        }}
        data-testid={`tree-${node.type}-${node.path}`}
      >
        {isDir ? (
          open ? (
            <ChevronDown size={14} className="tree-chevron" />
          ) : (
            <ChevronRight size={14} className="tree-chevron" />
          )
        ) : (
          <span className="tree-chevron-spacer" />
        )}
        {isDir ? <Folder size={14} /> : <File size={14} />}
        <span className="tree-name">{node.name}</span>
        {!isDir && node.size != null && (
          <span className="tree-size">{formatSize(node.size)}</span>
        )}
        <span className="tree-ext">{!isDir ? fileIcon(node.name) : ""}</span>
      </button>
      {isDir && open && node.children.length > 0 && (
        <div className="tree-children">
          {node.children.map((child) => (
            <TreeRow
              key={child.path}
              node={child}
              depth={depth + 1}
              selectedPath={selectedPath}
              onSelect={onSelect}
            />
          ))}
        </div>
      )}
    </div>
  );
}

interface FileTreeViewerProps {
  tree: ArtifactTreeNode[];
  selectedPath: string | null;
  onSelectFile: (path: string) => void;
  loading?: boolean;
}

export function FileTreeViewer({
  tree,
  selectedPath,
  onSelectFile,
  loading,
}: FileTreeViewerProps) {
  if (loading) {
    return <div className="empty-state">Loading tree…</div>;
  }
  if (!tree.length) {
    return <div className="empty-state">No files yet for this run.</div>;
  }
  return (
    <div className="file-tree" data-testid="file-tree">
      {tree.map((node) => (
        <TreeRow
          key={node.path}
          node={node}
          depth={0}
          selectedPath={selectedPath}
          onSelect={onSelectFile}
        />
      ))}
    </div>
  );
}
