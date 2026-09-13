import { useMemo, useState } from "react";
import { Copy, Search, X } from "lucide-react";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark } from "react-syntax-highlighter/dist/esm/styles/prism";
import type { ArtifactFileContent, ArtifactRoot, OpenFileTab } from "../types";
import { EmptyState } from "./EmptyState";
import { LoadingState } from "./LoadingState";

interface CodeViewerProps {
  tabs: OpenFileTab[];
  activeTab: OpenFileTab | null;
  content: ArtifactFileContent | null;
  loading: boolean;
  error: string | null;
  onSelectTab: (tab: OpenFileTab) => void;
  onCloseTab: (path: string, root: ArtifactRoot) => void;
}

function highlightLines(text: string, query: string): string {
  if (!query.trim()) return text;
  const q = query.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const re = new RegExp(`(${q})`, "gi");
  return text
    .split("\n")
    .map((line) =>
      line.replace(re, "<mark class=\"code-search-hit\">$1</mark>"),
    )
    .join("\n");
}

function MarkdownPreview({ text }: { text: string }) {
  return (
    <div
      className="markdown-preview"
      tabIndex={0}
      aria-label="Markdown preview"
      dangerouslySetInnerHTML={{
        __html: text
          .replace(/^### (.*)$/gm, "<h3>$1</h3>")
          .replace(/^## (.*)$/gm, "<h2>$1</h2>")
          .replace(/^# (.*)$/gm, "<h1>$1</h1>")
          .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
          .replace(/`([^`]+)`/g, "<code>$1</code>")
          .replace(/\n\n/g, "</p><p>")
          .replace(/^/, "<p>")
          .replace(/$/, "</p>"),
      }}
    />
  );
}

export function CodeViewer({
  tabs,
  activeTab,
  content,
  loading,
  error,
  onSelectTab,
  onCloseTab,
}: CodeViewerProps) {
  const [search, setSearch] = useState("");
  const [copied, setCopied] = useState(false);
  const [viewMode, setViewMode] = useState<"code" | "markdown">("code");

  const lang = content?.language || "text";
  const isMarkdown =
    lang === "markdown" || activeTab?.path.endsWith(".md") || activeTab?.path.endsWith(".mdx");

  const displayContent = content?.content ?? "";
  const highlightedHtml = useMemo(
    () => (search.trim() ? highlightLines(displayContent, search) : null),
    [displayContent, search],
  );

  const handleCopy = async () => {
    if (!content?.content) return;
    await navigator.clipboard.writeText(content.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="code-viewer" data-testid="code-viewer">
      <div className="code-tabs">
        {tabs.map((tab) => (
          <button
            key={`${tab.root}:${tab.path}`}
            type="button"
            className={`code-tab ${
              activeTab?.path === tab.path && activeTab?.root === tab.root ? "active" : ""
            }`}
            aria-pressed={activeTab?.path === tab.path && activeTab?.root === tab.root}
            onClick={() => onSelectTab(tab)}
          >
            {tab.label}
            <button
              type="button"
              className="code-tab-close"
              aria-label={`Close ${tab.label}`}
              onClick={(e) => {
                e.stopPropagation();
                onCloseTab(tab.path, tab.root);
              }}
            >
              <X className="icon-sm" aria-hidden="true" />
            </button>
          </button>
        ))}
      </div>
      <div className="code-toolbar">
        <div className="code-search">
          <Search className="icon-sm" aria-hidden="true" />
          <input
            type="search"
            placeholder="Highlight in file…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            data-testid="code-search"
          />
        </div>
        {isMarkdown && (
          <div className="code-view-modes">
            <button
              type="button"
              className={`btn-secondary btn-sm ${viewMode === "code" ? "active" : ""}`}
              aria-pressed={viewMode === "code"}
              onClick={() => setViewMode("code")}
            >
              Source
            </button>
            <button
              type="button"
              className={`btn-secondary btn-sm ${viewMode === "markdown" ? "active" : ""}`}
              aria-pressed={viewMode === "markdown"}
              onClick={() => setViewMode("markdown")}
            >
              Preview
            </button>
          </div>
        )}
        <button
          type="button"
          className="btn-secondary btn-sm"
          onClick={handleCopy}
          disabled={!content?.content}
        >
          <Copy className="icon-sm" aria-hidden="true" />
          {copied ? "Copied" : "Copy"}
        </button>
      </div>
      <div className="code-body" tabIndex={0} aria-label="File contents">
        {!activeTab && <EmptyState title="Select a file from the tree." />}
        {loading && <LoadingState label="Loading…" />}
        {error && <div className="code-error">{error}</div>}
        {content && !loading && !error && (
          <>
            {content.truncated && (
              <p className="code-truncated">File truncated for display.</p>
            )}
            {isMarkdown && viewMode === "markdown" ? (
              <MarkdownPreview text={displayContent} />
            ) : highlightedHtml && search.trim() ? (
              <pre
                className="code-highlight-pre"
                tabIndex={0}
                aria-label="Highlighted file"
                dangerouslySetInnerHTML={{ __html: highlightedHtml }}
              />
            ) : (
              <SyntaxHighlighter
                language={lang}
                style={oneDark}
                showLineNumbers
                customStyle={{ margin: 0, borderRadius: "var(--radius-md)", fontSize: "var(--text-sm)" }}
              >
                {displayContent || "(empty)"}
              </SyntaxHighlighter>
            )}
          </>
        )}
      </div>
    </div>
  );
}
