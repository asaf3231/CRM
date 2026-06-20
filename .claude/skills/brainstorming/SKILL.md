---
name: brainstorming
description: Use at the START of a new feature, stage, or non-trivial change — before any plan or code — to refine a rough idea into an agreed design. Surfaces alternatives and open questions one at a time, then presents a reviewable design for sign-off. Adapted from superpowers brainstorming for the ReactFirst PM workflow.
---

# Brainstorming

Use this when the request is a *new* feature or a non-trivial change whose design is not
yet settled. The goal is an **agreed design before a plan exists** — never jump from a
vague idea straight to `briefs/` or code. (This is the design phase that sits *before*
`PLAN.md` stage decomposition.)

For work that is already specified in `PLAN.md` and `QA_checklist.md`, skip this — go
straight to the orchestration loop.

## How to run it

1. **Restate the goal in one sentence** and the constraints that already bind it
   (CLAUDE.md non-negotiables, the 10-tool contract, policies, budget). Get agreement
   that the goal is right before exploring how.

2. **Ask questions one at a time.** Do not batch. Each answer should change the next
   question. Prioritize the questions whose answers most change the design:
   - What problem does this actually solve, and for which query class (Q1–Q6)?
   - Does it touch a graded contract (tool signature/schema/policy constant/loop
     contract/`FALLBACK_MESSAGE`)? If yes, that is an Asaf decision, not a design choice.
   - What is the smallest version that delivers the value? (YAGNI)

3. **Surface 2–3 real alternatives** with trade-offs and a recommendation — never pick
   silently. Note which alternative is cheapest in tool-calls / subagent spawns.

4. **Present the design in reviewable sections** for sign-off:
   - Goal & non-goals
   - Approach (chosen alternative + why)
   - Contract impact (none / requires Asaf decision — be explicit)
   - How it decomposes into PLAN.md stages + which QA check IDs prove each
   - Open questions / decisions needed

5. **Wait for sign-off.** Only after the design is approved do you write `PLAN.md` stages
   and the per-stage `briefs/`. Record any non-obvious decision in `NOTES.md`.

## Guardrails

- Brainstorming never edits production code or writes a brief — it produces an agreed
  design and open questions.
- If a design needs a contract change, that is a halt-and-ask-Asaf item, flagged in the
  design's "Contract impact" section — do not design around it silently.
