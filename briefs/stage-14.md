# Brief — Stage 14: Layer 6b — Outreach Center + end-to-end wiring + packaging
Read first: CLAUDE.md → PLAN.md (Stage 14 + Phase 2) → QA_checklist.md (§10, `OUT7`–`OUT10` + the
`INT1`–`INT3`/`H1`–`H5` lines) → NOTES.md (2026-06-19 Phase 2 entry + Stage 10–13 handbacks), then this brief.

Goal: Add the analytics/heartbeat rollup, wire L1→L5→L6 end-to-end, and re-package cleanly — as
**deterministic post-loop engine** code. **This is the FINAL backend stage.** Tool count stays **10**
(no `TOOL_SCHEMAS`/`TOOL_DISPATCH` change; L6b is plain functions, not LLM tools).

## Scope — do ONLY Stage 14
`outreach_status_brief`, a post-loop L6 orchestration wired into `main()`, the idempotency guard,
`MANIFEST.txt` refresh, and `tests/test_outreach.py` additions (or a new `tests/test_outreach_center.py`).
No new LLM tool. No new stage.

## NON-NEGOTIABLE: the graded loop contract stays byte-stable
- **Do NOT change `answer_question` (main.py:2873)** — its signature, return type (`str`),
  termination precedence, the 15-call `TOOL_CALL_CAP`, dispatch, the gateway chokepoint, and the
  Policy-6 `FALLBACK_MESSAGE` path are all graded and must not move. L6b runs **AFTER** the loop.
- The end-to-end "wiring" goes in **`main()`** (and a new helper), calling the L6 engine on the CRM
  workspace **after** `answer_question` returns. L6 adds **no LLM calls** and does not touch the cap.

## The functions to build (put in `main.py` §8f, after `escalate_prospect` ~line 2785)

### 1) `outreach_status_brief(state: dict) -> dict`  (OUT7)
- A deterministic morning-brief/heartbeat rollup over a run's L6 state (cohorts + dispatch results).
- `state` is a plain dict you define — e.g. `{"cohorts": [...], "dispatch_results": [...]}`. No network,
  no LLM, no randomness.
- Return AT LEAST these keys (extend if useful): `{"cohort_count": int, "scheduled": int, "sent": int,
  "failed": int, "replies": int, "reply_rate": float, "variants": {"A": int, "B": int}}`.
- **A/B variant tags:** assign deterministically (e.g. by lead index parity or a stable hash of the
  target) — same input ⇒ same tags. `replies`/`reply_rate` are mocked deterministic analytics
  (e.g. derived from sent count by a fixed rule); document the rule in the handback.

### 2) `run_outreach_pipeline(leads, *, sender=None, daily_cap=DAILY_SEND_CAP) -> dict`  (OUT8/OUT9)
A small deterministic post-loop orchestrator that ties L6a together:
1. `schedule_outreach_cohort(eligible_leads, daily_cap)` → cohorts (OUT1 reused).
2. For each lead in each cohort: `dispatch_outreach(target_email, caller_key, channel, payload, sender)`
   (OUT2–OUT5 reused — auth gate + opt-out + `gateway_validate` + single-host egress all already enforced
   inside `dispatch_outreach`; do NOT re-implement them).
3. `outreach_status_brief({...cohorts, dispatch_results...})` → the rollup.
4. Return `{"cohorts": [...], "dispatch_results": [...], "brief": {...}}`.
- **Idempotency (OUT9):** a successful dispatch marks the lead as sent in the CRM workspace
  (`crm_store`’s `outreach_state`, e.g. `{"sent": True}` via `update_lead_stage`/`upsert_lead`).
  The orchestrator **skips leads already marked sent**, so a replay produces identical cohorts/brief and
  **zero new sends**. Keep it deterministic and order-preserving.

