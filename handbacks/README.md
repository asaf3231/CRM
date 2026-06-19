# handbacks/ — executer → PM inbox

One file per stage attempt, written by the `swe-executer` at the **end** of a stage,
mirroring `CLAUDE.md` §12. Item 5 (**DECISION-NEEDED**) is the loop's halt trigger.

- `stage-<N>.md` — handback for stage N.
- `stage-<N>-r<k>.md` — handback for retry k.

The PM reviews each handback (re-running QA itself), then appends the accepted result
to `NOTES.md` and advances `PLAN.md`. See `../ORCHESTRATION.md`.
These are working artifacts, not part of the shipped pipeline.
