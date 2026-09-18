# Test the course

Use the `course-test` skill (`.cursor/skills/course-test/SKILL.md`) to test the course in
`course/`.

Parameters (edit before sending, or leave the defaults):

- scope: week-4,week-5   (all of it if you have the time — see skill §9 for what moved)
- mode: stranger
- budget_usd: 10   (see the spend plan in the skill, §2a)
- fix: no
- depth: build     (`walk` = type the commands only; `build` = also do §5)

Run every step as a learner who is trying to understand agentic systems, not as a
link-checker. Record observations in the first person — what you predicted, what surprised
you, what you still don't understand. Under `depth: build`, also do the build track (§5):
write the week 5 check yourself without the solution patch, make it fail on purpose, change
what it means and watch the numbers move, re-accept the baseline, take it to live traces, and
run the full pipeline. Re-run at all three scopes after every change (§5a).

Read **skill §9 first** — it names the three commits that landed since the last run and the
specific questions each one opens. Week 4 step 1 is the newest text in the course and has
never been run on a fresh clone.

Account for every step id in the coverage table (§4a) and fill in the concept ledger (§4b).
Write the report to `course/testing/runs/<date>-<mode>/report.md`. Finish by printing the
report path, the coverage percentage, and the Top 5 improvements.
