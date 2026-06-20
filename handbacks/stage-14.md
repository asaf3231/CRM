# Handback — Stage 14

## 1. What changed

### Files modified
- **`main.py`** — added two new plain functions (NOT LLM tools) in §8g (after `escalate_prospect`, before Section 9):
  - `outreach_status_brief(state: dict) -> dict` (OUT7) — deterministic morning-brief rollup.
  - `run_outreach_pipeline(leads, *, sender=None, daily_cap=DAILY_SEND_CAP) -> dict` (OUT8/OUT9) — post-loop L6 orchestrator.
  - Updated `main()` (§11) to wire L6 after the loop returns: if `result != FALLBACK_MESSAGE` and the CRM workspace has outbound-eligible leads, calls `run_outreach_pipeline` and logs the brief. Wrapped in try/except (RS5).

- **`MANIFEST.txt`** — added `crm_store.py` to the allowlist (OUT10/H5).

### New test file
- **`tests/test_outreach_center.py`** — 31 new tests covering OUT7–OUT10 + INT1/INT2/G1 extensions.

### Files NOT touched (graded contracts preserved)
- `answer_question` signature/return/termination/cap/dispatch/gateway/FALLBACK_MESSAGE — byte-stable.
- `dispatch_outreach`, `route_prospect`, `gateway_validate`, `lead_store` auth semantics — untouched.
- `TOOL_SCHEMAS`, `TOOL_DISPATCH`, tool count (stays 10) — untouched.
- `FALLBACK_MESSAGE` constant — untouched.

---

## 2. DoD checklist

| Check | Status | How verified |
|---|---|---|
| `OUT7` outreach_status_brief deterministic rollup | ✅ written + test-verified | 12 tests in TestOUT7OutreachStatusBrief; behavioral probe |
| `OUT8` end-to-end offline test | ✅ written + test-verified | TestOUT8EndToEnd (happy path + no-match) |
| `OUT9` idempotent re-run | ✅ written + test-verified | TestOUT9Idempotency (sender not called 2nd run) |
| `OUT10` crm_store.py in MANIFEST.txt; ENV4 holds; regression green | ✅ written + test-verified | TestOUT10Packaging; ENV4 subprocess probe |
| re-run `INT1` subdomain isolation | ✅ test-verified | TestINT1EgressIsolation (AST check); test_integration.py still 30/30 |
| re-run `INT2` auth gate honored | ✅ test-verified | TestINT2AuthGate; test_integration.py still 30/30 |
| re-run `INT3` idempotent re-run | ✅ test-verified | test_integration.py TestINT3 still 3/3 |
| re-run `H1`–`H5` packaging hygiene | ✅ test-verified | test_integration.py 30/30; H5 MANIFEST updated |

---

## 3. QA results

### Command + output

```
Command: .venv/bin/python -m pytest tests/ -q --tb=no
Output (final):  678 passed, 1 skipped, 245 warnings in 30.82s
```

Baseline before Stage 14: **647 passed, 1 skipped, 0 failed**
Stage 14 adds: **31 new tests** (678 - 647 = 31)
S10 skipped: live API key not set (expected, unchanged)

```
Command: .venv/bin/python -m pytest tests/test_outreach_center.py -q --tb=no
Output: 31 passed, 1 warning in 0.57s
```

```
Command: ENV4 subprocess probe (empty /tmp dir)
Output: ENV4 PASS: all 4 modules import clean; all lazy singletons are None
```

### Behavioral probes run

- Probe 1: `outreach_status_brief` deterministic rollup — PASS (cohort_count=2, sent=3, failed=1, replies=0, reply_rate=0.0, variants A=2 B=1)
- Probe 2: reply rate = 0.2 for 10 sends (10//5=2 replies) — PASS
- Probe 3: `FALLBACK_MESSAGE` byte-exact — PASS
- Probe 4: tool count=10, new fns not in TOOL_SCHEMAS — PASS
- G1 grep: no `eval(` / `exec(` in new code — PASS

---

## 4. Decisions made

### A/B variant tag rule
Variant assigned by **lead index parity** within the ordered cohort list (across all cohorts, global index):
- Even index (0, 2, 4, ...) → variant `"A"`
- Odd index  (1, 3, 5, ...) → variant `"B"`

Same input always produces the same assignments. Stored in the `dispatch_result["variant"]` key and counted in `outreach_status_brief`.

### Reply-rate rule (mocked analytics)
```
replies = max(0, sent // 5)   # one reply per 5 sends (integer division)
reply_rate = replies / sent if sent > 0 else 0.0
```
This is a deterministic fixed-ratio mocked metric — not real network data. Documented in the function docstring.

### `run_outreach_pipeline` lead shape contract
Leads list items must be dicts with at minimum:
- `"email"` (str) — required; leads without it are silently skipped with `reason: "missing_email"`.
- `"caller_key"` (str) — for the auth gate inside `dispatch_outreach`.
- `"domain"` (str) — used as the CRM workspace key for OUT9 idempotency.
- `"angle_key"` (str) — included in the outbound payload.

### INT1 test approach
The INT1 test uses AST analysis (Name + Attribute node walk) rather than substring search, so docstring mentions of `OUTREACH_SUBDOMAIN` in `run_outreach_pipeline` do not falsely trigger. Only functional code references are checked.

### `main()` L6 wiring
`crm_store.outbound_eligible_contacts()` is called to retrieve CRM workspace leads after `write_qualified_leads` has upserted them. If that list is empty or the CRM has no eligible leads, L6 is silently skipped. Any L6 exception is logged but never crashes `main()`.

---

## 5. DECISION-NEEDED

None. No tool signatures, JSON schemas, policy constants, loop contract, or graded literals were changed.

---

## 6. Deviations

None from the brief. All hard constraints honored:
- `answer_question` graded contract byte-stable (signature, return, cap, fallback, dispatch, gateway).
- `run_outreach_pipeline` does NOT reference `OUTREACH_SUBDOMAIN` in functional code (AST-verified).
- Tool count stays 10; no schema/dispatch/assert change.
- `crm_store.py` added to `MANIFEST.txt` as specified.

---

## 7. Blockers / risks

None. All transports mocked. Live smokes still gated on OQ-7 (API keys). No new external dependencies introduced.

---

## 8. Next recommended action

Stage 14 is complete. The PM should:
1. Run the full regression independently (`tests/` in `.venv`): **678 passed, 1 skipped, 0 failed**.
2. Verify ENV4 from an empty tmp dir (all 4 singletons None).
3. Check `MANIFEST.txt` includes `crm_store.py`.
4. Mark Stage 14 ✅ in `PLAN.md` and close Phase 2.
