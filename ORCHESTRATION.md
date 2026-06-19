# ORCHESTRATION.md — Autonomous PM ↔ Executer Loop

> How the **PM** (the persistent main Claude Code session) drives **swe-executer**
> subagents through the stages in `PLAN.md` without Asaf in the routine loop.
> `CLAUDE.md` = rules. `PLAN.md` = stage tracker. `QA_checklist.md` = verification.
> `NOTES.md` = decision log. This file = the loop protocol that wires them together.

---

## Roles

| Role | Who | Lifetime | Notes |
|---|---|---|---|
| **PM** | the main session (you talk to it) | the whole project | owns CLAUDE/PLAN/QA/NOTES; reviews; advances |
| **Executer** | a `swe-executer` subagent, spawned per stage | one stage, then dies | **cold every spawn** = a fresh engineer per stage |

The PM does **not** exit and reactivate. It stays running and *spawns* a cold executer
per stage; the executer's handback returns inline. That is what removes Asaf from the loop.

## Shared memory (two layers)

- **Ledger (durable state):** `PLAN.md` (stage + status), `NOTES.md` (decisions/handbacks),
  `QA_checklist.md` (how to verify). These persist across the whole project.
- **Mailbox (per-stage message bus):**
  - `briefs/stage-<N>[-r<k>].md` — PM → executer (one file per attempt; `-r<k>` = retry k).
  - `handbacks/stage-<N>[-r<k>].md` — executer → PM.

No database. Subagents read/write files natively, so the repo files *are* the shared memory.

---

## The loop (PM runs this)

```
current = first stage in PLAN.md whose status is not ✅
attempt = 0
loop:
    write briefs/stage-<current>[-r<attempt>].md       # tight brief (format below)
    spawn swe-executer subagent, prompt = "Execute the brief at <that path>."
    read its returned handback (also on disk at handbacks/...)

    REVIEW (PM does this itself, does not trust the handback blindly):
      - re-run / spot-check the stage's QA check IDs
      - verify any number against the source data file
      - confirm import-safety / no-eval / no-framework / catalog-by-name still hold

    decide:
      A) handback has DECISION-NEEDED, or stage needs an open-question/secret,
         or it requests a tool-signature / schema / policy-constant / loop-contract /
         graded-literal change:
             -> update PLAN/NOTES, **HALT and ask Asaf**          [decision gate]
      B) QA clean:
             -> mark stage ✅ in PLAN.md; append handback to NOTES.md;
                current = next stage; attempt = 0; continue
      C) QA failed:
             attempt += 1
             if attempt < 2: write briefs/stage-<current>-r<attempt>.md with
                             specific corrections; respawn a fresh executer   [auto-retry once]
             else: **HALT and ask Asaf**                          [2×-fail gate]

    if no stages remain: report "project complete", stop.
```

### Halt policy (Asaf's gate — decided 2026-06-18)

The PM auto-advances every clean stage. It **halts and asks Asaf only** on:

1. **Decision / open-question / secret** — e.g. OQ-2 (firecrawl pin), OQ-4 (RRF k/tiers),
   OQ-7 (keys/host), or any unspecified architectural/scope choice.
2. **Contract-change request** — a tool signature, JSON schema, policy constant, the loop
   contract, or a graded literal would have to change.
3. **Second consecutive QA failure** on the same stage (1 auto-retry, then halt).

Everything else proceeds autonomously.

---

## Brief format (`briefs/stage-<N>.md`)

```markdown
# Brief — Stage <N>: <name>
Read first: CLAUDE.md → PLAN.md → QA_checklist.md → NOTES.md, then this brief.

Goal: <one sentence from PLAN.md>
Scope (do ONLY this stage): <bullets>
QA checks to PASS (run, not inspect): <IDs, e.g. ENV4, CAT1–CAT6, AG1–AG6>
Constraints (from CLAUDE.md): <the ones that bite this stage>
Inputs / files you may touch: <paths>
Do NOT: advance past this stage; change a tool signature/schema/policy constant/
        loop contract/graded literal — surface those as DECISION-NEEDED.
Deliver: write handbacks/stage-<N>.md in the standard format; return it as your final message.
```

(On a retry, add a top section "Corrections required:" listing exactly what failed and
what must change; keep the rest.)

## Handback format

Defined in `.claude/agents/swe-executer.md` and mirrors `CLAUDE.md` §12 / `PLAN.md`
"Standard stage handback format". Item 5 **DECISION-NEEDED** is the halt trigger.

---

## Kickoff

Start a work block by telling the PM session once:

> "You are the PM. Run the ORCHESTRATION.md loop from the current PLAN.md stage.
>  Auto-advance clean stages; halt only on decision/open-question/secret, a
>  contract-change request, or a 2nd QA failure."

Or run the `/pm-run` command, which says the same thing.

## Defaults (decided 2026-06-18)

- Executer model: **Sonnet** (cheaper); PM stays on its session model.
- Retry budget: **1 auto-retry**, then halt.
- Reviewer independence: the PM **runs** QA checks itself — it never marks a stage ✅
  on the executer's word alone.

## Caveats

- Each executer is cold and re-reads CLAUDE/PLAN/QA/NOTES + brief — the cost of "fresh
  engineer per stage". Keep briefs tight.
- Subagents are non-interactive: an executer cannot ask mid-stage. It surfaces questions
  via DECISION-NEEDED, which the PM turns into a halt.
- No git in this repo yet. If per-stage rollback is wanted, `git init` lets the PM tag
  each ✅ stage.
