# Handback — Stage I1

## 1. What changed

Three new files created (no existing files modified):

- `/Users/asaframati/Documents/CRM/api_server.py` — FastAPI `app` with:
  - A no-op `lifespan` async context manager (`# I2: call api_seed.seed_demo() here` comment placeholder).
  - `GET /api/health` → `{"status": "ok"}` (200).
  - CORS middleware: `allow_origins=["http://localhost:5173"]`, `allow_methods=["*"]`, `allow_headers=["*"]`.
  - Zero backend imports at module top-level; import-safe.
  - Run command in module docstring: `uvicorn api_server:app --port 8000`.

- `/Users/asaframati/Documents/CRM/tests/conftest.py` — Autouse function-scoped pytest fixture `reset_singletons` that resets `crm_store._leads_collection = None` and `lead_store._collection_instance = None` both before and after every test. Uses try/except guards so it is harmless if an attribute is absent.

- `/Users/asaframati/Documents/CRM/tests/test_api.py` — 12 tests across three classes:
  - `TestINTG1ImportSafety` (2 tests): subprocess probe from empty `tmp_path` + in-process singleton check.
  - `TestINTG2SingletonReset` (3 tests): verifies the conftest autouse fixture is active at test start.
  - `TestINTG3HealthAndCORS` (7 tests): health 200, JSON body, content-type, CORS class presence, CORS origins value, preflight response, lifespan attribute.

No existing file was modified (`main.py`, `crm_store.py`, `lead_store.py`, `rag_engine.py`, any existing test).

## 2. DoD checklist

- `INTG1` — **written and test-verified** — subprocess probe from an empty `tmp_path` exits 0 with no stdout/stderr noise; in-process probe confirms singletons stay `None` after `import api_server`.
- `INTG2` — **written and test-verified** — `tests/conftest.py` autouse fixture resets singletons; three tests prove the fixture is active (singletons are `None` at test start).
- `INTG3` — **written and test-verified** — `GET /api/health` returns 200 + `{"status":"ok"}`; CORSMiddleware present with `allow_origins=["http://localhost:5173"]`; lifespan context manager confirmed.

## 3. QA results

All checks run with `.venv/bin/python -m pytest tests/test_api.py -v`:

```
tests/test_api.py::TestINTG1ImportSafety::test_import_api_server_no_side_effects PASSED
tests/test_api.py::TestINTG1ImportSafety::test_import_api_server_no_backend_imports_at_top_level PASSED
tests/test_api.py::TestINTG2SingletonReset::test_leads_collection_is_none_at_test_start PASSED
tests/test_api.py::TestINTG2SingletonReset::test_lead_store_instance_is_none_at_test_start PASSED
tests/test_api.py::TestINTG2SingletonReset::test_singleton_written_in_one_test_does_not_leak_to_next PASSED
tests/test_api.py::TestINTG3HealthAndCORS::test_health_returns_200 PASSED
tests/test_api.py::TestINTG3HealthAndCORS::test_health_returns_correct_json PASSED
tests/test_api.py::TestINTG3HealthAndCORS::test_health_content_type_is_json PASSED
tests/test_api.py::TestINTG3HealthAndCORS::test_cors_middleware_is_present PASSED
tests/test_api.py::TestINTG3HealthAndCORS::test_cors_allow_origins_is_localhost_only PASSED
tests/test_api.py::TestINTG3HealthAndCORS::test_cors_preflight_allowed_from_localhost PASSED
tests/test_api.py::TestINTG3HealthAndCORS::test_app_has_lifespan PASSED

12 passed, 2 warnings in 0.43s
```

Full regression with `.venv/bin/python -m pytest tests/ -v --tb=short`:

```
696 passed, 1 skipped, 246 warnings in 31.94s
```

Baseline before this stage: 684 passed, 1 skipped, 0 failed.
Delta: +12 (exactly the new test_api.py tests). No regressions.

Additional in-process probes (run, not inspected):
- `import api_server` → `crm_store._leads_collection is None` + `lead_store._collection_instance is None` confirmed.
- `TestClient(api_server.app).get('/api/health')` → 200, `{"status": "ok"}` confirmed.
- `app.user_middleware` has `CORSMiddleware` with `allow_origins=['http://localhost:5173']` confirmed.
- `router.lifespan_context` is non-None confirmed.
- `fastapi.middleware.cors.CORSMiddleware is starlette.middleware.cors.CORSMiddleware` → `True` confirmed (the `is` identity check in the test is valid).

## 4. Decisions made

1. `allow_origins=["http://localhost:5173"]` only (as specified in the brief). Decision recorded in NOTES.md (2026-06-19 Stage I1 entry).
2. Used `contextlib.asynccontextmanager` for the lifespan function — the standard FastAPI >= 0.93 pattern; the lifespan is detected via `router.lifespan_context` in the test.
3. No backend imports at `api_server.py` module top-level. Any future handler that needs crm_store must import it lazily inside the handler or the lifespan body.
4. `tests/conftest.py` uses try/except guards around both singleton resets so the fixture is safe if module attributes are renamed or absent in a future refactor.

## 5. DECISION-NEEDED

None. No tool signatures, schemas, policy constants, loop contract, or graded literals were touched or need changing.

One risk surfaced (non-blocking, does not require Asaf's decision): the `starlette.testclient` / `httpx` combination emits a deprecation warning ("install `httpx2` instead"). All 12 tests pass despite this warning; it is a cosmetic issue at the pinned `fastapi==0.137.2` / `httpx==0.28.1` versions. If it escalates to a hard error in a later stage, the fix is to add `httpx2` to `requirements.txt` — but that is a pinned-dep change which should be surfaced to the PM at that time, not pre-emptively now.

## 6. Deviations

None. No existing file was modified. Scope exactly matched the brief:
- CREATE `api_server.py` — done.
- CREATE `tests/conftest.py` — done.
- CREATE `tests/test_api.py` with INTG1/INTG2/INTG3 — done.
- No endpoints with real data, no seed, no frontend changes, no existing test modifications.

## 7. Blockers / risks

- `starlette.testclient` / `httpx==0.28.1` deprecation warning (see §5 above). Non-blocking for I1.
- Stage I2 will call `api_seed.seed_demo()` inside the lifespan body. The placeholder comment is in place. That import must remain lazy (inside the lifespan body, not at module top-level of `api_server.py`) to preserve ENV4.

## 8. Next recommended action

Dispatch Stage I2 (`briefs/stage-I2.md`) — Leads + ICP endpoints + adapters + seed (`INTG4`–`INTG6`). Creates `api_seed.py` + `api_adapters.py` and 5 leads/ICP routes; wires the lifespan body to call `api_seed.seed_demo()`.
