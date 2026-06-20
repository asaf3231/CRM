# Handback — Stage D0

## 1. What changed

Files touched (4 total, no app code modified):

- `/Users/asaframati/Documents/CRM/requirements.txt` — added `pymongo==4.17.0` on a new line directly after `mongomock==4.1.2`, in the core (non-Phase-3) dependency block. All other pins left exactly as-is.
- `/Users/asaframati/Documents/CRM/docker-compose.yml` — NEW file. One `mongo` service: image `mongo:7`, container name `reactfirst-mongo`, port `27017:27017`, named volume `mongo_data:/data/db`, `restart: unless-stopped`. Top-level `volumes:` block declares `mongo_data`. No credentials, no auth (local dev only). The `version` key was initially present but removed after `docker compose config` flagged it as obsolete — the file is valid without it.
- `/Users/asaframati/Documents/CRM/.env.example` — NEW file. Contains only the localhost placeholder (`MONGO_URI=mongodb://localhost:27017` and `DB_NAME=gtm_db`) plus a comment explaining that real values live in a gitignored `.env` and that unsetting `MONGO_URI` causes the app to fall back to mongomock. No real secret.
- `/Users/asaframati/Documents/CRM/.gitignore` — added a `.env` rule (with a section comment). `.env.example` is NOT ignored (correct — it is the tracked placeholder).

No app modules (`main.py`, `lead_store.py`, `crm_store.py`, `rag_engine.py`, `api_server.py`, `api_seed.py`, `api_adapters.py`) were touched. No tests were modified.

## 2. DoD checklist

- `DB0` — `pymongo==4.17.0` added with exact `==` pin; `mongomock==4.1.2` retained; full suite **754 passed, 1 skipped, 0 failed** with `MONGO_URI` unset. VERIFIED by running the suite.
- `DB1` — No real connection string or credential in any tracked file. `.env` is gitignored (confirmed via `git check-ignore`). `.env.example` contains only the localhost placeholder. VERIFIED by grep + git check-ignore.

## 3. QA results

**DB0 — full suite run:**
```
command: unset MONGO_URI && .venv/bin/python -m pytest tests/ -q --tb=short
result:  754 passed, 1 skipped, 246 warnings in 32.94s
```
Pass. The pre-existing 754/1 baseline is preserved.

**DB1 — no real credentials in tracked files:**
```
command: grep -rn "mongodb+srv|password|secret|AKIA|Bearer " .env.example docker-compose.yml
result:  NO_CREDENTIALS
```
Pass.

**DB1 — .env gitignored:**
```
command: git check-ignore -v .env
result:  .gitignore:28:.env	.env
```
Pass.

**docker-compose.yml YAML validity:**
```
command: docker compose config --quiet
result:  (exit 0, no warnings after removing the obsolete version key)
```
Pass.

## 4. Decisions made

- Placed `pymongo==4.17.0` immediately after `mongomock==4.1.2` in the core block (logically grouped as the two Mongo drivers; the Phase-3 block is kept separate with its comment header).
- Removed the `version: "3.9"` key from `docker-compose.yml` — Docker Compose v2 deprecates it and `docker compose config` emitted a warning. The file is fully valid without it and the warning is gone.
- `.env.example` uses plain `=` assignment (no `export`) so it can be sourced directly or read by dotenv libraries.

## 5. DECISION-NEEDED

None.

## 6. Deviations

- Removed `version: "3.9"` from `docker-compose.yml`. The brief did not specify whether to include it; it is obsolete in Compose v2 and caused a warning from `docker compose config`. Removing it produces a clean parse. This is a cosmetic infra decision, not a contract change.

## 7. Blockers / risks

None. `pymongo==4.17.0` was pre-installed and verified by the PM; the pin matches the actual `.venv` install. The test suite remains fully green. No app code was modified so no existing behavior is affected.

## 8. Next recommended action

Proceed to **Stage D1** — implement `db.py` (the lazy `get_mongo_client()` / `get_database()` connection layer with `mongomock` fallback when `MONGO_URI` is unset), covering QA checks `DB2`–`DB3`.
