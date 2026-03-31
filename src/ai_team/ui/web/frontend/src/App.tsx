import { BrowserRouter, Link, NavLink, Route, Routes } from "react-router-dom";
import { Dashboard } from "./pages/Dashboard";
import { Run } from "./pages/Run";
import { Compare } from "./pages/Compare";
import "./App.css";

function App() {
  return (
    <BrowserRouter>
      <div className="app">
        <nav className="nav">
          <Link to="/" className="nav-brand">
            <span className="brand-icon">🤖</span> AI-Team Dashboard
          </Link>
          <div className="nav-links">
            <NavLink to="/" end className={({ isActive }) => (isActive ? "active" : "")}>
              Dashboard
            </NavLink>
            <NavLink to="/run" className={({ isActive }) => (isActive ? "active" : "")}>
              Run
            </NavLink>
            <NavLink to="/compare" className={({ isActive }) => (isActive ? "active" : "")}>
              Compare
            </NavLink>
          </div>
        </nav>
        <main className="main">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/run" element={<Run />} />
            <Route path="/compare" element={<Compare />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}

export default App;
