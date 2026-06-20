# Handback — Stage D3

## 1. What changed

Files touched (exactly those listed in the brief scope):

- **`db.py`** (modified): added `using_real_mongo() -> bool` predicate after `get_database()`. Reads `os.environ.get("MONGO_URI")` inside the function — consistent with the D1 env-read-inside-getter pattern. Zero side effects at import; singletons stay None.

- **`lead_store.py`** (modified): inside the `if _collection_instance is None:` block, AFTER obtaining `collection = db.get_database()["contacts"]` and BEFORE the seed-if-empty guard — added a `db.using_real_mongo()`-gated `try/except` that calls `collection.create_index("email", unique=True)` and `collection.create_index("target_brand_id")`. The `except Exception: pass` ensures index creation never crashes the getter. Mongomock path is byte-identical to pre-D3.

- **`crm_store.py`** (modified): inside the `if _leads_collection is None:` block, after the assignment — added a `db.using_real_mongo()`-gated `try/except` that calls `_leads_collection.create_index("uniq_id", unique=True)`. Same `except Exception: pass` guard. Mongomock path byte-identical to pre-D3.

- **`scripts/seed_db.py`** (new): idempotent seed script. Guards all work in `def main()`. Resolves the project root via `__file__`, changes cwd, imports `lead_store` and `crm_store` after setup, calls their getters (which handles seed-if-empty + index creation). Prints `contacts: N, leads: M, MONGO_URI set? yes/no`. Prints a clear WARNING when MONGO_URI is unset. Does no work at import time.

- **`tests/test_persistence.py`** (modified): appended module-level `REQUIRES_MONGO = pytest.mark.skipif(not os.environ.get("MONGO_URI"), ...)` gate (same pattern as S10). Added:
  - `TestIndexesLiveMongo` (DB6): 3 tests — unique index on `leads.uniq_id`, unique index on `contacts.email`, `DuplicateKeyError` on duplicate `uniq_id` insert. All marked `@REQUIRES_MONGO`.
  - `TestRestartDurabilityLiveMongo` (DB7): 1 test — upsert lead, reset `db._client = None` and `crm_store._leads_collection = None`, reconnect via `crm_store.get_lead(test_id)`, assert still present, cleanup. Marked `@REQUIRES_MONGO`.

## 2. DoD checklist

| Check | Status | How verified |
|---|---|---|
| `DB6` indexes + uniqueness | ⚠️ SKIPIF offline — PM to run live | `TestIndexesLiveMongo` 3 tests skip when `MONGO_URI` unset. Gating pattern verified. |
| `DB7` restart durability | ⚠️ SKIPIF offline — PM to run live | `TestRestartDurabilityLiveMongo` 1 test skips when `MONGO_URI` unset. |
| `DB8` idempotent seed script | ✅ (offline smoke) | `python scripts/seed_db.py` twice → `contacts: 6, leads: 0, MONGO_URI set? no` both times (fresh in-memory each run — idempotency provable live by PM). |
| ENV4 import-safety | ✅ run-verified | From an empty `/tmp` dir: `import db, lead_store, crm_store, main, rag_engine, api_server` — all singletons `None`, zero side effects. |
| Offline suite baseline | ✅ run-verified | `765 passed, 5 skipped` (1 original S10 + 4 new live-gated DB6/DB7). Passed count unchanged at 765. |

## 3. QA results

**Offline suite (MONGO_URI unset):**
```
Command: source .venv/bin/activate && python -m pytest tests/ --tb=short -q
Result: 765 passed, 5 skipped, 246 warnings in 32.30s
```

**Persistence tests only (MONGO_URI unset):**
```
Command: source .venv/bin/activate && python -m pytest tests/test_persistence.py --tb=short -v
Result: 1 passed, 4 skipped — PASSED: test_contacts_seed_is_idempotent_across_store_restart; SKIPPED: 3x DB6 + 1x DB7
```

