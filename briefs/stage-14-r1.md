# Brief — Stage 14 (RETRY r1): fix the `main()` L6 wiring (OUT8)
Read first: CLAUDE.md → PLAN.md (Stage 14) → QA_checklist.md §10 (`OUT7`–`OUT10`) → NOTES.md (Stage
10–13 handbacks + your own Stage-14 handback) → `briefs/stage-14.md` → then this corrections brief.

**This is the single auto-retry.** A 2nd consecutive failure halts to Asaf. Run the
`systematic-debugging` skill (reproduce → isolate → hypothesize → fix), don't guess-and-check.

## Corrections required (reviewer `CHANGES-REQUIRED`, quoted verbatim)
> **[Important]** `main.py:3588` — `crm_store.outbound_eligible_contacts()` is called with **zero
> arguments**, but the function signature is `outbound_eligible_contacts(caller_key, uniq_id, emails)`
> with all three parameters required. This raises `TypeError` at runtime. The exception is silently
> caught by the surrounding `try/except`, so `main()` never crashes, but the L6 pipeline **never
> executes from `main()`** in production. This breaks the OUT8 "Wire into main()" DoD item. No test
> exercises this code path — the OUT8 test calls `run_outreach_pipeline` directly, bypassing `main()`.
> Additionally, the CRM records upserted by `write_qualified_leads` contain only domain-keyed brand
> records `{uniq_id, domain, status, profile, ...}` with no `email` or `caller_key` — the fields
> `run_outreach_pipeline` requires.

**Root cause:** `main()`'s post-loop L6 block (1) calls the wrong API with the wrong arity, and
(2) has no coherent way to assemble the `leads` list `run_outreach_pipeline` needs
(`{email, caller_key, domain, angle_key}` per CLAUDE.md / the L6a brief).

## The fix — PM-decided `main()` L6 data flow (implement exactly this; it is in-lane, non-graded)
The post-loop L6 stage in `main()` must build dispatch-ready leads from the CRM workspace and let
`dispatch_outreach`'s existing auth gate govern. Concretely:

1. **Add a small additive `crm_store` helper** to list workspace records, e.g.
   `all_leads() -> list[dict]` (iterate `get_crm_collection().find({})`, strip `_id` via the existing
   `_strip_id`). Additive, non-graded — no change to existing `crm_store` signatures.
2. **Add a tiny deterministic caller-key parser** in `main.py` (post-loop, no LLM), e.g.
   `_parse_caller_key(query) -> str` — a simple regex (`access key is (\S+)` / `key[:=]\s*(\S+)`,
   case-insensitive); return `""` if none found. (The key value must never be logged — OUT5/G4.)
3. **Assemble leads in `main()`** after `answer_question` returns and `result != FALLBACK_MESSAGE`:
   ```
   caller_key = _parse_caller_key(query)
   leads = []
   for rec in crm_store.all_leads():
       domain    = rec.get("domain", "")
       angle_key = (rec.get("profile") or {}).get("angle_key", "")
       for email in rec.get("contact_ids", []):       # discovered contacts (L5b)
           leads.append({"email": email, "caller_key": caller_key,
                         "domain": domain, "angle_key": angle_key})
   if leads:
       pipeline_result = run_outreach_pipeline(leads, sender=None)   # dispatch_outreach governs auth/opt-out/gateway/egress
       # log only the brief summary fields (no key, no PII beyond counts)
   ```
   - **Do NOT** use `outbound_eligible_contacts` here (it double-auths and returns sanitised contacts
     with no `caller_key` — wrong shape for the pipeline). Let the single auth happen inside
     `dispatch_outreach`. A run with no/invalid key → all sends auth-denied (the correct, safe outcome);
     a run whose query carries a valid key → sends proceed.
   - Keep the whole block wrapped in `try/except` (RS5) and the `result != FALLBACK_MESSAGE` skip.

## OUT8 test must drive the REAL `main()` path (this is why the bug slipped through)
- Add/replace an OUT8 test that calls **`main.main()`** (or the exact post-loop wiring) end-to-end —
  NOT `run_outreach_pipeline` directly. Use `test_e2e.py`'s `FakeReasoningClient` (monkeypatch
  `main._get_client`), seed a contacts store + a CRM lead with `contact_ids` + a matching
  `corporate_access_key`, put that key in the query text, inject a recording `sender`, and assert:
  (a) `run_outreach_pipeline` actually runs and the recording `sender` is called for the authorized
  contact, egressing only to `OUTREACH_SUBDOMAIN`; (b) a brief is produced/logged; (c) all under the
  15-call cap.
- Add the no-match assertion the reviewer's Minor flagged: on a `FALLBACK_MESSAGE` run, spy that
  `run_outreach_pipeline` (or `crm_store.all_leads`/dispatch) is **NOT** called — L6 skipped.
- (Minor, optional but do it) add an INT1-style check that `crm_store.py` does not reference
  `OUTREACH_SUBDOMAIN`, mirroring the `lead_store`/`rag_engine` checks (it's a shipped module now).

## Keep intact (already PASS — do not regress)
OUT7 (`outreach_status_brief`), OUT9 (idempotent replay — sender silent on 2nd pass), OUT10 (MANIFEST +
ENV4), the `answer_question` byte-stable contract, tool count 10, egress isolation
(`run_outreach_pipeline` references **no** `OUTREACH_SUBDOMAIN`), no `eval`/`exec`, no secret leak.

## Verify before handback (run, not inspect)
- New OUT8 test drives `main()` and passes; full `tests/` regression green (report the real count).
- ENV4 from an empty tmp dir (all 4 lazy singletons `None`).
- `git grep` clean: no `corporate_access_key` value / `eval(`/`exec(` in shipped code.

## Do NOT
- Touch `answer_question`'s graded contract, `dispatch_outreach`, `route_prospect`, `gateway_validate`,
  `lead_store` auth semantics, any tool schema/dispatch/assert, or any graded literal/constant.
- Edit PLAN.md status. Any contract change beyond this brief → **DECISION-NEEDED**, then stop.

## Deliver
Update `handbacks/stage-14.md` (or write `handbacks/stage-14-r1.md`) in CLAUDE.md §12 format: the fix,
the new `main()`-driving OUT8 test + its result, the `all_leads`/`_parse_caller_key` additions, the
re-run regression count, decisions, deviations, blockers, one next action. Append to NOTES.md and
return it as your final message.
