# data_plan.md — Durable Persistence Layer (Phase 4)

Project: **Autonomous Agentic GTM Engine & Value-Hook Pipeline** (ReactFirst AI Proactive Outbound Engine)
Workstream: **Backend — Phase 4 (Database / Persistence)**
Maintained by: Asaf

> This file is the live execution tracker for the **persistence layer** only. It follows the same
> standard as `PLAN.md`. `CLAUDE.md` defines the rules; `QA_checklist.md` §12 defines how each `DB*`
> check is verified; `NOTES.md` records decisions. Approved design plan:
> `~/.claude/plans/moonlit-herding-moon.md`.

---

## Why this exists (the problem)

There is **no durable database** today. Verified from the code (2026-06-20):

- `lead_store.py:34` — `mongomock.MongoClient()` (in-memory); `contacts.json` is `insert_many`'d on
  first call and **wiped on process exit**.
- `crm_store.py:49` — a separate in-memory `mongomock` `leads` workspace that starts **empty** and is
  populated only by in-process upserts; **nothing survives the run**.
- `api_server.py` — re-seeds 16 demo leads on every startup (`lifespan` → `api_seed.seed_demo()`); the
  only disk persistence anywhere is the `qualified_leads.json` export.

The whole stack already speaks MongoDB document semantics (`find_one`, `replace_one(upsert=True)`,
`update_one($set)`, `insert_many`, `find`), which drives the technology choice.

## Decisions (Asaf, 2026-06-20)

- **Technology:** real **MongoDB via `pymongo`**, with a **`mongomock` fallback** selected by the
  `MONGO_URI` env var (set → real Mongo; unset → mongomock). Rationale + rejected alternatives
  (SQLite, PostgreSQL) in `NOTES.md`.
- **Deployment:** **local Docker** Mongo for dev (`docker-compose.yml`, `mongo:7`, named volume).
- **Scope (this pass):** the **core stores only** — `contacts` (`lead_store.py`) + the `leads`
  workspace (`crm_store.py`). The brands catalog + `gtm_policies.txt` stay file inputs. ICP docs and
  outreach history are deferred (noted for `backend_connection_plan.md`).

## Hard constraints preserved (graded contracts — do not break)

- **Import-safety (ENV4):** no DB connection at import; the client is built lazily on first use.
- **Policy-4 auth gate** stays the single chokepoint (`lead_store.authenticate_and_get_contact`).
- **No secrets in tracked files:** the connection string lives only in `MONGO_URI` (env); `.env`
  gitignored; `.env.example` holds a placeholder only.
- **Test baseline:** the full offline suite stays **754 passed / 1 skipped (S10)** with `MONGO_URI`
  unset (mongomock path). *(PM-verified in `.venv` at session start, 2026-06-20 — 754/1/0 in 32.98s.)*
- **Untouched graded contracts:** tool count 10, `answer_question` byte-stable, `FALLBACK_MESSAGE`
  exact — none are in scope for this layer.

---

## How to use this file

- Work one stage at a time; do not advance until the stage's DoD passes (run, not inspected).
- Every DoD item references a `DB*` check in `QA_checklist.md` §12.
- Execution runs the `ORCHESTRATION.md` loop: PM briefs → `swe-executer` (cold, per stage) → PM
  re-verifies in `.venv` → `swe-reviewer` gate on graded-adjacent stages (D1/D2/D3) → advance or retry.
- The PM writes no production code; the executer does. The PM marks a stage ✅ only after its own
  verification (+ an APPROVE verdict where the reviewer gate fires).

Status values: ⬜ Not started · 🔄 In progress · 🟡 Awaiting verification · ⚠️ Blocked · ✅ Complete

---

## Stage tracker

| Stage | Name | DoD checks (`QA_checklist.md` §12) | Reviewer gate | Status |
|---:|---|---|:---:|---|
| D0 | Dependency + infra gate (pin `pymongo`, Docker, `.env`) | `DB0`–`DB1` | — | ✅ Complete |
| D1 | `db.py` connection layer (lazy, env-driven fallback) | `DB2`–`DB3` | ✅ | ✅ Complete |
| D2 | Route both stores through `db.py` + idempotent contacts seed | `DB4`–`DB5` | ✅ | ✅ Complete |
| D3 | Durability, indexes & restart proof | `DB6`–`DB8` | ✅ | ✅ Complete |
| D4 | Packaging + docs + handback | `DB9` | — | ✅ Complete |

---

## Stage D0 — Dependency + infra gate

**Goal:** pin the new dependency and stand up local Mongo **without touching app code**.

**Inputs:** `requirements.txt`; `.gitignore`; the live `.venv`.

**Outputs:** `pymongo==<captured>` in `requirements.txt` (keep `mongomock==4.1.2`); `docker-compose.yml`
(`mongo:7`, named volume, port 27017); `.env.example` with a placeholder `MONGO_URI`; `.gitignore`
covers `.env`.

