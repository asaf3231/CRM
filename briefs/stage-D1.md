# Brief — Stage D1: `db.py` connection layer (lazy, env-driven fallback)
Read first: CLAUDE.md (§3.4 import-safety) → data_plan.md (Stage D1) → QA_checklist.md §12 (`DB2`,`DB3`) → NOTES.md (2026-06-20 Phase 4 entry), then this brief.

Goal: create ONE import-safe module, `db.py`, that returns the correct Mongo client — real `pymongo`
when `MONGO_URI` is set, else `mongomock`. **Do not touch the stores yet** (that is D2).

Scope (do ONLY this stage):
- **`db.py`** (NEW, repo root). Mirror the lazy-singleton + import-safety style of `lead_store.py`:
  - Module docstring noting: import-safe (zero side effects at import); the `MONGO_URI`/`DB_NAME` env
    contract; the mongomock fallback.
  - Top-level imports: `os`, `pymongo`, `mongomock`. A module-level singleton `_client = None`.
    **Nothing else runs at import** — no client construction, no env-driven work, no I/O.
  - `get_mongo_client()` — lazy singleton:
    - reads `os.environ.get("MONGO_URI")` **inside the function** (so tests can monkeypatch).
    - if it is set/non-empty → construct `pymongo.MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)`
      (a modest timeout so a down server fails fast instead of hanging). Construction is lazy in pymongo
      — it does NOT connect until the first operation, which keeps this safe.
    - else → construct `mongomock.MongoClient()`.
    - cache in the module global `_client`, return it. A second call returns the SAME object.
  - `get_database()` — returns `get_mongo_client()[db_name]` where
    `db_name = os.environ.get("DB_NAME", "gtm_db")` is read **inside the function**.
  - Keep it small and dependency-light; no logging of any URI value (a URI can carry credentials).
- **`tests/test_db.py`** (NEW). Use a fixture/teardown that sets `db._client = None` and restores env
  around each test (monkeypatch). Cover:
  - **DB2 import-safety:** after `import db`, `db._client is None` (no client built at import). (An
    empty-dir `python -c "import db"` exit-0 check is run by the PM — you just must not do import-time work.)
  - **DB3 fallback branch (unset):** with `MONGO_URI` unset, `get_mongo_client()` returns an instance of
    `mongomock.MongoClient`.
  - **DB3 real branch (set):** with `MONGO_URI` monkeypatched to `mongodb://localhost:27017`,
    `get_mongo_client()` returns an instance of `pymongo.MongoClient`. **Do NOT call any method that
    triggers a connection** (no `list_database_names()`, no `.server_info()`) — only assert the type, so
    the test needs no running server.
  - **Singleton:** two calls to `get_mongo_client()` return the same object (`is`).
  - **`get_database()`:** returns a db whose `.name == "gtm_db"` by default, and honors a `DB_NAME`
    override (monkeypatched). (Under mongomock, `get_database().name` works.)

QA checks to PASS (PM re-runs in `.venv`):
- `DB2` — ENV4 holds: `import db` (and `import main, lead_store, crm_store, rag_engine, api_server`) is
  side-effect-free; `db._client` is `None` until the first `get_mongo_client()` call.
- `DB3` — branch selection correct under monkeypatched env (set→`pymongo.MongoClient`,
  unset→`mongomock.MongoClient`); no real network in tests; `get_database()` name default + override.

Constraints (from CLAUDE.md):
- **Import-safety is graded (ENV4).** Absolutely no client construction, env-driven logic, file read, or
  network at import time — only defs + the `_client = None` global.
- Read `MONGO_URI` / `DB_NAME` **inside** the getters, never at module scope (testability + safety).
- Never log or print a connection-string value.
- Do NOT edit `lead_store.py`, `crm_store.py`, `tests/conftest.py`, `main.py`, or any other module — D1
  adds `db.py` + its test only. Routing the stores through `db.py` is D2.

Inputs / files you may touch: `db.py` (new), `tests/test_db.py` (new).

Do NOT: advance to D2 (do not refactor the stores or conftest); change any tool signature / JSON schema /
policy constant / loop contract / graded literal — surface any such need as DECISION-NEEDED.

Deliver: write `handbacks/stage-D1.md` in the standard handback format and return it as your final message.
If your sandbox can run pytest, report the result; if not, say so — the PM will run the full suite.
