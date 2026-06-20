# backend_connection_plan.md — Connect the persistent DB to the backend

Project: **Autonomous Agentic GTM Engine & Value-Hook Pipeline** (ReactFirst AI Proactive Outbound Engine)
Workstream: **Backend — Phase 5 (proposed): DB ↔ backend wiring**
Maintained by: Asaf

> ⚠️ **THIS IS A PLAN ONLY — NOTHING HERE IS IMPLEMENTED.** It follows the `PLAN.md` standard and is
> handed to Asaf for review/approval before any coding. It builds on the completed Phase 4 persistence
> layer (`data_plan.md`, stages D0–D4 ✅: `db.py` + DB-backed stores + indexes + `scripts/seed_db.py`).

---

## Context — why this is needed

Phase 4 made the **stores** durable (`lead_store`/`crm_store` now read/write a real MongoDB when
`MONGO_URI` is set, mongomock otherwise). But the **backend that surrounds them** does not yet fully
*use* that persistence. Verified from the code (2026-06-20):

- **`api_server.py` re-seeds demo data on every startup.** The ASGI `lifespan` calls
  `api_seed.seed_demo()`, which **upserts 16 demo leads** (`api_seed._SEED_RECORDS`) into `crm_store`
  on each boot. Against a *persistent* Mongo this now runs every restart — so it will **overwrite any
  real edits** to those 16 `uniq_id`s and mixes demo rows into a real workspace.
- **The API is read-only + find-more.** Routes today: `GET /api/leads`, `GET /api/leads/stats`,
  `POST /api/leads/find-more`, `GET /api/icp`, `GET /api/icp/suggestions`, `GET /api/outreach/stats|cohorts|enrollments`.
  There are **no write endpoints** — the FE cannot persist a stage change, an ICP save, or an outreach
  enrollment. (`crm_store.update_lead_stage` / `attach_contact` exist but are unreachable via HTTP.)
- **Stats / ICP / outreach are static seeds**, not derived from the persisted workspace:
  `GET /api/leads/stats` returns the hardcoded `api_seed.SEED_STATS`; `GET /api/icp` returns
  `api_seed.SEED_ICP`; the outreach routes synthesize from a fixed `_DEMO_DAILY_CAP` demo cohort.
- **`/api/health` does not check Mongo.** It returns `{"status":"ok"}` unconditionally, so a down DB is
  invisible to the FE.
- **The pipeline already persists** — `main()` / `write_qualified_leads` / `run_outreach_pipeline` upsert
  into `crm_store`, so a real `answer_question` run now writes durable leads. But there is **no HTTP path**
  to trigger a live run (the I5 live-pipeline routes are still deferred, OQ-7-gated).

**Goal of this phase:** make the API **serve and mutate the durable workspace**, stop clobbering real data
with the demo seed, surface DB health, and (optionally, key-gated) let a real pipeline run feed the DB.

## Decisions still needed from Asaf (do not assume)
1. **Demo-seed policy:** seed-if-empty, an explicit `SEED_DEMO=1` flag, or drop the auto-seed entirely
   (a one-time `scripts/seed_db.py --demo`)? (Recommended: env-gated `SEED_DEMO`, default off when
   `MONGO_URI` is set.)
2. **ICP / outreach persistence:** Phase 4 scoped these OUT. Persisting ICP documents + outreach history
   needs **new collections** (`icp_documents`, `outreach_events`) — confirm whether to add them here or
   keep ICP/outreach as computed/seed for now.
3. **Live pipeline (C4):** depends on **OQ-7 keys** (`ANTHROPIC_API_KEY` + transports). Confirm whether to
   build the `ENABLE_LIVE` path now or keep it deferred (merges with the existing I5 stub).
4. **FE coordination:** the frontend is a **separate PM lane** (`frontend/`). Write-endpoint shapes must be
   agreed with the FE `api.ts` contract; this plan defines the backend side only.

---

## Status legend
⬜ Proposed (not started) · 🔄 In progress · ✅ Complete — **C0–C2 + C6 executed (Asaf, 2026-06-20); C3–C5 plan-only.**