### 3) Wire into `main()`  (OUT8)
- After `answer_question(...)` returns in `main()`, if the result is **not** `FALLBACK_MESSAGE` and the
  CRM workspace has outbound-eligible leads, call `run_outreach_pipeline(...)` (default `sender` = the
  real urlopen; mocked in tests) and log the brief. On a **no-match run** (`answer_question` returned the
  byte-exact `FALLBACK_MESSAGE`), **skip L6 entirely** — no cohorts, no dispatch — and surface the
  fallback unchanged. Wrap the L6 call so a failure never crashes `main()` (RS5).

## Packaging  (OUT10 + H-series)
- Add `crm_store.py` to the `MANIFEST.txt` allowlist (alongside `main.py`/`lead_store.py`/`rag_engine.py`).
- Re-prove **ENV4** (import `main, lead_store, rag_engine, crm_store` from an empty dir; all lazy
  singletons `None`). Full `tests/` regression must stay green.
- Optionally bump the stale `Stage: 5` line in the `main.py` header block (H4 cosmetic) — not required.

## QA checks to PASS (run, not inspect) — `tests/test_outreach.py` (or a new test file)
- `OUT7` `outreach_status_brief` deterministic rollup with the keys above + A/B tags; same input ⇒ same output.
- `OUT8` End-to-end **offline** test: reuse `test_e2e.py`’s `FakeReasoningClient`
  (monkeypatch `main._get_client`) to drive a discovery query through `answer_question` (L1 ICP +
  L5 discovery as tools, CRM upserts via `write_qualified_leads`), **all under the 15-call cap**, THEN
  call `run_outreach_pipeline` with an injected recording `sender` → cohorts → mocked dispatch → brief.
  A separate **no-match seed** still returns byte-exact `FALLBACK_MESSAGE` and triggers **no dispatch**.
- `OUT9` Idempotent re-run: calling `run_outreach_pipeline` twice on the same workspace ⇒ identical
  cohorts/brief and the `sender` stub is **not** called again on the 2nd pass (no duplicate sends).
- `OUT10` `crm_store.py` present in `MANIFEST.txt`; ENV4 holds; full regression green.
- **Re-run `INT1`–`INT3`, `H1`–`H5`** — they must stay green. `INT1` already sanctions
  `dispatch_outreach` as a 2nd `OUTREACH_SUBDOMAIN` referencer (no other host); `run_outreach_pipeline`
  must NOT reference `OUTREACH_SUBDOMAIN` itself (it only calls `dispatch_outreach`). `H5` now lists
  `crm_store.py`.

## Hard constraints (graded)
- `answer_question` loop contract byte-stable (signature/return/termination/cap/dispatch/gateway/FALLBACK).
- Single egress host `OUTREACH_SUBDOMAIN` for all sends — only via `dispatch_outreach` (OUT2/INT1). The new
  orchestrator/brief make **no** network calls of their own.
- Opt-out + Policy-4 auth gate honored on every dispatch (reused from `dispatch_outreach`, not re-implemented).
- No secret in any return/log/tracked file (OUT5/G4). Import-safe (ENV4). No raw `eval`/`exec` (G1).
- Tool count stays 10; no schema/dispatch/assert change. `FALLBACK_MESSAGE` byte-exact.

## Do NOT
- Modify `answer_question`’s graded contract, `route_prospect`, `dispatch_outreach`, `gateway_validate`,
  `lead_store` auth semantics, `evaluate_icp_tags`, the RRF engine, or any graded literal/constant.
- Add any LLM tool or change the tool count. Edit PLAN.md status (leave it to the PM).
- Any contract change beyond this brief → **DECISION-NEEDED**, then stop.

## Deliver
Write `handbacks/stage-14.md` (CLAUDE.md §12 format): what changed; DoD `OUT7`–`OUT10` + INT/H re-run
(written vs drafted); tests written + the verified counts you ran; the A/B + reply-rate rule you chose;
decisions; deviations; blockers; one next action. Append the handback to NOTES.md and return it as your
final message.
