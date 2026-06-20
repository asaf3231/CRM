# Brief — Stage C0: stop the demo seed from clobbering persisted data
Read first: CLAUDE.md (§3.4 import-safety) → backend_connection_plan.md (Stage C0) → QA_checklist.md §13 (`CONN0`,`CONN1`) → NOTES.md (2026-06-20 Phase 4 entry), then this brief.

Goal: `api_seed.seed_demo()` must NOT overwrite persisted leads on every API startup. Make it
**seed-if-empty** (skip when the leads workspace already has records) with a `SEED_DEMO` env opt-out, while
keeping the offline mongomock dev experience identical (the FE still gets the 16 demo leads).

## Background (current behavior)
`api_server.py`'s ASGI `lifespan` calls `api_seed.seed_demo()`, which **unconditionally upserts** the 16
`_SEED_RECORDS` into `crm_store` on every boot. With a persistent MongoDB (Phase 4), this re-runs each
restart and overwrites those 16 `uniq_id`s — clobbering any real edits. Offline (mongomock) the workspace is
always empty at boot, so seeding there is harmless and desired (FE dev data).

## Scope (do ONLY this stage)

### 1. `api_seed.py` — guard `seed_demo()`
Rewrite `seed_demo()` so it:
- reads a `SEED_DEMO` env opt-out: if `os.environ.get("SEED_DEMO", "1")` is one of `{"0","false","no","off"}`
  (case-insensitive), **return immediately** (no seeding);
- otherwise obtains `crm_store.get_crm_collection()` and, **if the leads workspace is non-empty**
  (`count_documents({}) > 0`), **returns without seeding** (seed-if-empty — never clobber persisted data);
- only when the workspace is empty (and not opted out) does it upsert the 16 `_SEED_RECORDS` as today.
Keep `crm_store` imported lazily inside the function (import-safety / INTG1). `import os` may go at the top
(it is import-safe) or inside the function. Update the docstring to describe the seed-if-empty + `SEED_DEMO`
behavior. **Do not change `_SEED_RECORDS`, `SEED_STATS`, or `SEED_ICP`.**

### 2. `tests/test_api.py` — APPEND a new test class (do NOT modify existing tests)
Add offline (mongomock) tests that prove the guard. The autouse `conftest` fixture resets the singletons,
so each test starts with an empty workspace.
- **CONN1 — offline demo still seeds:** call `api_seed.seed_demo()` on a fresh (empty) workspace, assert
  `crm_store.get_crm_collection().count_documents({}) == 16` (the demo seeds as before).
- **CONN0 — seed-if-empty does not clobber:** pre-`upsert_lead` ONE record with a custom `uniq_id`
  (e.g. `"real-lead-001"`) AND pre-upsert one of the demo ids (e.g. `"seed-lead-001"`) with a SENTINEL field
  (e.g. `domain="DO-NOT-OVERWRITE.example"`); then call `seed_demo()`; assert the workspace was NOT re-seeded
  — the count is unchanged (2) and the sentinel demo record still has `domain == "DO-NOT-OVERWRITE.example"`
  (i.e. the demo did not overwrite it).
- **CONN0 — `SEED_DEMO` opt-out:** with `SEED_DEMO=0` (monkeypatched), `seed_demo()` on an empty workspace
  leaves it empty (`count_documents({}) == 0`).

## QA checks to PASS (PM re-runs in `.venv` + live against Docker Mongo)
- `CONN0` — no clobber: a non-empty workspace is never overwritten by `seed_demo()`; `SEED_DEMO=0` disables
  it. (PM also live-verifies: seed real Mongo, restart the API, records unchanged.)
- `CONN1` — offline demo still seeds (16) on an empty mongomock workspace; the full offline suite stays green.

## Constraints (from CLAUDE.md)
- **Import-safety (ENV4 / INTG1):** `import api_seed` and `import api_server` stay side-effect-free; the seed
  still fires only inside the ASGI `lifespan`, never at import. `crm_store` stays a lazy import inside `seed_demo()`.
- This touches only the Phase-3 additive API layer — **no graded engine contract** (tool count, auth gate,
  `answer_question`, `FALLBACK_MESSAGE`, CRM record shape) may change. Surface any such need as DECISION-NEEDED.
- Do NOT modify `api_server.py` (its lifespan call is unchanged — the guard lives in `seed_demo()`), `main.py`,
  the stores, `db.py`, or any existing test.

## Inputs / files you may touch
`api_seed.py`, `tests/test_api.py` (append a new test class only).

Do NOT: advance to C1+ (no `/api/health` change, no new endpoints); change any graded contract — surface as
DECISION-NEEDED.

Deliver: write `handbacks/stage-C0.md` in the standard handback format and return it as your final message.
If your sandbox can run pytest, report it; otherwise say so — the PM runs the full suite + the live restart proof.
