# Brief — Stage 13: Layer 6a — Outreach Engine core
Read first: CLAUDE.md → PLAN.md (Stage 13 + Phase 2) → QA_checklist.md (§10, `OUT1`–`OUT6`) → NOTES.md (2026-06-19 Phase 2 entry + Stage 10–12 handbacks), then this brief.

Goal: Make the engine actually ACT — cohort scheduling, a governed **mocked** dispatch, and an escalation
path — as **deterministic post-loop engine functions** (NOT LLM tools). **Tool count stays 10**
(no `TOOL_SCHEMAS`/`TOOL_DISPATCH` change). Re-skin of SLED Layer-6 "Outreach Engine / Vixen".

## Scope — do ONLY Stage 13
`schedule_outreach_cohort`, `dispatch_outreach`, `escalate_prospect`, and `tests/test_outreach.py`.
No L6b analytics (Stage 14), no end-to-end `main()` wiring yet (Stage 14). Do NOT add any LLM tool.

## Where the code goes
Put these in `main.py` Section 8 (Gateway + policies), right AFTER `route_prospect` (`main.py:2475`),
since they are governance/outbound engine functions. They are plain module functions, not tools.

## The functions to build

### 1) `schedule_outreach_cohort(leads, daily_cap=DAILY_SEND_CAP) -> dict`  (OUT1)
- Batches `leads` (a list — e.g. CRM lead dicts or domains) into cohorts of size **≤ daily_cap**
  (`DAILY_SEND_CAP=50`, `main.py:57` — this WIRES the previously-dead constant).
- Deterministic, order-preserving chunking. Return:
  ```python
  {"cohorts": [[...], [...]], "cohort_count": int, "total_leads": int, "daily_cap": int}
  ```
- No cohort may exceed `daily_cap`. `daily_cap <= 0` → treat as a clean error dict (don't divide by zero).

### 2) `dispatch_outreach(target_email, caller_key, channel, payload, sender=None) -> dict`  (OUT2–OUT5)
A **mocked** governed sender. Order of checks matters:
1. **Policy-4 auth (OUT4):** `rec = lead_store.authenticate_and_get_contact(caller_key, target_email)`.
   If `rec.get("error")` → return `{"sent": False, "reason": "unauthorized"}` — generic, leaks NO field,
   NO key (OUT5). Do not reveal whether the record exists.
2. **Opt-out (OUT3):** if `lead_store.is_opted_out(rec)` → return `{"sent": False, "reason": "opted_out"}`.
   An opted-out contact is **never** dispatched, regardless of fit.
3. **Gateway (OUT4):** `gw = gateway_validate(payload)`; if `not gw["valid"]` → return
   `{"sent": False, "reason": "gateway_rejected", "error": gw["error"]}`. A rejection ABORTS the send —
   structured return, never a raise.
4. **Egress isolation (OUT2):** the ONLY host this function may contact is `OUTREACH_SUBDOMAIN`
   (`outreach.reactfirst.ai`, `main.py:98`). Build the send URL from `OUTREACH_SUBDOMAIN` and pass it to
   the injectable `sender(url, data)` (mirror `route_prospect`'s `slack_poster=None` pattern; default to
   `urllib.request.urlopen`). `channel` ∈ {"email", "linkedin", "form"} is metadata only — ALL channels
   route through the single isolated subdomain (network-isolation envelope, CLAUDE.md §5). Never contact
   any other host.
5. On success return `{"sent": True, "channel": channel, "host": OUTREACH_SUBDOMAIN, "target": target_email}`
   — NO `corporate_access_key`, NO record PII beyond the target email, NO secret.
- Log the dispatch via `dual_log` WITHOUT any key/secret (OUT5).
- Wrap in `try/except` → `{"sent": False, "reason": "error", "error": str(exc)}` (never crash the caller).

### 3) `escalate_prospect(routing_result, approved, escalator=None) -> dict`  (OUT6)
- Handles an unanswered borderline (Slack-gated) approval. Input is a `route_prospect` result dict.
- If `routing_result.get("action") == "slack_gate"` and `approved` is falsy → ESCALATE: call the
  injectable `escalator(payload)` (mocked — stands in for "send escalation email + book calendar"),
  return `{"action": "escalated", "domain": routing_result.get("domain"), "escalated": True}`.
- If already approved, or not a slack_gate result → `{"action": "no_escalation", "escalated": False}`.
- **Do NOT modify `route_prospect`** — it is graded (TG1/TG2). This is a separate, additive sibling.
- Never leak the Slack webhook URL or any secret.

## Hard constraints (graded)
- `DAILY_SEND_CAP` is now enforced, not advisory (OUT1).
- Single egress host `OUTREACH_SUBDOMAIN` for all dispatch (OUT2 / INT1 extension). No other network host.
- Opt-out and the Policy-4 auth gate are honored on every dispatch (OUT3/OUT4); the gate is the existing
  `lead_store` chokepoint — do not reimplement auth.
- No secret in any return/log/tracked file (OUT5 / G4).
- `route_prospect` byte-stable (OUT6). Import-safe (ENV4) — no network/client at import.
- Tool count stays 10; no schema/dispatch/assert change.

## Testing — `tests/test_outreach.py` (TDD; PM runs the full suite)
Reuse the `tests/test_lead_store.py` fixture (seed a mongomock contacts store from a temp `contacts.json`
with synthetic keys `TestKey001` etc.; reset `lead_store._collection_instance=None`). Inject `sender`
and `escalator` stubs that RECORD their calls (so tests assert the host + that opted-out/unauth never
reach the sender). Cover:
- `OUT1` cohorts never exceed `DAILY_SEND_CAP`; 120 leads → 3 cohorts (50/50/20); deterministic; cohort_count/total correct; `daily_cap<=0` clean error.
- `OUT2` a successful dispatch calls `sender` with a URL whose host is `OUTREACH_SUBDOMAIN` and NO other host; assert the sender is never called with any other host.
- `OUT3` opted-out contact → `{"sent": False, "reason": "opted_out"}` and the `sender` stub is **never called**.
- `OUT4` no-key / wrong-key → `{"sent": False, "reason": "unauthorized"}`, sender never called, no field leaked; a payload that fails `gateway_validate` (e.g. bad domain) → `{"sent": False, "reason": "gateway_rejected"}`, sender never called.
- `OUT5` no `corporate_access_key`/secret in any return or in what is passed to `sender`/`dual_log`.
- `OUT6` `escalate_prospect`: slack_gate + not approved → `escalated=True` and `escalator` called; approved → `no_escalation`; `route_prospect`'s existing behaviour/keys unchanged (call it on a clear-cut case → still `auto_proceed`).
- Use only synthetic keys/data — no real `corporate_access_key`/catalog literals.

## Do NOT
- Advance past Stage 13 (no analytics, no `main()` wiring). Do not modify `route_prospect`,
  `lead_store.py` auth semantics, `gateway_validate`, `evaluate_icp_tags`, the RRF engine, or any graded literal.
- **Do not edit PLAN.md status** — leave stage status to the PM. (Append your handback to NOTES.md.)
- Any contract change beyond this brief → **DECISION-NEEDED**, then stop.

## Deliver
Write `handbacks/stage-13.md` (CLAUDE.md §12 format): what changed; DoD `OUT1`–`OUT6` (drafted vs
written); tests written; decisions; deviations; blockers; one next action. Append to NOTES.md and return
it as your final message.
