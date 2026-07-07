import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { ArtifactsRedirect } from "../ArtifactsRedirect";

describe("ArtifactsRedirect", () => {
  it("redirects /artifacts?project=X to /runs/X#artifacts", () => {
    render(
      <MemoryRouter initialEntries={["/artifacts?project=run-abc"]}>
        <Routes>
          <Route path="/artifacts" element={<ArtifactsRedirect />} />
          <Route path="/runs/:runId" element={<div data-testid="run-detail" />} />
        </Routes>
      </MemoryRouter>,
    );
    expect(screen.getByTestId("run-detail")).toBeInTheDocument();
  });
});
