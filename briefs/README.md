# briefs/ — PM → executer outbox

One file per stage attempt, written by the PM **before** spawning a `swe-executer`.

- `stage-<N>.md` — the brief for stage N.
- `stage-<N>-r<k>.md` — retry k of stage N (after a failed review), with a
  "Corrections required:" section.

Format and the loop that produces these: see `../ORCHESTRATION.md`.
These are working artifacts, not part of the shipped pipeline.
