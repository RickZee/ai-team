/** Onboarding explainer for the empty Dashboard state. */
export function HowItWorks() {
  return (
    <div className="how-it-works" data-testid="how-it-works">
      <h3>How it works</h3>
      <ol className="how-it-works-steps">
        <li>
          <strong>Describe</strong> — write a project brief on the Run tab and pick a backend.
        </li>
        <li>
          <strong>Watch agents build</strong> — follow phases, agents, and guardrails live on the
          Dashboard.
        </li>
        <li>
          <strong>Browse artifacts</strong> — inspect generated code, tests, and architecture when
          the run completes.
        </li>
      </ol>
      <p className="dim how-it-works-cost">
        Real runs may incur LLM cost. CrewAI and LangGraph need <code>OPENROUTER_API_KEY</code>;
        Claude Agent SDK needs <code>ANTHROPIC_API_KEY</code>.
      </p>
    </div>
  );
}
