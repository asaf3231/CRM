---
description: Resume the autonomous PM ↔ executer orchestration loop from the current stage.
---

You are the **PM** for the ReactFirst Outbound Engine. Run the loop defined in
`ORCHESTRATION.md`.

1. Read `CLAUDE.md` → `PLAN.md` → `QA_checklist.md` → `NOTES.md`, then `ORCHESTRATION.md`.
2. Identify the first stage in `PLAN.md` whose status is not ✅ — that is the current stage.
3. For the current stage: write `briefs/stage-<N>.md` (format in ORCHESTRATION.md), then
   spawn a **swe-executer** subagent with the prompt "Execute the brief at briefs/stage-<N>.md."
4. When it returns, **review yourself** — re-run/spot-check the stage's QA check IDs and
   verify any number against source data. Do not trust the handback blindly.
5. Advance per the halt policy:
   - clean → mark ✅ in `PLAN.md`, append the handback to `NOTES.md`, move to the next stage;
   - failed → 1 auto-retry with a corrected brief (`-r1`), then HALT if it fails again;
   - DECISION-NEEDED / open-question / secret / contract-change → **HALT and ask Asaf**.
6. Continue stage by stage until all are ✅ or a halt fires. Report at each halt and at completion.

$ARGUMENTS
