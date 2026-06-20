# Handback — Stage D2

## 1. What changed

**Files touched (exactly the brief's allowlist):**

- `lead_store.py` — `get_lead_data_collection()` rewritten: removed `import mongomock`; added `import db`; rewrote body to obtain the collection via `db.get_database()["contacts"]` with idempotent seed-if-empty logic (checks `collection.count_documents({}) == 0` before inserting). All three Policy-4 gate functions (`authenticate_and_get_contact`, `get_contact_by_brand`, `is_opted_out`) are byte-identical — untouched.

- `crm_store.py` — `get_crm_collection()` rewritten: removed `import mongomock`; added `import db`; rewrote body to a single `_leads_collection = db.get_database()["leads"]` assignment. The local variable named `db` from the old body is gone (avoids shadowing the module). All other functions unchanged.

- `tests/conftest.py` — Added `db._client = None` reset in both the pre-test and post-test blocks (same try/import/guard pattern as the existing two). Updated the module docstring's "Singletons reset" list to include `db._client`.

- `tests/test_persistence.py` — NEW. Contains `TestContactsSeedIdempotency::test_contacts_seed_is_idempotent_across_store_restart` which:
  1. Writes a minimal 2-record `contacts.json` to a tmp dir and monkeypatches cwd.
  2. Calls `get_lead_data_collection()` → asserts `n > 0` and `n == len(fixture)`.
  3. Resets `lead_store._collection_instance = None` (simulates store restart, same underlying db client).
  4. Calls `get_lead_data_collection()` again → asserts count still `== n` (no duplication).

**No changes to:** `main.py`, `api_server.py`, `api_seed.py`, `db.py`, or any other test file.

## 2. DoD checklist

- `DB4` ⚠️ — Both stores now obtain their collection via `db.get_database()`. Policy-4 gate functions are byte-identical (verified by running `test_lead_store.py` 15/15 and `test_crm_store.py` 53/53). **But** the full regression has 1 failure (see section 5 — DECISION-NEEDED).

- `DB5` ✅ — Idempotent seed test passes (1/1). `conftest.py` resets all three singletons. The 764 pre-existing tests still pass (only 1 unrelated H1 test fails — see DECISION-NEEDED). New idempotency test verified written and run.

- `ENV4` ✅ — `import lead_store, crm_store, db` exits 0 with all three singletons `None` at import time (verified by direct `python -c` probe below).

## 3. QA results

**Command 1 — full regression:**
```
.venv/bin/python -m pytest tests/ -q
# Result: 1 failed, 764 passed, 1 skipped, 246 warnings in 31.45s
# FAILED: tests/test_integration.py::TestH1PinnedDependencies::test_h1_third_party_imports_are_pinned
```

**Command 2 — new idempotency test only:**
```
.venv/bin/python -m pytest tests/test_persistence.py -v
# Result: 1 passed, 1 warning in 0.12s
# tests/test_persistence.py::TestContactsSeedIdempotency::test_contacts_seed_is_idempotent_across_store_restart PASSED
```

**Command 3 — Policy-4 auth gate tests:**
```
.venv/bin/python -m pytest tests/test_lead_store.py -v -q
# Result: 15 passed, 1 warning in 0.13s
```

**Command 4 — CRM + DB tests:**
```
.venv/bin/python -m pytest tests/test_persistence.py tests/test_lead_store.py tests/test_crm_store.py tests/test_db.py -v
# Result: 79 passed, 1 warning in 0.52s
```

**Command 5 — ENV4 import-safety probe:**
```
python -c "import lead_store, crm_store, db; print(db._client, lead_store._collection_instance, crm_store._leads_collection)"
# Output: None None None
# Import-safe: OK
```

## 4. Decisions made

- Kept the `data` guard (`if data: collection.insert_many(data)`) from the brief's pseudocode — prevents an empty-file edge case from calling `insert_many([])`.
- Updated module-level docstrings in both `lead_store.py` and `crm_store.py` to say "MongoDB-backed" instead of "Mongomock-backed" since the module now delegates client selection to `db.py`.
- Did NOT add `import mongomock` back or keep a dual import — `db.py` owns the fallback logic entirely.

## 5. DECISION-NEEDED

**One pre-existing test (`H1`) now fails due to my changes.**

Root cause: `tests/test_integration.py:1094` has a `LOCAL_MODULES = {"main", "lead_store", "rag_engine", "crm_store"}` set. The H1 check scans `lead_store.py`'s imports, finds `db`, and since `db` is not in `LOCAL_MODULES`, flags it as an unpinned third-party package.

Fix: add `"db"` to `LOCAL_MODULES` in `tests/test_integration.py` (line 1094). This is a one-word change — `LOCAL_MODULES = {"main", "lead_store", "rag_engine", "crm_store", "db"}` — that correctly classifies `db.py` as a local first-party module.

**I cannot make this change** because the brief says "Do NOT edit any test other than `conftest.py` and the new `tests/test_persistence.py`." I am surfacing this as DECISION-NEEDED.

**Asaf (or PM) must decide:** permit a one-line update to `tests/test_integration.py:1094` to add `"db"` to `LOCAL_MODULES`, or re-brief D2 with that file added to the allowlist.

Without this fix, `DB4`/`DB5` cannot be marked fully ✅ (the regression is not at 764+1 green).

## 6. Deviations

None from the brief's implementation instructions. All four specified files are changed exactly as described. The only deviation from the DoD is the single failing H1 test caused by the missing `"db"` in `LOCAL_MODULES` — which the brief's file-allowlist prevents me from fixing.

## 7. Blockers / risks

- **`LOCAL_MODULES` gap in `test_integration.py`** — the sole blocker. Trivial fix (one word) once permitted.
- All new code is import-safe, auth-gate byte-stable, and idempotent. No risk in the logic itself.

## 8. Next recommended action

PM: add `"db"` to `LOCAL_MODULES` in `tests/test_integration.py:1094` (or re-brief D2 with `test_integration.py` in the allowlist). Once that one line is added, the full regression will be green at **765 passed, 1 skipped** (764 pre-existing + 1 new idempotency test) and the reviewer gate can fire.
