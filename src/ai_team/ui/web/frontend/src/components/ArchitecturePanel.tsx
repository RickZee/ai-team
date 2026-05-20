import type { ArchitecturePanelData } from "../types";

interface ArchitecturePanelProps {
  data: ArchitecturePanelData | null;
  loading: boolean;
}

export function ArchitecturePanel({ data, loading }: ArchitecturePanelProps) {
  if (loading) return <div className="empty-state">Loading architecture…</div>;
  if (!data || (data.source === "empty" && !data.markdown_fallback)) {
    return <div className="empty-state">No architecture artifact found for this run.</div>;
  }

  if (data.markdown_fallback) {
    return (
      <div className="arch-panel" data-testid="architecture-panel">
        {data.source && <p className="artifact-source">Source: {data.source}</p>}
        <pre className="arch-markdown">{data.markdown_fallback}</pre>
      </div>
    );
  }

  return (
    <div className="arch-panel" data-testid="architecture-panel">
      {data.source && <p className="artifact-source">Source: {data.source}</p>}
      {data.system_overview && (
        <section>
          <h4>Overview</h4>
          <p>{data.system_overview}</p>
        </section>
      )}
      {data.ascii_diagram && (
        <section>
          <h4>Diagram</h4>
          <pre className="arch-diagram">{data.ascii_diagram}</pre>
        </section>
      )}
      {data.components.length > 0 && (
        <section>
          <h4>Components</h4>
          <ul className="arch-list">
            {data.components.map((c) => (
              <li key={c.name}>
                <strong>{c.name}</strong> — {c.responsibilities}
              </li>
            ))}
          </ul>
        </section>
      )}
      {data.technology_stack.length > 0 && (
        <section>
          <h4>Technology stack</h4>
          <table className="arch-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Category</th>
                <th>Justification</th>
              </tr>
            </thead>
            <tbody>
              {data.technology_stack.map((t) => (
                <tr key={`${t.name}-${t.category}`}>
                  <td>{t.name}</td>
                  <td>{t.category}</td>
                  <td>{t.justification}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}
      {data.deployment_topology && (
        <section>
          <h4>Deployment</h4>
          <p>{data.deployment_topology}</p>
        </section>
      )}
      {data.adrs.length > 0 && (
        <section>
          <h4>ADRs</h4>
          {data.adrs.map((adr, i) => (
            <details key={i} className="adr-block">
              <summary>{String((adr as { title?: string }).title || `ADR ${i + 1}`)}</summary>
              <pre>{JSON.stringify(adr, null, 2)}</pre>
            </details>
          ))}
        </section>
      )}
    </div>
  );
}
