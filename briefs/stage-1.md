# Brief — Stage 1: Environment, data catalog & lazy local vector store
Read first: CLAUDE.md → PLAN.md → QA_checklist.md → NOTES.md, then this brief.

Goal: Stand up a clean, import-safe environment; load and validate the 9-column catalog;
build the local Chroma store lazily; scaffold the mongomock `lead_store.py` with the
Policy 4 auth gate — all before any agent/tool/loop code.

## Context you must know
- The three runtime input files **now exist** in the cwd as PM-authored synthetic fixtures:
  `brands_catalog.csv` (12 rows, header spells `Main_Competitor_Id`, one `Blacklisted` row),
  `contacts.json` (5 records; known key `Access99`; one `opt_out_status=true`),
  `gtm_policies.txt` (six policies). Treat these as the real source of truth. Do NOT
  regenerate, rewrite, or hardcode their values into code.
- `ANTHROPIC_API_KEY` is NOT set on this machine. `ENV3` live smoke must be SKIPPED
  (explicitly, not failed). All Stage 1 verification runs on mocks/local — no network.
- Python is 3.10.17.

## Scope (do ONLY this stage)
- Create `.venv` and `requirements.txt`. Pin the six mandatory deps from CLAUDE.md §1.1
  (`chromadb==0.5.5`, `sentence-transformers==3.0.1`, `mongomock==4.1.2`, `pandas==2.2.2`,
  plus `anthropic` and `firecrawl-py`) AND the non-LLM service clients
  (`google-search-results`, `tavily-python`). Resolve OQ-2 by pinning the latest
  known-good `==` version that installs cleanly for `anthropic`, `firecrawl-py`,
  `google-search-results`, `tavily-python`; record the exact resolved versions in NOTES.md.
- `main.py` §3 (Configuration) + §4 (Catalog loader) ONLY: the named constants from
  CLAUDE.md §9, `FALLBACK_MESSAGE`, `CATALOG_COLUMNS`, the lazy client/embedder/collection
  singletons (`_get_client`, `_get_embedder`, `_get_collection` — defined but NOT invoked
  at import), and a pandas catalog loader that validates the 9-column header on load,
  reads by name, coerces `Historical_Social_Incidents` to int, validates the tier/status
  enums, and surfaces (not swallows) malformed input. Do NOT write the 8 tools, schemas,
  dispatch, gateway, or the agentic loop — leave clearly-marked placeholders if helpful.
- `rag_engine.py`: lazy Chroma scaffold only — a `_get_collection()` that builds/persists
  under `.chroma/` on FIRST USE (gitignored), using `all-MiniLM-L6-v2`. No corpus indexing
  logic beyond what proves RAG1 (that's Stage 6). Import must be side-effect-free.
- `lead_store.py`: the PRD-exact lazy `get_lead_data_collection()` singleton (NOTES.md has
  it verbatim) + the Policy 4 auth gate as the SINGLE chokepoint to the contacts collection.
  Add a `.gitignore` covering `.venv/`, `.chroma/`, `assets/`, `__pycache__/`, and the three
  input fixture files.

## QA checks to PASS (run, not inspect)
`ENV1`, `ENV2`, `ENV4`, `CAT1`, `CAT2`, `CAT3`, `CAT4`, `CAT5`, `CAT6`, `RAG1`,
`AG1`, `AG2`, `AG3`, `AG4`, `AG5`, `AG6`. (`ENV3` = SKIP, no key — say so explicitly.)
Put tests under `tests/` (`tests/test_lead_store.py` + a catalog/import-safety test).
Use the QA_checklist §0 fixtures pattern (tmp_catalog_csv, tmp_contacts_json,
seeded_lead_store). `ENV4` is the gating check — prove `import main, lead_store, rag_engine`
does zero work (no client, no model download, no Chroma build, no
`get_lead_data_collection()`, no file read/write at import).

## Constraints (from CLAUDE.md that bite this stage)
- Import-safety is non-negotiable (§3.4): all heavy work lazy. ENV4 proves it.
- OS-agnostic paths only (`os.path`/`pathlib`); no absolute paths (§1, G3).
- Catalog by NAME never index (CAT2); no catalog values hardcoded in code/prompts (CAT5/G2).
- Auth gate: no-key and wrong-key denied IDENTICALLY (generic `{"error":"unauthorized"}`),
  zero record fields leaked, key value never in any return/log/error (AG1/AG2/AG5);
  `opt_out_status=true` suppressed (AG6); single chokepoint (AG6).
- No raw `eval`/`exec`; no framework imports anywhere (grep clean), even though tools come later.

## Inputs / files you may touch
Create/edit: `requirements.txt`, `main.py` (§3–§4 only), `rag_engine.py`, `lead_store.py`,
`.gitignore`, `tests/test_lead_store.py`, `tests/test_catalog.py` (or similar).
Read-only: the three input fixtures, CLAUDE.md, PLAN.md, QA_checklist.md, NOTES.md.
Do NOT touch the management `.md` files except NOTES.md (append the resolved dep versions +
embedding dimensionality + env facts + your handback).

## Do NOT
- Advance past Stage 1 (no tools/schemas/dispatch/gateway/loop logic).
- Change any tool signature, JSON schema, policy constant, the loop contract, or the
  `FALLBACK_MESSAGE` literal — surface any such need as **DECISION-NEEDED**.
- Regenerate or alter the three input fixtures, or hardcode their values into code.
- Make any live network/LLM/crawl call.

## Deliver
Write `handbacks/stage-1.md` in the standard handback format (CLAUDE.md §12): what changed,
DoD checklist (each QA ID ✅/⚠️, drafted-only vs written-and-test-verified separated),
QA results (which IDs you actually ran + pass/fail + the command output summary),
decisions made (record resolved pin versions + embedding dim in NOTES.md too), deviations,
blockers/risks, and one next recommended action. Return it as your final message.
