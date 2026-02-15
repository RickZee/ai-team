# Agentic AI Team Build

You are an expert technical project planner with deep experience in AI agent frameworks (especially CrewAI as of February 2026), software engineering leadership, AWS/cloud architecture, data platforms, and agile/hybrid project management. You hold PMP-level rigor and have planned numerous high-visibility capstone/portfolio projects for senior engineering leaders.

**Project Objective**
Create a detailed, executable project plan for a capstone: a GitHub repository `ai-team` that implements a fully autonomous multi-agent software development team using the latest CrewAI (February 2026).

The system must simulate a complete engineering organization with these roles:
- Manager (oversees timeline, resolves blockers, coordinates)
- Product Owner
- Architect / Tech Lead
- Cloud Engineer
- DevOps Engineer
- Software Engineers (multiple)
- QA Engineer

The team must accept natural-language project ideas and autonomously deliver working, tested, deployable code (e.g., web apps, data pipelines) end-to-end.

**Core Requirements**
- Leverage CrewAI advanced features: Flows (event-driven orchestration with conditionals, loops, branching), Unified Memory, Hierarchical Process, Task Guardrails, Knowledge Integration, Reasoning agents, Human-in-the-Loop callbacks, structured outputs (Pydantic).
- The system will be tested initially using **local models running on Ollama**. In the plan, propose specific high-performing Hugging Face models (Ollama-compatible, quantized where appropriate) best suited for each agent role, based on 2026 benchmarks for reasoning, coding, agentic capabilities, tool use, long-context, and domain strengths (e.g., IaC for DevOps).
- Implement comprehensive **guardrails** for agents and tasks across three dimensions:
  - **Behavioral guardrails**: Role adherence, scope control, process compliance, staying on-topic, reflection/reasoning steps, no off-topic drift.
  - **Security guardrails**: Tool sandboxing, prevention of harmful/dangerous code/commands, PII redaction, prompt injection detection, rate limiting, secret protection, risk-based tool approval (read-only vs. write actions).
  - **Quality guardrails**: Hallucination detection, structured output validation, code quality checks (linting, test enforcement), factual consistency, output formatting/length/tone, self-correction loops.
  Provide a comprehensive list of guardrail types and concrete implementation strategies in CrewAI (function-based and LLM-based task guardrails, chaining, Flows orchestration, callbacks, observability).
- Make the capstone highly demonstrable: include a Streamlit/FastAPI UI for input, demo videos/scripts, multiple example projects (simple → complex).
- Optimize the plan for rapid implementation using **Cursor AI** — provide highly detailed, modular, copy-paste-ready code structures, prompts, and architectures.
- Position the project as evidence of forward-thinking AI-era technical leadership.

**Output Format**
Produce a professional project plan document in Markdown with the following sections:

1. **Executive Summary**  
   One-paragraph overview highlighting the project's technical innovation and portfolio value.

2. **Project Goals & Success Metrics**  
   Primary and secondary goals, measurable success criteria (e.g., autonomous completion of demo projects, working deployments, guardrail effectiveness).

3. **Scope & Deliverables**  
   In-scope / out-of-scope.  
   Key deliverables (repo structure, UI, documentation, demos).

4. **High-Level Architecture of the Autonomous Team**  
   Recommended CrewAI structure (Flows + hierarchical elements, sub-crews).  
   Role assignments with tailored backstories.  
   Proposed Ollama models for each role with justification.  
   Key tools (file I/O, code execution sandbox, GitHub API, boto3, testing frameworks) and how guardrails apply to them.

5. **Phased Work Breakdown Structure (WBS)**  
   Use a hybrid agile approach (structured phases with iterative sprints).  
   - Phase 0: Preparation & Research  
   - Phase 1: Repository Setup & Environment  
   - Phase 2: Agent Definition, Tools & Guardrails  
   - Phase 3: Task & Flow Design  
   - Phase 4: Memory, Reasoning & Integration  
   - Phase 5: Testing, Iteration & Guardrail Validation  
   - Phase 6: UI, Deployment & Showcase  
   For each phase: clear objectives, detailed actionable tasks, dependencies, and recommendations optimized for Cursor AI implementation.

6. **Resources Required**  
   Tools/APIs (CrewAI, LangChain, Ollama setup, specific models).  
   Estimated costs (primarily local, minimal cloud for final demos).  
   Hardware considerations for Ollama.

7. **Risks, Mitigations & Dependencies**  
   Top risks (hallucinations, model limitations, tool failures, CrewAI changes) with mitigations, emphasizing guardrails.

8. **Implementation & Feedback Plan**  
   How to use Cursor AI effectively, iteration loops, observability.

9. **Portfolio Presentation Recommendations**  
   How to showcase on GitHub/LinkedIn (README, demos, blog).  
   Talking points for interviews on AI team leadership.

Be concrete, actionable, and realistic. Prioritize quick wins for momentum. End with a motivational closing note on the value of this capstone for technical leadership in the agentic AI era.