**Definition of Done (QA: `DB0`–`DB1`):**
- [x] `DB0` — `pymongo==4.17.0` captured from the actual `.venv` install (not guessed); no wildcards;
  `mongomock==4.1.2` retained; full suite **754/1** with `MONGO_URI` unset (PM-verified before the edit;
  a `requirements.txt` line cannot change the running `.venv`).
- [x] `DB1` — no secret in any tracked file (PM grep clean); `.env` gitignored (`.gitignore:28`);
  `.env.example` is the localhost placeholder only and is itself tracked; `docker compose config` parses.

**Status:** ✅ Complete — PM-verified in `.venv` 2026-06-20. `pymongo==4.17.0` (+ transitive `dnspython
2.8.0`) installed; suite held at 754/1 with it present. Executer wrote `requirements.txt` pin,
`docker-compose.yml` (`mongo:7` + named volume), `.env.example` (placeholder), `.gitignore` `.env` rule.
No app code touched; no graded contract → no reviewer gate. One cosmetic deviation: executer dropped the
obsolete `version:` key from compose (Compose v2 warns on it) — non-contract.

---

## Stage D1 — `db.py` connection layer (lazy, env-driven fallback)  *(reviewer gate)*

**Goal:** one import-safe place that returns the correct Mongo client.

**Inputs:** `mongomock`/`pymongo`; the lazy-singleton pattern from `lead_store.py`.

**Outputs:** new module `db.py`: `get_mongo_client()` lazy singleton (`pymongo.MongoClient(MONGO_URI)`
if `MONGO_URI` set, else `mongomock.MongoClient()`); `get_database()` → `client[DB_NAME]` (default
`gtm_db`). Env read **inside** the getter (testable). `tests/test_db.py` covering both branches.

**Definition of Done (QA: `DB2`–`DB3`):**
- [x] `DB2` — ENV4 holds with `db.py` added (`db._client` `None` until first call; PM-probed `import db,
  main, lead_store, crm_store, rag_engine, api_server` from an empty cwd `/tmp` → all clean, singletons `None`).
- [x] `DB3` — branch selection correct under monkeypatched env (set → `pymongo.MongoClient`; unset/empty →
  `mongomock.MongoClient`); singleton; `get_database()` default `gtm_db` + `DB_NAME` override; no real network.

**Status:** ✅ Complete — PM-verified in `.venv` 2026-06-20. New `db.py` (64 lines, import-safe) +
`tests/test_db.py` (10 tests). Full regression **764 passed, 1 skipped (S10), 0 failed** (754 + 10 new).
**`swe-reviewer` gate: APPROVE** — 0 Critical / 0 Important / 0 Minor; confirmed byte-compliant with the
brief, import side-effect-free, no URI logging, scope confined to the two new files.

---

## Stage D2 — Route both stores through `db.py` + idempotent contacts seed  *(reviewer gate)*

**Goal:** make the stores persistent without changing their public behavior.

**Inputs:** `db.py` (D1); `lead_store.py`; `crm_store.py`; `tests/conftest.py`.

**Outputs:** `lead_store.get_lead_data_collection()` + `crm_store.get_crm_collection()` use
`db.get_database()[...]`. **Critical idempotency fix:** `get_lead_data_collection()` seeds `contacts.json`
**only when the collection is empty** (today it `insert_many`s unconditionally — would duplicate against a
persistent Mongo on every restart). `crm_store` upserts are already idempotent. `tests/conftest.py` also
resets the new `db._client` singleton.

**Definition of Done (QA: `DB4`–`DB5`):**
- [x] `DB4` — both stores obtain their collection via `db.get_database()`; the Policy-4 auth gate is
  byte-stable (PM probe: valid passes + key stripped; wrong-key == no-key generic denial); CRM shape unchanged.
- [x] `DB5` — contacts seed idempotent (`count_documents({}) == 0` guard; `tests/test_persistence.py`
  passes); `conftest.py` resets all three singletons; full regression **765 passed, 1 skipped, 0 failed**.

**Status:** ✅ Complete — PM-verified in `.venv` 2026-06-20. `lead_store`/`crm_store` getters route through
`db.py`; `import mongomock` removed from both; idempotent seed-if-empty fixes the would-be duplicate-on-restart
bug. PM fix: added `"db"` to `LOCAL_MODULES` in `tests/test_integration.py` (H1 packaging — `db` is a local
module, same pattern as `crm_store`). **`swe-reviewer` gate: APPROVE** — 0 Critical / 0 Important; 2 Minor
(both non-blocking, logged): (a) the broad `git diff HEAD` of `test_integration.py` surfaces pre-existing
Phase-2/3 edits — not D2's; (b) `test_persistence.py` uses `TestKeyAlice/Bob` vs the `TestKey001/002`
convention — synthetic, no secret risk.

---

## Stage D3 — Durability, indexes & restart proof  *(reviewer gate)*

**Goal:** prove data survives a process restart and enforce key uniqueness.

**Inputs:** D1/D2; a running local Docker Mongo (`MONGO_URI` set).