**ENV4 import-safety probe:**
```
Command: python -c "import db, lead_store, crm_store, main, rag_engine, api_server" (from empty /tmp dir)
Result: all singletons None — exit 0
```

**seed_db.py offline run (twice):**
```
Command: python scripts/seed_db.py (twice)
Result: [seed_db] WARNING: MONGO_URI is not set. Seeding into the ephemeral in-memory mongomock store...
        [seed_db] contacts: 6, leads: 0, MONGO_URI set? no
```

**using_real_mongo() logic:**
```
MONGO_URI unset → False (verified)
MONGO_URI set → True (verified)
_client stayed None after using_real_mongo() call → no side effects (verified)
```

**Live DB6/DB7/DB8 checks:** deferred to PM with Docker Mongo (`MONGO_URI=mongodb://localhost:27017`). See brief — sandbox cannot run Docker.

## 4. Decisions made

- **Where to place the index call in `lead_store.py`**: AFTER obtaining the collection reference and BEFORE the seed-if-empty block. This matches the brief's exact placement ("AFTER obtaining collection = ... and BEFORE the seed-if-empty block"). The 6 contacts in `contacts.json` have unique emails (verified per the brief), so the unique index is safe to create before seeding.

- **`except Exception: pass` scope**: catches all exceptions from `create_index`. This is the exact pattern the brief specifies ("index creation is a real-Mongo safety net; never crash the getter"). The narrow try/except wraps only the `create_index` calls, not the entire getter body.

- **`using_real_mongo()` reads env on every call**: reads `os.environ.get("MONGO_URI")` directly each time — not cached. Consistent with D1 design (env read inside getter so monkeypatching works in tests). No performance concern since it's called at most once per getter invocation.

- **New skip count is 5 not 1**: the brief's "765 passed / 1 skipped" referred to the pre-D3 baseline. Adding 4 new `@REQUIRES_MONGO`-gated tests (3 DB6 + 1 DB7) changes the skip count to 5. The passed count stays exactly 765. This is the correct behaviour — the brief's constraint "the new DB6/DB7 tests must SKIP" is satisfied.

- **`scripts/seed_db.py` imports stores after cwd/sys.path setup**: `import lead_store, crm_store` happen inside `main()` only, after the project root is in `sys.path` and cwd is set. This keeps the script import-safe per CLAUDE.md §3.4 and also allows it to be run from any directory.

## 5. DECISION-NEEDED

None. All design choices were specified by the brief or follow directly from established CLAUDE.md patterns.

## 6. Deviations

- **Offline skip count is 5 not 1**: the brief referenced the pre-D3 baseline count of 1 skip. The 4 new `REQUIRES_MONGO`-gated tests add 4 more skips. This is the intended behaviour — the brief explicitly says the new DB6/DB7 tests must SKIP offline. No deviation from intent.

## 7. Blockers / risks

- **DB6/DB7 live verification requires Docker+Mongo**: this sandbox cannot run Docker, so DB6 (index existence + DuplicateKeyError) and DB7 (restart durability) can only be PM-verified with `MONGO_URI` set. The tests are correctly written and structurally sound (verified by reading the mongomock path and the pymongo API contract).
- **DB8 live idempotency**: `seed_db.py` ran correctly in offline mode. Live test (same script, `MONGO_URI` set, run twice) must be confirmed by the PM — the seed-if-empty guard in `lead_store.get_lead_data_collection()` makes this idempotent by construction.

## 8. Next recommended action

PM runs the live DB6/DB7/DB8 checks with Docker Mongo:
```bash
docker compose up -d mongo
MONGO_URI=mongodb://localhost:27017 python scripts/seed_db.py
MONGO_URI=mongodb://localhost:27017 python scripts/seed_db.py   # second run — must not duplicate
MONGO_URI=mongodb://localhost:27017 python -m pytest tests/test_persistence.py -v
```
Then advance to Stage D4 (packaging + docs).