## Stage tracker (proposed)

| Stage | Name | DoD checks (`QA_checklist.md` §13) | Status |
|---:|---|---|---|
| C0 | Demo-seed policy: stop clobbering persisted data | `CONN0`–`CONN1` | ✅ Complete |
| C1 | DB-aware `/api/health` + connection lifecycle | `CONN2` | ✅ Complete |
| C2 | Read endpoints serve real persisted data (computed stats) | `CONN3`–`CONN4` | ✅ Complete |
| C3 | Write endpoints (stage / enrollment) — persist FE mutations | `CONN5`–`CONN6` | ⬜ Proposed |
| C4 | Live-pipeline ingest (`ENABLE_LIVE`, OQ-7-gated) — merges I5 | `CONN7`, `CONN11`–`CONN12` | 🔄 Code complete (offline-green); live pending keys |
| C5 | FE wiring + cross-restart Preview proof | `CONN8` | ⬜ Proposed |
| C6 | ICP durable substrate (read-only persistence) — decision #2, read half | `CONN9`–`CONN10` | ✅ Complete |

---

## Stage C0 — Demo-seed policy: stop clobbering persisted data
**Goal:** the API must not overwrite real persisted leads with the 16 demo rows on every boot.
**Inputs:** `api_server.py` (`lifespan`), `api_seed.seed_demo()`, `db.using_real_mongo()`.
**Approach (proposed):** gate `seed_demo()` behind an env flag (e.g. `SEED_DEMO`) and/or seed-if-empty;
when `MONGO_URI` is set and the workspace is non-empty, **skip** the demo seed. Keep the offline mock path
(no `MONGO_URI`) seeding the demo so the FE dev experience is unchanged.
**DoD:** `CONN0` with a persisted non-empty `leads` collection, a server restart does **not** modify
existing records; `CONN1` offline (mongomock) demo still seeds (FE dev unchanged). Import-safety preserved.
**Status:** ✅ Complete — executed via `swe-executer` + PM-verified 2026-06-20. `api_seed.seed_demo()` is now
seed-if-empty (skips when `leads` is non-empty) + a `SEED_DEMO` opt-out; `api_server.py` lifespan unchanged.
Offline suite **768 passed, 5 skipped** (+3 CONN tests); **live proof** (Docker Mongo): boot1 seeded 16 →
real edit (`seed-lead-001`→"won") + a real lead (17) → simulated restart + boot2 **skipped** (count 17, the
"won" edit + real lead intact). No graded contract touched. Files: `Backend/api_seed.py`,
`Backend/tests/test_api.py` (+`TestSeedDemoGuard`).

## Stage C1 — DB-aware `/api/health` + connection lifecycle
**Goal:** surface real DB connectivity; reuse the shared client.
**Approach (proposed):** `/api/health` pings Mongo (`db.get_mongo_client().admin.command("ping")`) when
`MONGO_URI` is set and reports `{status, db: "up"|"down"|"mock"}`; handler catches the
`serverSelectionTimeoutMS=5000` failure and returns a degraded (not 500) body. No client built at import.
**DoD:** `CONN2` health reflects up / down / mock states; a stopped Mongo yields a graceful degraded
response, not a hang or uncaught 500.
**Status:** ✅ Complete — PM-implemented + verified 2026-06-20. `/api/health` pings Mongo when `MONGO_URI`
is set. Offline `CONN2` test green (db:"mock"); **live**: `https://backend-production-77e4.up.railway.app/api/health`
→ `{"status":"ok","db":"up"}` (Atlas ping). No client at import (ENV4 holds). Files: `api_server.py`.

