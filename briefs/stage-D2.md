# Brief — Stage D2: Route both stores through `db.py` + idempotent contacts seed
Read first: CLAUDE.md (§3.4 import-safety, §5 Policy 4 auth gate, §4.1 contacts) → data_plan.md (Stage D2) → QA_checklist.md §12 (`DB4`,`DB5`) → NOTES.md (2026-06-20 Phase 4 entry), then this brief.

Goal: make the two stores **persistent** by obtaining their collections from `db.py`, **without changing
any public behavior**. The mongomock offline path must behave exactly as today (suite stays green); the
Policy-4 auth gate and the CRM record shape must be **byte-stable**.

## Scope (do ONLY this stage)

### 1. `lead_store.py` — `get_lead_data_collection()` only
- Add `import db` at the top (top-level — `db.py` is import-safe). **Remove `import mongomock`** *only
  after grep-confirming it is no longer referenced anywhere else in the file.*
- Rewrite the body of `get_lead_data_collection()` so the collection comes from `db.py` and the
  `contacts.json` load is **idempotent (seed-if-empty)**:
  ```python
  global _collection_instance
  if _collection_instance is None:
      collection = db.get_database()["contacts"]
      # Idempotent seed: only load contacts.json when the collection is empty.
      # (Today's unconditional insert_many would DUPLICATE against a persistent Mongo on every restart.)
      if collection.count_documents({}) == 0:
          contacts_path = os.path.join(os.getcwd(), "contacts.json")
          with open(contacts_path, "r", encoding="utf-8") as f:
              data = json.load(f)
          if data:
              collection.insert_many(data)
      _collection_instance = collection
  return _collection_instance
  ```
- **Do NOT touch** `authenticate_and_get_contact`, `get_contact_by_brand`, or `is_opted_out` — they must
  be byte-identical (the Policy-4 auth gate is the single graded chokepoint).

### 2. `crm_store.py` — `get_crm_collection()` only
- Add `import db` at the top. **Remove `import mongomock`** *only after grep-confirming it is unused.*
- Rewrite the body of `get_crm_collection()` to:
  ```python
  global _leads_collection
  if _leads_collection is None:
      _leads_collection = db.get_database()["leads"]
  return _leads_collection
  ```
  **Do NOT introduce a local variable named `db`** (it would shadow the module) — the old body used a
  local `db`; the new body must not.
- **Do NOT touch** any other function (`upsert_lead`, `get_lead`, `update_lead_stage`, `attach_contact`,
  `outbound_eligible_contacts`, `compute_win_prob`, `all_leads`, the helpers) — the CRM record shape and
  all behavior stay byte-stable.

### 3. `tests/conftest.py` — reset the new singleton
- Add a `db._client = None` reset (same `try/import/guard` pattern) in **both** the pre-test and the
  post-test blocks, alongside the existing two. Update the module docstring's "Singletons reset" list to
  include `db._client`. Resetting all three forces a fresh client + fresh collections per test (isolation).

### 4. `tests/test_persistence.py` — NEW, the DB5 idempotency test
- Create this file with a focused offline test (mongomock path, `MONGO_URI` unset) proving the seed is
  idempotent across a store "restart" that keeps the underlying client:
  ```python
  def test_contacts_seed_is_idempotent_across_store_restart():
      import db, lead_store
      col1 = lead_store.get_lead_data_collection()      # first call seeds contacts.json
      n = col1.count_documents({})
      assert n > 0
      # Simulate restarting the store singleton but NOT the underlying client (persistence):
      lead_store._collection_instance = None
      col2 = lead_store.get_lead_data_collection()      # re-enters; collection already non-empty
      assert col2.count_documents({}) == n              # NO duplicate seeding
  ```
  (The autouse conftest fixture resets all three singletons around the test, so it starts clean.)

## QA checks to PASS (PM re-runs in `.venv`)
- `DB4` — both stores obtain their collection via `db.get_database()`; the Policy-4 auth gate is unchanged
  (single chokepoint; denial semantics byte-stable); the CRM record shape is unchanged.
- `DB5` — contacts seed is idempotent (the new test passes); `conftest.py` resets `db._client`; the full
  pre-existing regression stays green on the mongomock path (no test regresses; existing **764 passed,
  1 skipped** holds, plus your new idempotency test).

## Constraints (from CLAUDE.md)
- **Import-safety (ENV4)** still holds: `import lead_store, crm_store, db` side-effect-free; the singletons
  (`_collection_instance`, `_leads_collection`, `db._client`) are all `None` until first use.
- **Policy 4 auth gate is graded** — its functions must be byte-identical; the collection is still reached
  ONLY through the gate. Changing only *where the collection object comes from* is allowed; changing the
  gate logic is NOT.
- No change to any tool signature / JSON schema / policy constant / the loop contract / a graded literal /
  the CRM record shape. Surface any such need as DECISION-NEEDED.
- Do NOT edit `main.py`, `api_server.py`, `api_seed.py`, `db.py`, or any test other than `conftest.py` and
  the new `tests/test_persistence.py`.

## Inputs / files you may touch
`lead_store.py`, `crm_store.py`, `tests/conftest.py`, `tests/test_persistence.py` (new).

Do NOT: advance to D3 (no indexes, no `scripts/seed_db.py`, no live-Mongo test); change the auth gate or
CRM shape — surface as DECISION-NEEDED.

Deliver: write `handbacks/stage-D2.md` in the standard handback format and return it as your final message.
If your sandbox can run pytest, report results; otherwise say so — the PM runs the full suite.
