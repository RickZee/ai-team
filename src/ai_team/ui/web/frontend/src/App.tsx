import { useState } from "react";
import { Bot } from "lucide-react";
import { BrowserRouter, Link, NavLink, Route, Routes } from "react-router-dom";
import { CommandPalette } from "./components/CommandPalette";
import { useUnifiedRuns } from "./hooks/useUnifiedRuns";
import { ArtifactsRedirect } from "./pages/ArtifactsRedirect";
import { Compare } from "./pages/Compare";
import { Home } from "./pages/Home";
import { Run } from "./pages/Run";
import { RunDetail } from "./pages/RunDetail";

const IS_APPLE =
  typeof navigator !== "undefined" && /Mac|iPhone|iPad|iPod/i.test(navigator.platform);

function NavBar({ onOpenPalette }: { onOpenPalette: () => void }) {
  return (
    <nav className="nav" aria-label="Main">
      <Link to="/" className="nav-brand" aria-label="AI-Team home">
        <Bot className="icon-md brand-icon" aria-hidden="true" />
        AI-Team
      </Link>
      <div className="nav-links">
        <NavLink
          to="/"
          end
          className={({ isActive }) => (isActive ? "active" : "")}
          data-testid="nav-home"
        >
          Home
        </NavLink>
        <NavLink
          to="/compare"
          className={({ isActive }) => (isActive ? "active" : "")}
          data-testid="nav-compare"
        >
          Compare
        </NavLink>
      </div>
      <button
        type="button"
        className="nav-hint btn-ghost"
        onClick={onOpenPalette}
        aria-label="Open command palette"
      >
        {IS_APPLE ? "⌘K" : "Ctrl K"}
      </button>
    </nav>
  );
}

function AppShell() {
  const { runs } = useUnifiedRuns();
  const [paletteOpen, setPaletteOpen] = useState(false);
  return (
    <>
      <a href="#main" className="skip-link">
        Skip to content
      </a>
      <CommandPalette runs={runs} open={paletteOpen} onOpenChange={setPaletteOpen} />
      <NavBar onOpenPalette={() => setPaletteOpen(true)} />
      <main id="main" className="main">
        <div className="content">
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/runs/:runId" element={<RunDetail />} />
            <Route path="/run" element={<Run />} />
            <Route path="/compare" element={<Compare />} />
            {/* /artifacts is a redirect target only — not linked in nav (design §8.3). */}
            <Route path="/artifacts" element={<ArtifactsRedirect />} />
          </Routes>
        </div>
      </main>
    </>
  );
}

function App() {
  return (
    <BrowserRouter>
      <div className="app">
        <AppShell />
      </div>
    </BrowserRouter>
  );
}

export default App;
