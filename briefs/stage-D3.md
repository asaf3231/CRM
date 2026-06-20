# Brief — Stage D3: Durability, indexes & restart proof
Read first: CLAUDE.md (§3.4 import-safety) → data_plan.md (Stage D3) → QA_checklist.md §12 (`DB6`,`DB7`,`DB8`) → NOTES.md (2026-06-20 Phase 4 entry), then this brief.

Goal: enforce key uniqueness with indexes, prove data survives a process restart, and give an idempotent
seed script — all **without perturbing the offline mongomock path** (the 765/1 suite must stay green).

## Key design rule — indexes are created on REAL Mongo ONLY
Index creation must be **gated to a real client** so it can never interfere with a mongomock test fixture
or the 765/1 baseline. Add a tiny helper to `db.py` and gate on it.

## Scope (do ONLY this stage)

### 1. `db.py` — add a real-client predicate (additive)
- Add `def using_real_mongo() -> bool: return bool(os.environ.get("MONGO_URI"))`. Read env inside the
  function (consistent with D1). Do NOT change `get_mongo_client()` / `get_database()`.

### 2. `lead_store.py` — create indexes (real-Mongo-gated) in `get_lead_data_collection()`
- Inside the `if _collection_instance is None:` block, AFTER obtaining `collection = db.get_database()["contacts"]`
  and BEFORE the seed-if-empty block, add:
  ```python
  if db.using_real_mongo():
      try:
          collection.create_index("email", unique=True)
          collection.create_index("target_brand_id")   # non-unique lookup
      except Exception:
          pass  # index creation is a real-Mongo safety net; never crash the getter
  ```
  (`contacts.json` has 6 unique emails — verified — so the unique index is safe to build before seeding.)
- Touch nothing else in this file; the Policy-4 gate functions stay byte-identical.

### 3. `crm_store.py` — create the unique index (real-Mongo-gated) in `get_crm_collection()`
- Inside the `if _leads_collection is None:` block, after the assignment, add:
  ```python
  if db.using_real_mongo():
      try:
          _leads_collection.create_index("uniq_id", unique=True)
      except Exception:
          pass
  ```
- Touch nothing else in this file.

### 4. `scripts/seed_db.py` — NEW, idempotent seed (DB8)
- A runnable script (`python scripts/seed_db.py`) that loads `contacts.json` into the configured DB and
  ensures the CRM leads collection/indexes exist. **Reuse the existing seed-if-empty logic** rather than
  duplicating it: import `lead_store` + `crm_store`, call `lead_store.get_lead_data_collection()` (which
  seeds contacts.json only if empty) and `crm_store.get_crm_collection()` (builds the leads collection +
  index), then print a short summary (e.g. `contacts: N, leads: M, MONGO_URI set? yes/no`).
- If `MONGO_URI` is unset, print a clear warning that it is seeding the ephemeral in-memory mongomock
  (no persistence) and exit 0 — do not crash.
- Guard the whole thing in a `def main(): ...` + `if __name__ == "__main__": main()` block; import-safe
  (no work at import).

### 5. `tests/test_persistence.py` — APPEND the live, skipif-gated checks (DB6, DB7)
Add (keep the existing DB5 idempotency test):
- A module-level `REQUIRES_MONGO = pytest.mark.skipif(not os.environ.get("MONGO_URI"), reason="requires a
  real MongoDB (MONGO_URI)")` — same gating pattern as the live `S10` test, so the offline suite skips these.
- **DB7 restart durability:** upsert a lead with a throwaway `uniq_id` (e.g. `"db7-restart-probe"`); set
  `db._client = None` and `crm_store._leads_collection = None` (simulate a full restart); reconnect via
  `crm_store.get_lead(test_id)`; assert it is still present; then clean up
  (`crm_store.get_crm_collection().delete_one({"uniq_id": test_id})`).
- **DB6 indexes + uniqueness:** with a real client, assert `crm_store.get_crm_collection().index_information()`
  contains a unique index on `uniq_id` and `lead_store.get_lead_data_collection().index_information()` a
  unique index on `email`; then assert inserting a DUPLICATE `uniq_id` via `insert_one` twice raises
  `pymongo.errors.DuplicateKeyError` (use a throwaway id; clean up after).

## QA checks to PASS
- `DB6` — indexes present + uniqueness enforced under real Mongo (the skipif test passes when `MONGO_URI`
  is set); offline suite unaffected.
- `DB7` — cross-restart round-trip persists (skipif test passes when `MONGO_URI` is set).
- `DB8` — `scripts/seed_db.py` is idempotent (PM runs it twice against real Mongo → no duplicate contacts).

## Constraints (from CLAUDE.md)
- **Import-safety (ENV4)** holds: `import db, lead_store, crm_store` and `import scripts.seed_db` (or
  running the file) do nothing at import; singletons stay `None`; no index creation at import.
- **The offline mongomock path must stay byte-identical** — index creation is gated behind
  `db.using_real_mongo()`, so with `MONGO_URI` unset the getters behave exactly as in D2. The full suite
  with `MONGO_URI` unset must stay **765 passed, 1 skipped** (the new DB6/DB7 tests SKIP offline).
- Auth gate + CRM shape unchanged. No tool/schema/constant/loop/graded-literal changes — surface as
  DECISION-NEEDED.
- Note: the full suite is an OFFLINE (mongomock) contract; the live DB6/DB7 tests are run in isolation by
  the PM with `MONGO_URI` set. Do not make any existing test require a real Mongo.

## Inputs / files you may touch
`db.py`, `lead_store.py`, `crm_store.py`, `scripts/seed_db.py` (new), `tests/test_persistence.py`.

Do NOT: advance to D4 (no MANIFEST/CLAUDE/NOTES doc edits); change the auth gate, CRM shape, or any graded
contract — surface as DECISION-NEEDED.

Deliver: write `handbacks/stage-D3.md` in the standard handback format and return it as your final message.
Your sandbox likely cannot run Docker/Mongo — run the OFFLINE suite (`MONGO_URI` unset, the live tests
skip) and report it; the PM will run the live DB6/DB7/DB8 checks against the Docker Mongo.
