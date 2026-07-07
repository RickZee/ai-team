import { BrowserRouter, Link, NavLink, Route, Routes, useLocation } from "react-router-dom";
import { CommandPalette } from "./components/CommandPalette";
import { useUnifiedRuns } from "./hooks/useUnifiedRuns";
import { ArtifactsRedirect } from "./pages/ArtifactsRedirect";
import { Compare } from "./pages/Compare";
import { Home } from "./pages/Home";
import { Run } from "./pages/Run";
import { RunDetail } from "./pages/RunDetail";
import "./App.css";

function NavBar() {
  const location = useLocation();
  const runMatch = location.pathname.match(/^\/runs\/([^/]+)/);
  const openRunId = runMatch?.[1] ?? null;

  return (
    <nav className="nav" aria-label="Main">
      <Link to="/" className="nav-brand">
        <span className="brand-icon">🤖</span> AI-Team
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
        {openRunId && (
          <NavLink
            to={`/runs/${openRunId}`}
            className={({ isActive }) => (isActive ? "active" : "")}
            data-testid="nav-open-run"
          >
            Run
          </NavLink>
        )}
      </div>
      <span className="nav-hint dim" title="Command palette">
        ⌘K
      </span>
    </nav>
  );
}

function AppShell() {
  const { runs } = useUnifiedRuns();
  return (
    <>
      <CommandPalette runs={runs} />
      <NavBar />
      <main className="main">
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/runs/:runId" element={<RunDetail />} />
          <Route path="/run" element={<Run />} />
          <Route path="/compare" element={<Compare />} />
          <Route path="/artifacts" element={<ArtifactsRedirect />} />
        </Routes>
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
