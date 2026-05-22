import { BrowserRouter, Link, NavLink, Route, Routes, useLocation } from "react-router-dom";
import { CommandPalette } from "./components/CommandPalette";
import { formatUnifiedRunLabel, useUnifiedRuns } from "./hooks/useUnifiedRuns";
import { Artifacts } from "./pages/Artifacts";
import { Compare } from "./pages/Compare";
import { Dashboard } from "./pages/Dashboard";
import { Run } from "./pages/Run";
import "./App.css";

function NavBar() {
  const location = useLocation();
  const dashboardActive =
    location.pathname === "/" || location.pathname.startsWith("/runs/");

  return (
    <nav className="nav" aria-label="Main">
      <Link to="/" className="nav-brand">
        <span className="brand-icon">🤖</span> AI-Team Dashboard
      </Link>
      <div className="nav-links">
        <NavLink
          to="/"
          className={dashboardActive ? "active" : ""}
          data-testid="nav-dashboard"
        >
          Dashboard
        </NavLink>
        <NavLink
          to="/run"
          className={({ isActive }) => (isActive ? "active" : "")}
          data-testid="nav-run"
        >
          Run
        </NavLink>
        <NavLink
          to="/compare"
          className={({ isActive }) => (isActive ? "active" : "")}
          data-testid="nav-compare"
        >
          Compare
        </NavLink>
        <NavLink
          to="/artifacts"
          className={({ isActive }) => (isActive ? "active" : "")}
          data-testid="nav-artifacts"
        >
          Artifacts
        </NavLink>
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
          <Route path="/" element={<Dashboard />} />
          <Route path="/runs/:runId" element={<Dashboard />} />
          <Route path="/run" element={<Run />} />
          <Route path="/compare" element={<Compare />} />
          <Route path="/artifacts" element={<Artifacts />} />
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
