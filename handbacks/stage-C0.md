# Handback — Stage C0

## 1. What changed

**Files touched (2):**

- `/Users/asaframati/Documents/CRM/Backend/api_seed.py` — `seed_demo()` rewritten with the seed-if-empty guard and `SEED_DEMO` env opt-out. The function body now:
  1. Reads `os.environ.get("SEED_DEMO", "1")` (import inside function — import-safe); if the value is in `{"0", "false", "no", "off"}` (case-insensitive), returns immediately.
  2. Imports `crm_store` lazily (unchanged position — still inside function).
  3. Calls `crm_store.get_crm_collection().count_documents({})` and returns if > 0.
  4. Falls through to the 16-record upsert loop only when the workspace is empty and not opted out.
  The `_SEED_RECORDS`, `SEED_STATS`, and `SEED_ICP` constants are unchanged.

- `/Users/asaframati/Documents/CRM/Backend/tests/test_api.py` — new class `TestSeedDemoGuard` appended (3 tests; no existing test modified):
  - `test_conn1_empty_workspace_seeds_16_records` — CONN1
  - `test_conn0_nonempty_workspace_is_not_clobbered` — CONN0 (non-empty guard)
  - `test_conn0_seed_demo_env_opt_out` — CONN0 (SEED_DEMO=0)

## 2. DoD checklist

| Check | Status | How verified |
|---|---|---|
| `CONN1` — empty workspace seeds 16 | ✅ | `TestSeedDemoGuard::test_conn1_empty_workspace_seeds_16_records` PASSED |
| `CONN0` — non-empty not clobbered | ✅ | `TestSeedDemoGuard::test_conn0_nonempty_workspace_is_not_clobbered` PASSED |
| `CONN0` — `SEED_DEMO=0` opt-out | ✅ | `TestSeedDemoGuard::test_conn0_seed_demo_env_opt_out` PASSED |
| `ENV4` / `INTG1` import-safety | ✅ | Manual probe: `import api_seed` from `/tmp` with key stripped, `crm_store._leads_collection` stays `None` after import |
| Full regression — no regressions | ✅ | 768 passed, 5 skipped, 0 failed (previous baseline 765 + 3 new = 768) |
| No graded contract changed | ✅ | `_SEED_RECORDS`, `SEED_STATS`, `SEED_ICP`, `api_server.py`, `main.py`, stores, `db.py` untouched |
| No existing test modified | ✅ | Only appended a new class; all prior test classes byte-stable |

## 3. QA results

**Command 1 — target tests only:**
```
cd /Users/asaframati/Documents/CRM/Backend
/Users/asaframati/Documents/CRM/.venv/bin/python -m pytest tests/test_api.py::TestSeedDemoGuard -v
```
Output:
```
tests/test_api.py::TestSeedDemoGuard::test_conn1_empty_workspace_seeds_16_records PASSED
tests/test_api.py::TestSeedDemoGuard::test_conn0_nonempty_workspace_is_not_clobbered PASSED
tests/test_api.py::TestSeedDemoGuard::test_conn0_seed_demo_env_opt_out PASSED
3 passed, 1 warning in 0.13s
```

**Command 2 — full `test_api.py`:**
```
/Users/asaframati/Documents/CRM/.venv/bin/python -m pytest tests/test_api.py -q
```
Output:
```
73 passed, 2 warnings in 1.67s
```
(70 pre-existing + 3 new = 73)

**Command 3 — full regression suite:**
```
/Users/asaframati/Documents/CRM/.venv/bin/python -m pytest tests/ --tb=short -q
```
Output:
```
768 passed, 5 skipped, 246 warnings in 32.34s
```

**Command 4 — import-safety probe:**
```
python -c "import api_seed; assert crm_store._leads_collection is None"
```
Output: `PASS: import api_seed has zero side effects; crm_store._leads_collection remains None`

## 4. Decisions made

- `import os` was placed **inside** `seed_demo()` rather than at the module top-level. The brief permits either; placing it inside keeps the function fully self-contained and visually consistent with the existing `import crm_store` pattern.
- The `SEED_DEMO` check is performed **before** importing `crm_store`, so even the lazy import is skipped on opt-out. This is marginally more efficient and keeps the fast-path truly zero-work.

## 5. DECISION-NEEDED

None.

## 6. Deviations

None. Implementation matches the brief exactly.

## 7. Blockers / risks

None. The PM noted the live-restart proof (real Mongo + API restart → records unchanged) is a PM-only check that requires a Docker Mongo environment; that is deferred to the PM per the brief.

## 8. Next recommended action

PM runs the live-restart proof against a real Docker Mongo instance (restart the API with `SEED_DEMO` default, verify the 16 demo records were not re-inserted over any real data), then marks stage C0 ✅ in `PLAN.md`.