## Stage C2 — Read endpoints serve real persisted data
**Goal:** the dashboard reflects the durable workspace, not static seeds.
**Approach (proposed):** `GET /api/leads/stats` computes the funnel from the persisted `leads` collection
(counts by GovBand/FitGrade/LeadKind via the existing `api_adapters` thresholds) instead of returning
`SEED_STATS`; `GET /api/leads` + `find-more` already read `crm_store` — verify against real Mongo.
**DoD:** `CONN3` `/api/leads` + `/api/leads/stats` reflect actual persisted records (add/modify a lead →
the response changes); `CONN4` adapter contract unchanged (camelCase; `contact_ids` + `corporate_access_key`
never emitted).
**Status:** ✅ Complete — PM-implemented + verified 2026-06-20. `GET /api/leads/stats` now computes the funnel
from `crm_store.all_leads()` via new `api_adapters.compute_stats_from_leads` (was static `SEED_STATS`).
Offline `CONN3`/`CONN4` tests green; full suite **777 passed / 5 skipped / 0 failed**. **Live**: public
`/api/leads/stats` → `goal/discovered/retained=9, aboveFloor=6, strong=1, review=8, "Live (>=3 ICP signals)"`
(reconciles with the 9 persisted real leads); no `corporate_access_key`/`contact_ids` in the body. ICP/outreach
read endpoints unchanged (ICP still seed — needs a new collection, decision #2, deferred). Files:
`api_server.py`, `api_adapters.py`, `tests/test_api.py`.

## Stage C3 — Write endpoints (the gap): persist FE mutations
**Goal:** let the FE persist changes through the API.
**Approach (proposed):** add `PATCH /api/leads/{uniq_id}/stage` → `crm_store.update_lead_stage`;
`POST /api/outreach/enroll` → persist `outreach_state` / call `run_outreach_pipeline` write paths;
(optional, decision #2) `PUT /api/icp` → persist an ICP doc. All write paths that touch private contact
fields go through the **Policy-4 auth gate** (no bypass). Agree shapes with FE `api.ts`.
**DoD:** `CONN5` a stage PATCH persists across a restart; `CONN6` no write path bypasses the auth gate or
emits `corporate_access_key`; invalid payloads return structured 4xx, never a 500.

## Stage C4 — Live-pipeline ingest (`ENABLE_LIVE`, OQ-7-gated) — merges I5
**Goal:** a real discovery run writes durable leads via HTTP.
**Approach (proposed):** an `ENABLE_LIVE`-gated route runs `answer_question` (keys required) whose
`write_qualified_leads` already upserts `crm_store` → now durable. Implements the deferred I5 routes
(`/api/pipeline/discover|swarm`). **Blocked on OQ-7 keys** — keep behind the flag; offline default unchanged.
**DoD:** `CONN7` with keys, a discovery run persists new leads queryable via `GET /api/leads`; without keys
the route is disabled and the rest of the API is unaffected.
**Status:** 🔄 Code complete + offline-verified (live pending Railway keys) — PM-implemented 2026-06-20.
**Deviation (Asaf-approved):** built as a **deterministic real-tool runner** (`Backend/pipeline_runner.py`),
NOT the 15-call `answer_question` loop — the loop qualifies inconsistently (feeds the ICP check thin strings;
NOTES 2026-06-20). The runner chains the same graded tools and is **ICP-driven**: reads the persisted ICP via
`api_seed.get_icp_document()` (the C6 seam), composes the search seed from `vertical`+`want_signals`, keeps the
graded `evaluate_icp_tags` gate untouched, and applies an `icp_tags`/`avoid_signals` overlay. Async job
(`POST`/`GET /api/pipeline/discover`, 2–5 min runs) gated by `ENABLE_LIVE` + `DISCOVERY_TOKEN` + a single-job
lock; job state in a `pipeline_jobs` collection. Catalog matches persist (Policy 1); net-new = show-only.
Offline suite **796 passed / 5+ skipped / 0 failed** (+13 `test_pipeline.py`); `main.py` untouched (graded
contracts byte-stable); ENV4 holds. **Live verification (deployed POST/poll) pending the 4 Railway vars.**
Files: `Backend/pipeline_runner.py`, `Backend/api_server.py`, `Backend/tests/test_pipeline.py`, `conftest.py`.

## Stage C5 — FE wiring + cross-restart Preview proof
**Goal:** prove end-to-end persistence in the running app.
**Approach (proposed):** flip the relevant `frontend/src/lib/api.ts` methods to the new write routes
(coordinate with the FE PM); two-server Preview-MCP check: create/modify a lead in the UI → **restart the
backend** → the change is **still there** (the headline proof that persistence is real).
**DoD:** `CONN8` a UI mutation survives a backend restart, shown live; `tsc --noEmit` clean; kill-Mongo →
graceful UI error (not a crash).

## Stage C6 — ICP durable substrate (read-only persistence)
**Goal:** make `/api/icp` serve a durable, editable ICP document from the DB instead of the in-memory
`SEED_ICP` constant — the read half of decision #2 (Asaf chose read-only; write endpoints stay deferred at C3).
**Inputs:** `api_seed.SEED_ICP`, `api_adapters.icp_doc_to_ui`, `db.get_database()`, the `crm_store` collection-
getter pattern.
**Approach (executed):** new `icp_documents` collection via a lazy getter `api_seed.get_icp_collection()`
(mirrors `crm_store.get_crm_collection()`; real-Mongo-only unique index on `icp_id`, mongomock-guarded).
`api_seed.seed_icp_if_empty()` (called from the ASGI lifespan alongside `seed_demo()`) inserts the SEED_ICP doc
**only when the collection is empty** and is **deliberately NOT gated on `SEED_DEMO`** (the ICP is baseline
config; Railway runs `SEED_DEMO=0`). `api_seed.get_icp_document()` reads the persisted doc (strips `_id`/`icp_id`)
and **falls back to a copy of `SEED_ICP`** if the collection is empty (never 500/empty). `GET /api/icp` and
`/api/icp/suggestions` now read `get_icp_document()`. No Policy-4 gate (ICP has no private contact fields); no
graded contract touched (tool count 10, `answer_question`, `FALLBACK_MESSAGE` byte-stable); FE contract unchanged.
**DoD:** `CONN9` (offline: served-from-DB, seed-if-empty, edit-reflected, SEED_ICP fallback, no secret/internal
keys) + `CONN10` (live restart durability + idempotent re-seed).
**Status:** ✅ Complete — PM-implemented + verified 2026-06-20. Offline full suite **783 passed / 6 skipped / 0
failed** (`MONGO_URI` unset; 777 + 6 CONN9; CONN10 live-gated skip). ENV4 holds for all 7 modules incl.
`api_seed._icp_collection` (lazy `None`). No reviewer gate (no graded contract — same as C0/C1/C2). **Deploy
note:** the first Railway boot after this ships seeds `icp_documents` into Atlas (currently empty) →
`/api/icp` then serves from Atlas. Files: `api_seed.py`, `api_server.py`, `tests/test_api.py`, `tests/conftest.py`.

---

## Constraints (carried from `CLAUDE.md`)
- Import-safety (ENV4): no DB connection at import; reuse `db.get_mongo_client()`.
- Policy-4 auth gate stays the single chokepoint for private contact fields on every new write path.
- No secrets in tracked files (`MONGO_URI` + any keys in env only).
- The graded engine (`main.py`) stays byte-stable: tool count 10, `answer_question`, `FALLBACK_MESSAGE`.
- The offline (mongomock, no `MONGO_URI`) test suite must stay green; live behavior is `skipif`/flag-gated.

## Verification (when executed)
- Offline: full `tests/` regression stays green; new `CONN*` tests gated like `S10`/`DB7`.
- Live (Docker Mongo): the C5 restart proof; `/api/health` up/down/mock; write→restart→read round-trip;
  auth-gate + no-`corporate_access_key` assertions on every new endpoint.

## Open risks
- Demo seed vs real data conflict (C0) — the highest-value early fix.
- ICP/outreach persistence needs new collections (decision #2) — scope creep if bundled.
- C4 is OQ-7-gated and overlaps the existing deferred I5.
- FE is a separate PM lane — write-endpoint shapes need cross-lane agreement.
