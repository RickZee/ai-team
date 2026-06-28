import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useFocusTrap } from "../hooks/useFocusTrap";
import { postDemo } from "../hooks/useApi";
import type { UnifiedRun } from "../hooks/useUnifiedRuns";

interface CommandPaletteProps {
  runs: UnifiedRun[];
}

interface Command {
  id: string;
  label: string;
  group: string;
  action: () => void;
}

const SAMPLE_RUN_LABEL = "Play sample run (free · no files)";

export function CommandPalette({ runs }: CommandPaletteProps) {
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [selectedIndex, setSelectedIndex] = useState(0);
  const panelRef = useRef<HTMLDivElement>(null);

  const close = useCallback(() => {
    setOpen(false);
    setQuery("");
    setSelectedIndex(0);
  }, []);

  useFocusTrap(open, panelRef);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setOpen((v) => !v);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

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
        id: "estimate",
        label: "Estimate cost (opens Run page)",
        group: "Actions",
        action: () => navigate("/run?estimate=1"),
      },
      {
        id: "demo",
        label: SAMPLE_RUN_LABEL,
        group: "Actions",
        action: async () => {
          const { run_id } = await postDemo();
          navigate(`/runs/${run_id}`);
        },
      },
    ];
    for (const r of runs.slice(0, 12)) {
      base.push({
        id: `run-${r.run_id}`,
        label: `Open run ${r.run_id.slice(0, 8)}… — ${r.description.slice(0, 40) || r.backend}`,
        group: "Recent runs",
        action: () => navigate(`/runs/${r.run_id}`),
      });
    }
    return base;
  }, [navigate, runs]);

  const filtered = useMemo(() => {
    const q = query.toLowerCase().trim();
    if (!q) return commands;
    return commands.filter((c) => c.label.toLowerCase().includes(q));
  }, [commands, query]);

  const grouped = useMemo(() => {
    const map = new Map<string, Command[]>();
    for (const cmd of filtered) {
      if (!map.has(cmd.group)) map.set(cmd.group, []);
      map.get(cmd.group)!.push(cmd);
    }
    return [...map.entries()];
  }, [filtered]);

  const flatFiltered = useMemo(() => grouped.flatMap(([, items]) => items), [grouped]);

  useEffect(() => {
    setSelectedIndex(0);
  }, [query]);

  const runSelected = useCallback(
    (cmd: Command) => {
      cmd.action();
      close();
    },
    [close],
  );

  const onPaletteKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Escape") {
      e.preventDefault();
      close();
      return;
    }
    if (flatFiltered.length === 0) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setSelectedIndex((i) => (i + 1) % flatFiltered.length);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setSelectedIndex((i) => (i - 1 + flatFiltered.length) % flatFiltered.length);
    } else if (e.key === "Enter") {
      e.preventDefault();
      runSelected(flatFiltered[selectedIndex]);
    }
  };

  if (!open) return null;

  let flatIdx = 0;

  return (
    <div
      className="modal-overlay command-palette-overlay"
      role="dialog"
      aria-modal="true"
      aria-label="Command palette"
      onClick={close}
    >
      <div
        ref={panelRef}
        className="command-palette panel"
        onClick={(e) => e.stopPropagation()}
        onKeyDown={onPaletteKeyDown}
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
          {flatFiltered.length === 0 ? (
            <li className="dim">No matches</li>
          ) : (
            grouped.map(([group, items]) => (
              <li key={group} className="command-palette-group">
                <span className="command-group-header">{group}</span>
                <ul>
                  {items.map((cmd) => {
                    const idx = flatIdx++;
                    const isActive = idx === selectedIndex;
                    return (
                      <li key={cmd.id}>
                        <button
                          type="button"
                          className={`command-palette-item ${isActive ? "active" : ""}`}
                          onClick={() => runSelected(cmd)}
                          onMouseEnter={() => setSelectedIndex(idx)}
                        >
                          {cmd.label}
                        </button>
                      </li>
                    );
                  })}
                </ul>
              </li>
            ))
          )}
        </ul>
        <p className="dim command-palette-hint">↑↓ navigate · Enter run · ⌘K · Esc close</p>
      </div>
    </div>
  );
}
