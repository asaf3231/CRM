# Brief — Stage I1: API scaffold + import-safety + conftest (Phase 3 — Integration Layer)
Read first: CLAUDE.md → PLAN.md (Phase 3 section) → QA_checklist.md §11 → NOTES.md (2026-06-19 Phase 3 entry), then this brief.

Goal: Stand up the FastAPI app skeleton for the new integration server, with test isolation and
import-safety — NO endpoints with real data and NO seed yet (those are Stage I2).

Context: Phase 3 adds an ADDITIVE FastAPI server (`api_server.py`) exposing the backend to the React
frontend. The graded backend is untouched — `main.py` is NOT modified and NOT imported by the server's
import path in a way that runs side effects. Full approved plan: `~/.claude/plans/sprightly-tinkering-hennessy.md`.

Scope (do ONLY this stage):
1. Create `api_server.py` (repo root):
   - Build a FastAPI `app`. Add CORS middleware with `allow_origins=["http://localhost:5173"]` only
     (localhost dev; recorded as a decision in NOTES). `allow_methods=["*"]`, `allow_headers=["*"]`.
   - Route `GET /api/health` → `{"status": "ok"}` (200).
   - Define a FastAPI **`lifespan`** async context manager and pass it to `FastAPI(lifespan=...)`.
     In I1 the lifespan body is a **no-op** with a comment `# I2: call api_seed.seed_demo() here`.
     (Do NOT import or call any seed yet.)
   - **Import-safety:** importing `api_server` must do ZERO backend work — no `crm_store`/`lead_store`/
     `main` calls at import, no file reads, no network. Any backend import must be lazy (inside a
     handler or the lifespan body), not at module top level. Constructing `app` must be side-effect-free.
   - Run command (put in a module docstring): `uvicorn api_server:app --port 8000`.
2. Create `tests/conftest.py` (repo root tests dir):
   - An **autouse** fixture (function-scoped) that resets the lazy singletons to `None` BEFORE and AFTER
     every test: `crm_store._leads_collection = None` and `lead_store._collection_instance = None`.
     Import those modules inside the fixture; guard with `getattr`/try so it is safe if an attr is absent.
   - Rationale: I2 will seed `crm_store` on server startup; this fixture stops that seed (and any test's
     writes) from leaking across tests and breaking the existing CRM*/DISC*/ENV4 suite.
3. Create `tests/test_api.py` with the I1-scope checks (mark with the QA IDs in comments):
   - `INTG1`: a subprocess test — run `python -c "import api_server"` with `env` stripped of
     `ANTHROPIC_API_KEY`, cwd = a fresh `tmp_path` with none of the 3 input files — assert exit code 0
     and no stdout/stderr noise. (Proves import side-effect-free.)
   - `INTG3`: using `fastapi.testclient.TestClient(api_server.app)`, assert `GET /api/health` returns 200
     and JSON `{"status":"ok"}`; assert the app has the CORS middleware configured.
   - (INTG2 is exercised by `tests/conftest.py` itself; add one test asserting that at test start
     `crm_store._leads_collection is None` to prove the reset fixture runs.)

Constraints (from CLAUDE.md):
- **Import-safety / ENV4 is graded.** `import main, lead_store, rag_engine, crm_store` AND
  `import api_server` must all be side-effect-free. `main.py` must NOT be edited and must NOT import
  `api_server`.
- No raw `eval`/`exec`. OS-agnostic paths (`os.path`/`pathlib`). No secrets in tracked files.
- Do not touch `frontend/`. Do not modify `main.py`, `crm_store.py`, `lead_store.py`, `rag_engine.py`,
  or any existing test.

Inputs / files you may touch: CREATE `api_server.py`, `tests/conftest.py`, `tests/test_api.py` only.

Do NOT: add endpoints that read real data or any seed (Stage I2); advance past this stage; change a
tool signature / schema / policy constant / the loop contract / a graded literal — surface those as
DECISION-NEEDED.

NOTE on verification: your sandbox cannot run pytest — the PM runs it. Write the code + tests; in your
handback, quote the exact files/functions created and state clearly what you wrote vs verified. If a
check fails when the PM runs it and you are re-briefed, use the `systematic-debugging` skill.

Deliver: write `handbacks/stage-I1.md` in the standard format; return it as your final message.