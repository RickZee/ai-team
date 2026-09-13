/** Onboarding explainer for the empty Home state. */
export function HowItWorks() {
  return (
    <div className="how-it-works measure" data-testid="how-it-works">
      <h2>How it works</h2>
      <ol className="how-it-works-steps">
        <li>
          <strong>Describe</strong> — write a project brief and pick a backend.
        </li>
        <li>
          <strong>Watch agents build</strong> — follow phases, agents, and guardrails on the run
          detail page.
        </li>
        <li>
          <strong>Browse artifacts</strong> — inspect generated code, tests, and architecture when
          the run completes.
        </li>
      </ol>
      <p className="text-muted how-it-works-cost">
        Real runs may incur LLM cost. CrewAI and LangGraph need <code>OPENROUTER_API_KEY</code>;
        Claude Agent SDK needs <code>ANTHROPIC_API_KEY</code>.
      </p>
    </div>
  );
}
