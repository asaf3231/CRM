# Brief — Stage D0: Dependency + infra gate (Phase 4 / Durable Persistence)
Read first: CLAUDE.md → data_plan.md → QA_checklist.md §12 → NOTES.md (2026-06-20 Phase 4 entry), then this brief.

Goal: pin the new DB dependency and stand up local Docker MongoDB **without touching any app code**.

Context: Phase 4 adds a real database (MongoDB via `pymongo`, with a `mongomock` fallback chosen by the
`MONGO_URI` env var). This stage is **infra + deps only** — no `db.py`, no store edits (those are D1/D2).
The PM has already installed `pymongo` into `.venv` and captured the exact version, and confirmed the full
suite stays **754 passed, 1 skipped** with it present and `MONGO_URI` unset.

Scope (do ONLY this stage):
- **requirements.txt** — add the line `pymongo==4.17.0` (this exact version — captured from the real
  `.venv` install; do NOT guess or change it). Keep `mongomock==4.1.2` exactly as-is (it is now the
  offline/test fallback driver). Place `pymongo==4.17.0` in the core (non-Phase-3) dependency block,
  logically next to `mongomock==4.1.2`. Do not reorder or alter other pins.
- **docker-compose.yml** (NEW, repo root) — one `mongo` service: image `mongo:7`, container name e.g.
  `reactfirst-mongo`, port mapping `27017:27017`, a NAMED volume (e.g. `mongo_data:/data/db`) declared
  under top-level `volumes:`, and `restart: unless-stopped`. No credentials/auth (local dev only).
- **.env.example** (NEW, repo root) — placeholder env file, tracked, with NO real secret:
  `MONGO_URI=mongodb://localhost:27017` and `DB_NAME=gtm_db`. Add a short comment that the real values
  live in a gitignored `.env` and that unsetting `MONGO_URI` makes the app fall back to mongomock.
- **.gitignore** — ensure `.env` is ignored. If a `.env` ignore rule is already present, change nothing;
  if absent, add a single `.env` line. (Do NOT ignore `.env.example`.)

QA checks to PASS (the PM re-runs these in `.venv` — you just make them true):
- `DB0` — `pymongo==4.17.0` present (exact `==`, no wildcard); `mongomock==4.1.2` retained; the full
  suite stays **754 passed, 1 skipped, 0 failed** with `MONGO_URI` unset.
- `DB1` — no real connection string / credential in any tracked file; `.env` is gitignored; `.env.example`
  contains only the localhost placeholder above.

Constraints (from CLAUDE.md):
- Do NOT touch any app/code module (`main.py`, `lead_store.py`, `crm_store.py`, `rag_engine.py`,
  `api_server.py`, `api_seed.py`, `api_adapters.py`) or the `tests/`. This stage writes only deps + infra.
- No secrets in tracked files (G4). The only env value committed is the localhost placeholder.
- `docker-compose.yml` must be valid YAML (`docker compose config` should parse it).

Inputs / files you may touch: `requirements.txt`, `docker-compose.yml` (new), `.env.example` (new),
`.gitignore`.

Do NOT: advance past D0; create `db.py`; edit any store or `main.py`; change a tool signature / JSON
schema / policy constant / the loop contract / a graded literal — surface any such need as DECISION-NEEDED.

Deliver: write `handbacks/stage-D0.md` in the standard handback format (what changed, DoD checklist with
each DB id, decisions, deviations, blockers, next action) and return it as your final message.
