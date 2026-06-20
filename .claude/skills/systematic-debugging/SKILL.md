---
name: systematic-debugging
description: Use when a QA check fails, a test is red, or behavior is wrong and the cause is not obvious — especially on a stage retry. A disciplined 4-phase root-cause loop that stops guess-and-check patching. Adapted from superpowers systematic-debugging for the ReactFirst pipeline.
---

# Systematic debugging

Use this the moment a fix is not obvious — do **not** start changing lines hoping one
sticks. On a stage **retry** (a `-r<k>` brief), running this loop is expected, not optional.

## Phase 1 — Reproduce

- Get a single, deterministic command that fails. For this repo that is almost always a
  `pytest` invocation: `pytest tests/<file>::<test> -x -q`.
- Quote the exact failure (assertion, traceback, or wrong value). If you cannot reproduce
  it on demand, you are not ready to fix — keep narrowing until you can.
- Confirm it fails for the reason you think (read the assertion, not just red/green).

## Phase 2 — Isolate

- Bisect: which file, which function, which line produces the wrong value? Add a focused
  print/log or run the function directly in a `python -c` one-liner; remove it after.
- Check the obvious project traps first:
  - import-safety (`ENV4`) — did something construct a client/model/store at import?
  - catalog access by name vs index; coercion of `Historical_Social_Incidents` to int.
  - a policy chokepoint bypassed (auth gate, ≤3 ceiling, byte-exact `FALLBACK_MESSAGE`).
  - a mock not wired (LLM/Firecrawl/SerpAPI/Tavily must be mocked in logic tests).
- State the smallest input that triggers the bug.

## Phase 3 — Hypothesize and test the cause

- Write one sentence: "The bug is X because Y." It must explain *the actual observed
  value*, not a plausible-sounding story.
- Prove it cheaply before fixing: a print, a breakpoint value, or a one-line experiment
  that would be true iff the hypothesis holds. If the experiment refutes it, go back to
  Phase 2 — do not patch on a hunch.

## Phase 4 — Fix and verify

- Make the **smallest** change that addresses the proven root cause. No drive-by edits,
  no widening a contract, no touching files outside the stage's lane.
- Re-run the exact failing command from Phase 1 → green.
- Re-run the stage's full QA check set → green. Then the broader regression if the change
  could ripple (`pytest -q`).
- If the real fix would require changing a tool signature, schema, policy constant, the
  loop contract, or a graded literal — **stop** and surface it as `DECISION-NEEDED`. A
  contract change is never a debugging shortcut.

## Anti-patterns (do not do these)

- Changing several things at once so you cannot tell which fixed it.
- "Fixing" the test instead of the code to make red go green.
- Swallowing the error (bare `except`, silent default) instead of finding the cause.
- Declaring it fixed without re-running the command that was red.
