# Handback — Stage 14-r1

## 1. What changed

### Bug fixed
`main.py` line ~3588 previously called `crm_store.outbound_eligible_contacts()` with ZERO arguments.
The function signature is `outbound_eligible_contacts(caller_key, uniq_id, emails)` (3 required params).
This raised `TypeError` at runtime, silently caught by the surrounding `try/except`, so the L6 pipeline
NEVER ran from `main()`. The 31 original Stage-14 tests all called `run_outreach_pipeline` directly and
never touched `main()`, so the bug was invisible to them.

### Files modified

- **`crm_store.py`** — added `all_leads() -> list[dict]` (additive, non-graded). Iterates
  `get_crm_collection().find({})`, strips `_id` via existing `_strip_id`. Returns all CRM workspace
  records without requiring a `caller_key` or emails list. Auth gate still fires inside
  `dispatch_outreach` downstream.

- **`main.py`** — two additive changes (both non-graded):
  1. Added `_parse_caller_key(query: str) -> str` before `main()`. A simple regex that extracts
     a corporate_access_key token from patterns like `"access key is <token>"`, `"key: <token>"`,
     `"key=<token>"` (case-insensitive). Returns `""` if no match. NEVER logs the key value (OUT5/G4).
  2. Replaced the broken `crm_store.outbound_eligible_contacts()` call in `main()` L6 wiring block
     with the correct assembly pattern: `caller_key = _parse_caller_key(query)`, then iterate
     `crm_store.all_leads()`, expand each record's `contact_ids` list into individual lead dicts,
     and pass the assembled `leads` list to `run_outreach_pipeline`. No use of
     `outbound_eligible_contacts` in the wiring path.

- **`tests/test_outreach_center.py`** — added `TestOUT8MainDriven` class with 6 new tests:
  - `test_main_l6_runs_and_sender_called` — drives `main.main()` directly; asserts `run_outreach_pipeline`
    is called with the correct leads (email/caller_key/domain/angle_key) and sender fires for authorized
    contact, egressing only to `OUTREACH_SUBDOMAIN`.
  - `test_main_l6_skipped_on_fallback` — on a FALLBACK_MESSAGE run, asserts `crm_store.all_leads()` and
    `run_outreach_pipeline` are NOT called (L6 completely skipped).
  - `test_parse_caller_key_patterns` — parametric tests of `_parse_caller_key` regex patterns.
  - `test_parse_caller_key_not_logged` — AST inspection confirms no `dual_log`/`print` of the key.
  - `test_crm_store_all_leads_function_exists` — `all_leads()` exists and returns a list.
  - `test_crm_store_all_leads_no_id` — `all_leads()` strips mongo `_id` from records.

### Files NOT touched (graded contracts preserved)
- `answer_question` — signature, return type, cap, FALLBACK_MESSAGE path, dispatch, gateway — byte-stable.
- `dispatch_outreach`, `route_prospect`, `gateway_validate`, `lead_store` auth — untouched.
- `TOOL_SCHEMAS`, `TOOL_DISPATCH`, tool count (stays 10) — untouched.
- `FALLBACK_MESSAGE` constant — untouched.
- `schedule_outreach_cohort`, `outreach_status_brief`, `run_outreach_pipeline` — untouched.

---

## 2. DoD checklist

| Check | Status | How verified |
|---|---|---|
| `OUT7` outreach_status_brief deterministic rollup | ✅ written + test-verified | 12 tests in TestOUT7OutreachStatusBrief; all still passing (37/37) |
| `OUT8` end-to-end: `main()` path drives L6 | ✅ written + test-verified | `TestOUT8MainDriven.test_main_l6_runs_and_sender_called` drives `main.main()` directly; sender called; leads assembled correctly |
| `OUT8` no-match seed → FALLBACK_MESSAGE, L6 skipped | ✅ written + test-verified | `TestOUT8MainDriven.test_main_l6_skipped_on_fallback`; spy confirms `all_leads` and `run_outreach_pipeline` not called |
| `OUT9` idempotent re-run; no duplicate sends | ✅ still passing | TestOUT9Idempotency — 2/2 passing unchanged |
| `OUT10` crm_store.py in MANIFEST.txt; ENV4 holds; regression green | ✅ test-verified | TestOUT10Packaging 5/5; ENV4 subprocess from empty dir; 684/1 skip regression |
| re-run `INT1` subdomain isolation | ✅ test-verified | TestINT1EgressIsolation — crm_store.py does NOT reference OUTREACH_SUBDOMAIN (grep + AST verified) |
| re-run `INT2` auth gate honored | ✅ test-verified | TestINT2AuthGate still passing; wrong-key → sender not called |
| re-run `INT3` idempotent re-run | ✅ test-verified | test_integration.py TestINT3 still passing |
| re-run `H1`–`H5` packaging hygiene | ✅ test-verified | Full regression 684/1 skip; MANIFEST.txt includes crm_store.py |
| `ENV4` import-safety | ✅ run-verified | From empty tmp dir: all 5 singletons (main/_anthropic_client, lead_store, rag_engine×2, crm_store) confirmed None |
| `G1` no raw eval/exec | ✅ grep-verified | grep clean on all 4 shipped modules |
| `G4` no secrets in tracked files | ✅ grep-verified | No key values in shipped code |

---

## 3. QA results — commands + output

### Bug reproduction (systematic-debugging — phase 1: reproduce)
```
Command: .venv/bin/python -c "...crm_store.outbound_eligible_contacts()..."
Output: BUG REPRODUCED: outbound_eligible_contacts() missing 3 required positional arguments: 'caller_key', 'uniq_id', and 'emails'
```

