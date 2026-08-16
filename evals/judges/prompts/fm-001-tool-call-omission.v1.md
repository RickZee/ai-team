---
judge_id: fm-001-tool-call-omission
version: 1
failure_mode_id: FM-001
question: Did the agent finish a development phase without writing the code to disk?
pass_means: The agent wrote code to disk via tool calls; no prose-only delivery.
fail_means: The agent produced code only as message text, or asked permission to save.
model: claude-haiku-4-5-20251001
provider: anthropic
evidence_builder: dev_phase_transcript
---

You are auditing one phase of an autonomous software agent's run.

Multi-agent frameworks coordinate through files on disk. Code that appears only in
an agent's message text writes nothing and is a total failure of the phase, even
when the code itself is correct.

## Evidence
{evidence}

## Decision
Answer the single question: {question}

Reply with JSON only:
{"verdict": "pass" | "fail", "reason": "<one sentence>", "evidence_quote": "<≤200 chars quoted verbatim from the evidence>"}
