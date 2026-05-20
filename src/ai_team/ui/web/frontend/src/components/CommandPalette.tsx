import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { postDemo } from "../hooks/useApi";
import type { UnifiedRun } from "../hooks/useUnifiedRuns";

interface CommandPaletteProps {
  runs: UnifiedRun[];
  onEstimate?: () => void;
}

interface Command {
  id: string;
  label: string;
  group: string;
  action: () => void;
}

export function CommandPalette({ runs, onEstimate }: CommandPaletteProps) {
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");

  const close = useCallback(() => {
    setOpen(false);
    setQuery("");
  }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setOpen((v) => !v);
      }
      if (e.key === "Escape") close();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [close]);

  const commands: Command[] = useMemo(() => {
    const base: Command[] = [
      { id: "nav-dash", label: "Go to Dashboard", group: "Navigate", action: () => navigate("/") },
      { id: "nav-run", label: "Go to Run", group: "Navigate", action: () => navigate("/run") },
      {
        id: "nav-compare",
        label: "Go to Compare",
        group: "Navigate",
        action: () => navigate("/compare"),
      },
      {
        id: "nav-artifacts",
        label: "Go to Artifacts",
        group: "Navigate",
        action: () => navigate("/artifacts"),
      },
      {
        id: "demo",
        label: "Launch demo run",
        group: "Actions",
        action: async () => {
          const { run_id } = await postDemo();
          navigate(`/runs/${run_id}`);
        },
      },
    ];
    if (onEstimate) {
      base.push({
        id: "estimate",
        label: "Estimate cost (on Run page)",
        group: "Actions",
        action: () => {
          navigate("/run");
          onEstimate();
        },
      });
    }
    for (const r of runs.slice(0, 12)) {
      base.push({
        id: `run-${r.run_id}`,
        label: `Open run ${r.run_id.slice(0, 8)}… — ${r.description.slice(0, 40) || r.backend}`,
        group: "Recent runs",
        action: () => navigate(`/runs/${r.run_id}`),
      });
    }
    return base;
  }, [navigate, runs, onEstimate]);

  const filtered = useMemo(() => {
    const q = query.toLowerCase().trim();
    if (!q) return commands;
    return commands.filter((c) => c.label.toLowerCase().includes(q));
  }, [commands, query]);

  if (!open) return null;

  return (
    <div
      className="modal-overlay command-palette-overlay"
      role="dialog"
      aria-modal="true"
      aria-label="Command palette"
      onClick={close}
    >
      <div
        className="command-palette panel"
        onClick={(e) => e.stopPropagation()}
        data-testid="command-palette"
      >
        <input
          type="text"
          className="command-palette-input"
          placeholder="Type a command…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          autoFocus
          data-testid="command-palette-input"
        />
        <ul className="command-palette-list">
          {filtered.length === 0 ? (
            <li className="dim">No matches</li>
          ) : (
            filtered.map((cmd) => (
              <li key={cmd.id}>
                <button
                  type="button"
                  className="command-palette-item"
                  onClick={() => {
                    cmd.action();
                    close();
                  }}
                >
                  <span className="command-group">{cmd.group}</span>
                  {cmd.label}
                </button>
              </li>
            ))
          )}
        </ul>
        <p className="dim command-palette-hint">⌘K · Esc to close</p>
      </div>
    </div>
  );
}