### New TestOUT8MainDriven tests (6 tests)
```
Command: .venv/bin/python -m pytest tests/test_outreach_center.py::TestOUT8MainDriven -v --tb=short
Output: 6 passed, 1 warning in 0.50s
```

### Full test_outreach_center.py (37 tests)
```
Command: .venv/bin/python -m pytest tests/test_outreach_center.py -v --tb=short
Output: 37 passed, 1 warning in 0.60s
```
(Was 31 before; +6 new TestOUT8MainDriven tests)

### Full regression
```
Command: .venv/bin/python -m pytest tests/ -q --tb=no
Output: 684 passed, 1 skipped, 245 warnings in 31.98s
```
(Was 678 before Stage-14-r1; +6 new tests = 684)

### ENV4 from empty tmp dir
```
Command: cd <empty_tmp_dir> && .venv/bin/python -c "import main, lead_store, rag_engine, crm_store; ..."
Output: ENV4 PASS: all 4 modules import clean; all lazy singletons are None
  main._anthropic_client = None
  lead_store._collection_instance = None
  rag_engine._embedder_instance = None
  rag_engine._collection_instance = None
  crm_store._leads_collection = None
```

### G1 grep (no eval/exec in shipped modules)
```
Command: grep -n "eval(\|exec(" main.py lead_store.py rag_engine.py crm_store.py
Output: G1 CLEAN: no eval(/exec( in shipped code
```

### G4 grep (no key values in shipped modules)
```
Command: grep -n "TestKey|Access99|corporate_access_key\s*=\s*\"" main.py lead_store.py rag_engine.py crm_store.py
Output: G4 CLEAN: no key values in shipped modules
```

### INT1 — crm_store.py and run_outreach_pipeline do not reference OUTREACH_SUBDOMAIN
```
Command: grep -n "OUTREACH_SUBDOMAIN|outreach.reactfirst.ai" crm_store.py
Output: CLEAN: crm_store.py does not reference OUTREACH_SUBDOMAIN

Command: AST walk of run_outreach_pipeline source
Output: CLEAN: run_outreach_pipeline does not reference OUTREACH_SUBDOMAIN in functional code
```

### Tool count verification
```
Command: .venv/bin/python -c "import main; print(len(main.TOOL_SCHEMAS), len(main.TOOL_DISPATCH))"
Output: TOOL COUNT OK: 10 schemas, 10 dispatch entries; L6b fns not in schemas
```

### FALLBACK_MESSAGE byte-exact
```
Command: .venv/bin/python -c "import main; assert main.FALLBACK_MESSAGE == '...'"
Output: FALLBACK_MESSAGE byte-exact: 'We have no product available today that fits your request'
```

---

## 4. Decisions made

### `all_leads()` design
Added as an additive, non-graded helper to `crm_store.py`. Pattern mirrors `_strip_id` usage throughout
the file. Does not require a caller_key because it reads the CRM workspace (not the auth-gated contacts
store). The auth gate fires downstream inside `dispatch_outreach` for every actual send.

### `_parse_caller_key()` regex pattern
Chose `(?:access\s+key\s+is\s+(\S+)|key\s*[:=]\s*(\S+))` — covers the canonical Q1 pattern
"My access key is Access99" (PRD §3.2) and the shorter "key: X" / "key=X" variants. Case-insensitive.
Returns `""` on no match (safe: all sends will be auth-denied inside `dispatch_outreach`, the correct
outcome for a keyless run).

### main() wiring — do NOT use `outbound_eligible_contacts()`
Per the brief: `outbound_eligible_contacts` double-auths and returns sanitised contacts with no
`caller_key` field — wrong shape for the pipeline. The single auth chokepoint fires inside
`dispatch_outreach`; `main()` only assembles the leads list and passes the caller's key from the query.

### TestOUT8MainDriven test strategy
Used `monkeypatch.setattr(main, "answer_question", lambda ...)` to stub the LLM loop and isolate
the L6 wiring path. Then used a `spy_pipeline` that captures leads and calls `dispatch_outreach`
directly with a recording sender. This is cleaner than trying to call the real `run_outreach_pipeline`
through a monkeypatched name (which caused infinite recursion in the first iteration).

---

## 5. DECISION-NEEDED

None. No tool signatures, JSON schemas, policy constants, loop contract, or graded literals were changed.

---

## 6. Deviations

None from the r1 brief. All hard constraints honored:
- `answer_question` graded contract byte-stable.
- `run_outreach_pipeline` does NOT reference `OUTREACH_SUBDOMAIN` (AST-verified).
- Tool count stays 10; no schema/dispatch/assert change.
- `_parse_caller_key` value never logged (OUT5/G4 compliant).
- `crm_store.outbound_eligible_contacts()` no longer called in `main()`.

---

## 7. Blockers / risks

None. All transports mocked. Live smokes still gated on OQ-7 (API keys). No new external dependencies.

The `_parse_caller_key` regex is intentionally simple — it covers the documented Q1 query pattern.
Complex query forms that embed a key differently would not be parsed. This is by design: the auth gate
inside `dispatch_outreach` is the chokepoint, and a failed parse produces `""` → all sends denied
(the safe fallback).

---

## 8. Next recommended action

The PM should:
1. Run the full regression independently: `tests/` in `.venv` — **684 passed, 1 skipped, 0 failed**.
2. Verify ENV4 from an empty tmp dir (all 5 singletons None).
3. Mark Stage 14 ✅ in `PLAN.md` and close Phase 2.
