# /cloud-backends: execute the next task from the cloud-native specs

You are executing one task from the cloud-native backend specs in `.kiro/specs/`.

## Pick the task
1. Read `.kiro/specs/README.md` § *Cloud-native backends* for the order.
2. Open the first spec in that order that still has unchecked tasks, and take its
   **first unchecked task whose blockers are done**. Skip tasks marked 💲 or 🔑 unless Rick
   says in this session that he's ready for them.
3. Read that spec's `requirements.md` and `design.md` sections the task cites.

## Do the task
- Work on a branch named in the spec's *How to execute this plan*.
- Run that section's check commands before you finish, and paste the tail of each output
  into your final message.
- Don't edit the harness (`tools/bus.py`, `tools/draft.py`, `core/spend_guard.py`,
  `guardrails/`) to make a backend pass. If you believe the harness is wrong, stop and
  explain why.
- Never commit secrets, `.env`, `.tfvars`, Terraform state or `backend.hcl`.
- Never run `terraform apply` or `destroy`, and never spend money, without Rick's explicit
  go-ahead in this session.
- After any cloud session, run `infra/scripts/teardown_check.sh <cloud>` and report the result.

## Finish
- Check the task's box **only if** its Definition of done is literally true.
- Add a short `docs/journal/` entry: what changed, what you verified, anything surprising.
- End with: the task id, the files changed, the check results, the next task, and
  anything Rick has to do by hand.
