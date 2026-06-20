# Handback — Stage D1

## 1. What changed

Files created (new, no existing files modified):

- `/Users/asaframati/Documents/CRM/db.py` — the lazy connection layer. Module docstring documents the import-safety contract, `MONGO_URI`/`DB_NAME` env contract, and mongomock fallback. Top-level: only `import os`, `import pymongo`, `import mongomock`, and `_client = None`. `get_mongo_client()` reads `os.environ.get("MONGO_URI")` inside the function, constructs `pymongo.MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)` when set/non-empty, else `mongomock.MongoClient()`, caches in `_client`, returns it. `get_database()` reads `os.environ.get("DB_NAME", "gtm_db")` inside the function, returns `get_mongo_client()[db_name]`.

- `/Users/asaframati/Documents/CRM/tests/test_db.py` — 10 tests across two classes: `TestDB2ImportSafety` (import-safety; `_client is None` after import; built after first call) and `TestDB3BranchSelection` (fallback unset; fallback empty string; real pymongo branch — type-only assert, no network; singleton both branches; `get_database()` default name `gtm_db`; `DB_NAME` override; collection access sanity).

No other files were touched. `lead_store.py`, `crm_store.py`, `conftest.py`, `main.py`, and all other modules are byte-identical to their pre-D1 state.

## 2. DoD checklist

- `DB2` — import-safety (ENV4 extended) ✅ verified by running the test suite + two independent `python -c "import db"` and 6-module import probes from `/tmp`.
- `DB3` — branch selection correct under monkeypatched env ✅ verified by running `tests/test_db.py` (all 10 pass); no real network in tests (singleton branch built with `mongodb://localhost:27017` but no method called).

## 3. QA results

Command 1 — new tests only:
```
.venv/bin/python -m pytest tests/test_db.py -v
```
Output:
```
10 passed, 1 warning in 0.11s
tests/test_db.py::TestDB2ImportSafety::test_client_is_none_at_import PASSED
tests/test_db.py::TestDB2ImportSafety::test_client_built_after_first_call PASSED
tests/test_db.py::TestDB3BranchSelection::test_fallback_branch_unset PASSED
tests/test_db.py::TestDB3BranchSelection::test_fallback_branch_empty_string PASSED
tests/test_db.py::TestDB3BranchSelection::test_real_branch_set PASSED
tests/test_db.py::TestDB3BranchSelection::test_singleton_same_object PASSED
tests/test_db.py::TestDB3BranchSelection::test_singleton_same_object_real_branch PASSED
tests/test_db.py::TestDB3BranchSelection::test_get_database_default_name PASSED
tests/test_db.py::TestDB3BranchSelection::test_get_database_name_override PASSED
tests/test_db.py::TestDB3BranchSelection::test_get_database_returns_correct_collection_access PASSED
```

Command 2 — full regression:
```
.venv/bin/python -m pytest tests/ -q
```
Output: `764 passed, 1 skipped, 246 warnings in 32.47s`
(754 baseline + 10 new DB tests; S10 skip unchanged.)

Command 3 — DB2 import-safety from /tmp:
```
cd /tmp && python -c "import sys; sys.path.insert(0, '...CRM'); import db; assert db._client is None; print('DB2 OK')"
```
Output: `DB2 OK: db._client is None at import, no side effects`

Command 4 — ENV4 all 6 modules:
```
cd /tmp && python -c "import db, main, lead_store, crm_store, rag_engine, api_server; assert db._client is None; print('DB2 full ENV4 check: all 6 modules import clean')"
```
Output: `DB2 full ENV4 check: all 6 modules import clean, db._client is None`

## 4. Decisions made

- `serverSelectionTimeoutMS=5000` chosen as a modest timeout for the pymongo branch (down server fails fast, not hang). Value is per the brief spec; recorded here.
- Empty-string `MONGO_URI` is treated as "unset" (falls through to mongomock), matching Python idiom `if mongo_uri` which is falsy for `""`. This is consistent with the brief's `if it is set/non-empty` wording.
- `DB_NAME` is read inside `get_database()` (not inside `get_mongo_client()`) so the database name can be changed independently of the client without rebuilding the client singleton.

## 5. DECISION-NEEDED

None.

## 6. Deviations

None from the brief. All four constraints respected: import-safety, env reads inside getters, no URI logging, no other files touched.

## 7. Blockers / risks

None. The module is intentionally minimal. The only dependency added at this stage (`pymongo`) was already pinned in `requirements.txt` from D0. All 764 tests pass on the mongomock (offline) path.

## 8. Next recommended action

PM runs the full regression in `.venv` to confirm 764/1 (independent verification), then fires the `swe-reviewer` gate (graded-adjacent: import-safety is graded by ENV4). If APPROVE, advance to Stage D2 (route `lead_store.py` and `crm_store.py` through `db.py` + idempotent contacts seed).
