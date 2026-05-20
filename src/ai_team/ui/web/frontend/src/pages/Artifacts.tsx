import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { ArchitecturePanel } from "../components/ArchitecturePanel";
import { CodeViewer } from "../components/CodeViewer";
import { DownloadPanel } from "../components/DownloadPanel";
import { FileTreeViewer } from "../components/FileTreeViewer";
import { TestResultsPanel } from "../components/TestResultsPanel";
import {
  getProjectArchitecture,
  getProjectFile,
  getProjectTests,
  getProjectTree,
} from "../hooks/useApi";
import { formatUnifiedRunLabel, useUnifiedRuns } from "../hooks/useUnifiedRuns";
import type {
  ArchitecturePanelData,
  ArtifactFileContent,
  ArtifactRoot,
  ArtifactTreeNode,
  OpenFileTab,
  TestsPanelData,
} from "../types";

type TabId = "files" | "tests" | "architecture" | "download";

export function Artifacts() {
  const [searchParams, setSearchParams] = useSearchParams();
  const initialProject = searchParams.get("project") || "";
  const { runs, loading: runsLoading } = useUnifiedRuns();

  const [projectId, setProjectId] = useState(initialProject);
  const [tab, setTab] = useState<TabId>("files");
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

  const selectedRun = useMemo(
    () => runs.find((r) => r.run_id === projectId),
    [runs, projectId],
  );
  const isDemo = selectedRun?.backend === "demo";
  const hasFiles =
    treesLoaded && (workspaceTree.length > 0 || bundleTree.length > 0);

  const activeTree = fileRoot === "workspace" ? workspaceTree : bundleTree;

  useEffect(() => {
    if (!projectId && runs.length > 0 && !runsLoading) {
      setProjectId(runs[0].run_id);
    }
  }, [projectId, runs, runsLoading]);

  const loadTrees = useCallback(async (pid: string) => {
    if (!pid) return;
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
      const [t, a] = await Promise.all([
        getProjectTests(pid),
        getProjectArchitecture(pid),
      ]);
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
    setSearchParams({ project: projectId });
    loadTrees(projectId);
    if (selectedRun?.backend !== "demo") {
      loadTestsArch(projectId);
    } else {
      setTests(null);
      setArch(null);
    }
  }, [projectId, loadTrees, loadTestsArch, setSearchParams, selectedRun?.backend]);

  const openFile = (path: string) => {
    if (!projectId) return;
    setSelectedPath(path);
    const tabEntry: OpenFileTab = {
      path,
      root: fileRoot,
      label: path.split("/").pop() || path,
    };
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
        if (last && projectId) loadFile(projectId, last.path, last.root);
        else {
          setFileContent(null);
          setFileError(null);
        }
      }
      return next;
    });
  };

  return (
    <div className="artifacts-page page-shell" data-testid="artifacts-page">
      <header className="page-header artifacts-header">
        <h2>Artifact Browser</h2>
        <div className="artifacts-controls">
          <label>
            Run
            <select
              value={projectId}
              onChange={(e) => setProjectId(e.target.value)}
              data-testid="artifact-run-select"
              disabled={runsLoading}
            >
              <option value="">Select run…</option>
              {runs.map((r) => (
                <option key={r.run_id} value={r.run_id}>
                  {formatUnifiedRunLabel(r)}
                </option>
              ))}
            </select>
          </label>
          {tab === "files" && projectId && !isDemo && (
            <label>
              Root
              <select
                value={fileRoot}
                onChange={(e) => setFileRoot(e.target.value as ArtifactRoot)}
              >
                <option value="workspace">Workspace</option>
                <option value="bundle">Results bundle</option>
              </select>
            </label>
          )}
        </div>
      </header>

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

      {!projectId ? (
        <div className="empty-state">Select a run to browse artifacts.</div>
      ) : isDemo ? (
        <div className="empty-state panel" data-testid="artifacts-demo-empty">
          <h3>Demo runs have no files on disk</h3>
          <p className="dim">
            The demo simulates the pipeline in memory only. Start a real run to generate
            workspace and bundle artifacts.
          </p>
          <Link to="/run" className="btn-primary">
            Start a real run
          </Link>
        </div>
      ) : treesLoaded && !hasFiles ? (
        <div className="empty-state panel" data-testid="artifacts-no-files">
          <p>No artifact files found for this run yet. It may still be in progress or failed
            before writing output.</p>
          <Link to={`/runs/${projectId}`} className="btn-secondary">
            Open dashboard
          </Link>
        </div>
      ) : (
        <div className="artifacts-content">
          {tab === "files" && (
            <div className="artifacts-files-layout">
              <div className="panel artifacts-tree-panel">
                <h3>Files ({fileRoot})</h3>
                <FileTreeViewer
                  tree={activeTree}
                  selectedPath={selectedPath}
                  onSelectFile={openFile}
                  loading={treeLoading}
                />
              </div>
              <div className="panel artifacts-viewer-panel">
                <h3>Preview</h3>
                <CodeViewer
                  tabs={tabs}
                  activeTab={activeTab}
                  content={fileContent}
                  loading={fileLoading}
                  error={fileError}
                  onSelectTab={(t) => {
                    setActiveTab(t);
                    setFileRoot(t.root);
                    if (projectId) loadFile(projectId, t.path, t.root);
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