**Outputs:** idempotent `create_index` (unique `leads.uniq_id`, unique `contacts.email`,
`contacts.target_brand_id`) in the getters, guarded to not error under mongomock; `scripts/seed_db.py`
(idempotent, seed-if-empty) to load `contacts.json` into a real Mongo; an integration test that (against
real Mongo) upserts a lead, drops the client singleton, reconnects, and finds it still present.

**Definition of Done (QA: `DB6`–`DB8`):**
- [x] `DB6` — indexes present + uniqueness enforced under real Mongo (PM live-verified: unique `leads.uniq_id`
  + `contacts.email`, `target_brand_id` index; duplicate `uniq_id` → `DuplicateKeyError`). Index creation
  gated behind `db.using_real_mongo()` so the mongomock path is byte-identical.
- [x] `DB7` — cross-restart round-trip persists (PM live-verified: upsert → reset singletons → reconnect →
  lead present); `skipif` no `MONGO_URI` (gated like `S10`); DB5 gated `OFFLINE_ONLY` (skips under real Mongo).
- [x] `DB8` — `scripts/seed_db.py` idempotent (PM ran it twice against Docker Mongo → `contacts: 6` both
  times; mongosh confirms exactly 6 docs, no duplication).

**Status:** ✅ Complete — PM-verified in `.venv` 2026-06-20 against Docker Mongo (`reactfirst-mongo`, `mongo:7`).
Offline suite **765 passed, 5 skipped (S10 + 4 live DB6/DB7), 0 failed**; live `pytest tests/test_persistence.py`
with `MONGO_URI` set → **4 passed, 1 skipped (DB5 offline-only)**. **`swe-reviewer` gate: APPROVE** — 0
Critical / 0 Important; 1 Minor (a live test locates `contacts.json` by path rather than cwd — more robust,
non-blocking). PM hardening: added `OFFLINE_ONLY` gate to DB5 so it can't false-fail against persistent Mongo.

---

## Stage D4 — Packaging + docs + handback

**Goal:** ship the layer cleanly and record the decision.

**Inputs:** D0–D3; `MANIFEST.txt`; `CLAUDE.md`; `NOTES.md`.

**Outputs:** `db.py` + `pymongo` added to `MANIFEST.txt`; `CLAUDE.md` (§1.1 pins, §2 layout, §3.4
import-safety) + `NOTES.md` updated (persistence decision, rejected SQLite/Postgres, index choices);
final green regression + ENV4 from an empty dir.

**Definition of Done (QA: `DB9`):**
- [x] `DB9` — `MANIFEST.txt` (+`db.py` + infra note) and `CLAUDE.md` (§1.1 pin, §2 layout, §3.4
  import-safety) updated; NOTES Phase-4 handback appended; ENV4 holds for all 6 modules incl. `db.py` from
  an empty cwd; full regression **765 passed, 5 skipped (S10 + 4 live), 0 failed** (packaging tests H1/H5 green).

**Status:** ✅ Complete — PM-done + verified in `.venv` 2026-06-20 (PM-owned doc/packaging stage, no
production code → no executer spawn, no reviewer gate).

---

## Verification (how the layer is proven)

- **Offline (always, every stage):** full `tests/` regression stays **754 passed / 1 skipped** with
  `MONGO_URI` unset; ENV4 re-proven from an empty tmp dir after each store edit; auth-gate + CRM-shape
  probes byte-stable; secrets-grep on tracked files clean.
- **Real-DB (Docker, D3):** `docker compose up -d mongo`; `python scripts/seed_db.py`;
  `MONGO_URI=mongodb://localhost:27017`; run the `DB7` restart round-trip; confirm `mongosh` shows
  `gtm_db.leads` / `gtm_db.contacts` populated with unique indexes.

---

## Current state

- **Current stage:** **PHASE 4 COMPLETE** — D0 ✅, D1 ✅, D2 ✅, D3 ✅, D4 ✅. The persistence layer is built
  and verified; the CRM now persists leads/contacts across restarts when `MONGO_URI` is set.
- **Baseline (PM-verified `.venv` 2026-06-20):** offline `tests/` = **765 passed, 5 skipped (S10 + 4 live
  DB6/DB7), 0 failed**; live `tests/test_persistence.py` (Docker Mongo) = **4 passed, 1 skipped (DB5)**.
- **Reviewer gates:** D1/D2/D3 all **APPROVE** (0 Critical / 0 Important). Minors logged, non-blocking.
- **No graded contract touched:** tool count 10, `answer_question` byte-stable, `FALLBACK_MESSAGE` exact,
  Policy-4 auth gate + CRM record shape unchanged.
- **Out of scope (deferred):** ICP-document + outreach-history persistence; wiring the persistent DB into
  the API/pipeline — captured plan-only in `backend_connection_plan.md`.
- **Next action:** none on the data layer. The follow-on `backend_connection_plan.md` (plan only) describes
  connecting this DB to the API/pipeline; it is for Asaf's review, not yet implemented.
