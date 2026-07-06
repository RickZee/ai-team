import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { FileTreeViewer } from "../FileTreeViewer";
import type { ArtifactTreeNode } from "../../types";

const tree: ArtifactTreeNode[] = [
  {
    name: "src",
    path: "src",
    type: "dir",
    children: [
      { name: "main.py", path: "src/main.py", type: "file", children: [], size: 120 },
    ],
  },
];

describe("FileTreeViewer", () => {
  it("shows loading empty state", () => {
    render(
      <FileTreeViewer tree={[]} selectedPath={null} onSelectFile={() => {}} loading />,
    );
    expect(screen.getByTestId("file-tree-loading")).toHaveTextContent("Loading file tree");
  });

  it("shows empty tree state", () => {
    render(
      <FileTreeViewer tree={[]} selectedPath={null} onSelectFile={() => {}} />,
    );
    expect(screen.getByTestId("file-tree-empty")).toHaveTextContent("No files in this root");
  });

  it("selects a file on click", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    render(
      <FileTreeViewer tree={tree} selectedPath={null} onSelectFile={onSelect} />,
    );

    await user.click(screen.getByTestId("tree-file-src/main.py"));
    expect(onSelect).toHaveBeenCalledWith("src/main.py");
  });
});
