import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ArchitecturePanel } from "./ArchitecturePanel";
import { CodeViewer } from "./CodeViewer";
import { DownloadPanel } from "./DownloadPanel";
import { EmptyState } from "./EmptyState";
import { FileTreeViewer } from "./FileTreeViewer";
import { TestResultsPanel } from "./TestResultsPanel";
import {
  getProjectArchitecture,
  getProjectFile,
  getProjectTests,
  getProjectTree,
} from "../hooks/useApi";
import type {
  ArchitecturePanelData,
  ArtifactFileContent,
  ArtifactRoot,
  ArtifactTreeNode,
  OpenFileTab,
  TestsPanelData,
} from "../types";

type TabId = "files" | "tests" | "architecture" | "download";

interface RunArtifactsPanelProps {
  projectId: string;
  isDemo?: boolean;
  initialTab?: TabId;
}

/** Artifact browser scoped to a single run — no run selector (IA-1). */
export function RunArtifactsPanel({
  projectId,
  isDemo = false,
  initialTab = "files",
}: RunArtifactsPanelProps) {
  const [tab, setTab] = useState<TabId>(initialTab);
  const [fileRoot, setFileRoot] = useState<ArtifactRoot>("workspace");

  const [workspaceTree, setWorkspaceTree] = useState<ArtifactTreeNode[]>([]);
  const [bundleTree, setBundleTree] = useState<ArtifactTreeNode[]>([]);
  const [treeLoading, setTreeLoading] = useState(false);
  const [treesLoaded, setTreesLoaded] = useState(false);

  const [tabs, setTabs] = useState<OpenFileTab[]>([]);
  const [activeTab, setActiveTab] = useState<OpenFileTab | null>(null);
  const [fileContent, setFileContent] = useState<ArtifactFileContent | null>(null);
  const [fileLoading, setFileLoading] = useState(false);
  const [fileError, setFileError] = useState<string | null>(null);
  const [selectedPath, setSelectedPath] = useState<string | null>(null);

  const [tests, setTests] = useState<TestsPanelData | null>(null);
  const [testsLoading, setTestsLoading] = useState(false);
  const [arch, setArch] = useState<ArchitecturePanelData | null>(null);
  const [archLoading, setArchLoading] = useState(false);

  const hasFiles = treesLoaded && (workspaceTree.length > 0 || bundleTree.length > 0);
  const activeTree = fileRoot === "workspace" ? workspaceTree : bundleTree;

  const loadTrees = useCallback(async (pid: string) => {
    setTreeLoading(true);
    setTreesLoaded(false);
    try {
      const [ws, bundle] = await Promise.all([
        getProjectTree(pid, "workspace"),
        getProjectTree(pid, "bundle"),
      ]);
      setWorkspaceTree(ws.tree);
      setBundleTree(bundle.tree);
    } catch {
      setWorkspaceTree([]);
      setBundleTree([]);
    } finally {
      setTreeLoading(false);
      setTreesLoaded(true);
    }
  }, []);

  const loadFile = useCallback(async (pid: string, path: string, root: ArtifactRoot) => {
    setFileLoading(true);
    setFileError(null);
    try {
      const content = await getProjectFile(pid, path, root);
      setFileContent(content);
    } catch (e) {
      setFileContent(null);
      setFileError(e instanceof Error ? e.message : "Failed to load file");
    } finally {
      setFileLoading(false);
    }
  }, []);

  const loadTestsArch = useCallback(async (pid: string) => {
    setTestsLoading(true);
    setArchLoading(true);
    try {
      const [t, a] = await Promise.all([getProjectTests(pid), getProjectArchitecture(pid)]);
      setTests(t);
      setArch(a);
    } catch {
      setTests(null);
      setArch(null);
    } finally {
      setTestsLoading(false);
      setArchLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!projectId) return;
    setTabs([]);
    setActiveTab(null);
    setFileContent(null);
    loadTrees(projectId);
    if (!isDemo) {
      loadTestsArch(projectId);
    } else {
      setTests(null);
      setArch(null);
    }
  }, [projectId, isDemo, loadTrees, loadTestsArch]);

  const openFile = (path: string) => {
    const tabEntry: OpenFileTab = {
      path,
      root: fileRoot,
      label: path.split("/").pop() || path,
    };
    setSelectedPath(path);
    setTabs((prev) => {
      if (prev.some((t) => t.path === path && t.root === fileRoot)) return prev;
      return [...prev, tabEntry];
    });
    setActiveTab(tabEntry);
    loadFile(projectId, path, fileRoot);
  };

  const closeTab = (path: string, root: ArtifactRoot) => {
    setTabs((prev) => {
      const next = prev.filter((t) => !(t.path === path && t.root === root));
      if (activeTab?.path === path && activeTab?.root === root) {
        const last = next[next.length - 1] ?? null;
        setActiveTab(last);
        if (last) loadFile(projectId, last.path, last.root);
        else {
          setFileContent(null);
          setFileError(null);
        }
      }
      return next;
    });
  };

  if (isDemo) {
    return (
      <div className="empty-state" data-testid="artifacts-demo-empty">
        <h3>Demo runs have no files on disk</h3>
        <p className="dim">Start a real run to generate workspace and bundle artifacts.</p>
        <Link to="/run" className="btn-primary">
          Start a real run
        </Link>
      </div>
    );
  }

  return (
    <div className="run-artifacts-panel" data-testid="run-artifacts-panel">
      <div className="artifacts-tabs">
        {(["files", "tests", "architecture", "download"] as TabId[]).map((id) => (
          <button
            key={id}
            type="button"
            className={`artifacts-tab ${tab === id ? "active" : ""}`}
            onClick={() => setTab(id)}
            data-testid={`tab-${id}`}
          >
            {id.charAt(0).toUpperCase() + id.slice(1)}
          </button>
        ))}
      </div>

      {treesLoaded && !hasFiles ? (
        <EmptyState
          title="No files found for this run"
          hint="This run may still be in progress or completed without writing output."
          testId="artifacts-no-files"
          className="empty-state"
        />
      ) : (
        <div className="artifacts-content">
          {tab === "files" && (
            <div className="artifacts-files-layout">
              <div className="panel artifacts-tree-panel">
                <div className="panel-header-row">
                  <h3 className="panel-header">Files ({fileRoot})</h3>
                  <select
                    value={fileRoot}
                    onChange={(e) => setFileRoot(e.target.value as ArtifactRoot)}
                    aria-label="Artifact root"
                  >
                    <option value="workspace">Workspace</option>
                    <option value="bundle">Results bundle</option>
                  </select>
                </div>
                <FileTreeViewer
                  tree={activeTree}
                  selectedPath={selectedPath}
                  onSelectFile={openFile}
                  loading={treeLoading}
                />
              </div>
              <div className="panel artifacts-viewer-panel">
                <h3 className="panel-header">Preview</h3>
                <CodeViewer
                  tabs={tabs}
                  activeTab={activeTab}
                  content={fileContent}
                  loading={fileLoading}
                  error={fileError}
                  onSelectTab={(t) => {
                    setActiveTab(t);
                    setFileRoot(t.root);
                    loadFile(projectId, t.path, t.root);
                  }}
                  onCloseTab={closeTab}
                />
              </div>
            </div>
          )}
          {tab === "tests" && (
            <div className="panel">
              <TestResultsPanel data={tests} loading={testsLoading} />
            </div>
          )}
          {tab === "architecture" && (
            <div className="panel">
              <ArchitecturePanel data={arch} loading={archLoading} />
            </div>
          )}
          {tab === "download" && (
            <div className="panel">
              <DownloadPanel
                projectId={projectId}
                workspaceTree={workspaceTree}
                selectedPath={selectedPath}
                fileRoot={fileRoot}
              />
            </div>
          )}
        </div>
      )}
    </div>
  );
}
