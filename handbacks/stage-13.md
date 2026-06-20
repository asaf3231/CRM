# Handback — Stage 13: Layer 6a — Outreach Engine core (`OUT1`–`OUT6`)

> **Provenance note:** the Stage-13 code + tests were implemented by a prior `swe-executer`
> session that was **interrupted before writing this handback** (code landed in `main.py` and
> `tests/test_outreach.py`, all green, but `handbacks/stage-13.md` and the NOTES.md append were
> never produced; PLAN status stayed ⬜). This handback was authored by the **PM at stage close**
> from an independent re-verification (full-suite run + own behavioral probes) and the
> `swe-reviewer` gate. The implementation is a faithful 1:1 of `briefs/stage-13.md` — no hidden
> executer decisions to surface.

## 1. What changed
- `main.py` §8f (inserted right after `route_prospect`, lines ~2588–2785) — three **plain
  module functions** (NOT LLM tools):
  - `schedule_outreach_cohort(leads, daily_cap=DAILY_SEND_CAP)` — wires the previously-dead
    `DAILY_SEND_CAP` (=50); deterministic order-preserving chunking; clean error dict on
    `daily_cap<=0`.
  - `dispatch_outreach(target_email, caller_key, channel, payload, sender=None)` — governed
    mocked sender; check order **auth → opt-out → gateway → egress**; egress isolated to
    `OUTREACH_SUBDOMAIN`; injectable `sender`; structured returns, never raises.
  - `escalate_prospect(routing_result, approved, escalator=None)` — additive sibling to
    `route_prospect`; escalates an unanswered `slack_gate`; injectable `escalator`.
- `tests/test_outreach.py` — NEW 45-test file (OUT1×14, OUT2×5, OUT3×2, OUT4×6, OUT5×4,
  OUT6×11, ENV4/tool-count×4 — reviewer-confirmed grouping).
- No change to `TOOL_SCHEMAS`/`TOOL_DISPATCH`/asserts (**tool count stays 10**); `route_prospect`,
  `gateway_validate`, `lead_store` auth semantics, `evaluate_icp_tags`, RRF engine all untouched.

## 2. DoD checklist (`OUT1`–`OUT6`) — written and test-verified
- ✅ `OUT1` cohorts ≤ `DAILY_SEND_CAP`(=50); 120→[50,50,20]; `daily_cap<=0`→clean error; keys
  `{cohorts,cohort_count,total_leads,daily_cap}`. *(PM probe + 14 tests)*
- ✅ `OUT2` egress isolated to `OUTREACH_SUBDOMAIN` only; all sender hosts ⊆ {outreach.reactfirst.ai}. *(PM probe + 5 tests)*
- ✅ `OUT3` `opt_out_status==True` → `{"sent":False,"reason":"opted_out"}`, sender never called. *(PM probe + 2 tests)*
- ✅ `OUT4` no-key/wrong-key identical `unauthorized`; bad payload → `gateway_rejected` (structured, no raise); sender never called on any failure. *(PM probe + 6 tests)*
- ✅ `OUT5` no `corporate_access_key`/secret in returns, logs, or sender data; no PII beyond `target_email`. *(PM probe + 4 tests + grep)*
- ✅ `OUT6` `escalate_prospect` additive; `route_prospect` byte-stable (keys + auto_proceed/slack_gate unchanged). *(PM probe + 11 tests + diff)*

## 3. QA results (run, not inspected)
- `tests/test_outreach.py` — **45/45 pass**.
- Full regression — **647 passed, 1 skipped (S10, gated on `ANTHROPIC_API_KEY`), 0 failed**
  (602 Stage-12 baseline + 45 outreach).
- ENV4 from an empty tmp dir — exit 0; `lead_store._collection_instance`, `crm_store._leads_collection`,
  `main._anthropic_client` all `None`; tool count 10; three-way name identity holds; L6 fns absent
  from schemas/dispatch.
- G1/G4 grep — no `eval(`/`exec(` in the new code; no hardcoded `corporate_access_key` in shipped code.
- `swe-reviewer` gate — APPROVE on all `OUT1`–`OUT6` code (spec + quality); CHANGES-REQUIRED was
  **documentation-only** (this handback + the NOTES append), now resolved.

## 4. Decisions made
- Egress URL `https://{OUTREACH_SUBDOMAIN}/api/outreach`; `channel` ∈ {email,linkedin,form} is
  metadata only — all channels route through the single isolated subdomain (network-isolation
  envelope, CLAUDE.md §5).
- Auth gate reused as-is (`lead_store.authenticate_and_get_contact` + `is_opted_out`) — no
  re-implementation; the single Policy-4 chokepoint is preserved.
- Stage closed without re-spawning an executer to write this handback (code was already complete,
  PM-verified, and reviewer-approved) — a deliberate budget choice by the PM; full transparency in
  the NOTES.md Stage-13 entry + PM_LOG.

## 5. Deviations
- None from `briefs/stage-13.md`. Process deviation only: handback authored by PM (not the
  interrupted executer) at stage close.

## 6. Blockers / risks
- None functional. Live transports (real `sender`/Slack/escalator) remain mocked/gated on OQ-7
  keys; live smoke deferred to Stage 14 re-run.
- Minor (logged, not changed): `dispatch_outreach` inline-imports `urllib.request`/`json` inside
  the function — cosmetic; mirrors `route_prospect`'s existing inline-import pattern; no contract impact.

## 7. Next recommended action
Dispatch **Stage 14** (L6b — Outreach Center + end-to-end `main()` wiring + packaging;
`OUT7`–`OUT10` + re-run `INT1`–`INT3`, `H1`–`H5`).
