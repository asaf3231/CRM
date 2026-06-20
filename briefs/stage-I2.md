# Brief — Stage I2: Leads + ICP endpoints + adapters + seed (Phase 3 — Integration Layer)
Read first: CLAUDE.md → PLAN.md (Phase 3 section) → QA_checklist.md §11 (`INTG4`–`INTG6`) → NOTES.md (2026-06-19 Phase 3 entry), then this brief. Full approved plan: `~/.claude/plans/sprightly-tinkering-hennessy.md`.

Goal: Add the deterministic offline seed, the pure snake_case→camelCase adapters (with the LOCKED thresholds), and the 5 leads/ICP routes that serve the React frontend over HTTP — all offline, no API keys, graded backend untouched.

Context: Stage I1 already landed `api_server.py` (FastAPI `app`, `/api/health`, a no-op `lifespan`, localhost CORS) + `tests/conftest.py` (singleton reset) + `tests/test_api.py`. This stage adds `api_seed.py` + `api_adapters.py`, wires `seed_demo()` into the lifespan, and adds the leads/ICP routes. The API only READS the backend (`crm_store`); `main.py` is NOT edited and NOT imported at module top-level of `api_server.py`.

## Scope (do ONLY this stage)

### 1. Create `api_seed.py` (repo root)
- `SEED_ICP: dict` — the seed ICP document dict with EXACTLY these keys (matches `build_icp_document` output shape):
  `{"vertical": str, "want_signals": list[str], "avoid_signals": list[str], "geo": str, "size_band": str, "icp_tags": list[str], "anchor_companies": list[dict]}`.
  Each `anchor_companies` item: `{"name": str, "domain": str, "why": str}`. Keep it generic crisis-narrative / DTC brand-safety themed (NO real `brands_catalog.csv` values — anti-leakage G2). e.g. vertical "Athleisure", want_signals like "high ad spend", "active social presence", "DTC", geo "North America", size_band "Mid-Market". Provide ~5 anchor companies with INVENTED names/domains (not catalog brands).
- `seed_demo() -> None` — upserts ~16 deterministic example lead records into `crm_store` via `crm_store.upsert_lead`. Import `crm_store` INSIDE the function (lazy), never at module top-level (so `import api_seed` stays side-effect-free).
  - Each seed record MUST carry the base CRM keys plus the extra catalog-derived fields the adapter needs:
    `{"uniq_id": str, "domain": str, "company": str (display name), "status": "qualified", "stage": <LifecycleStage>, "win_prob": float (0..1), "profile": {"icp_tags": list[str]}, "icp_count": int, "historical_social_incidents": int, "current_status": <one of "Active_Client"|"Open_Opportunity"|"Unreached_Prospect">, "contact_ids": list[str]}`.
    NOTE: `contact_ids` may be non-empty (emails) — the adapter MUST strip it (INTG5). Do NOT put any `corporate_access_key` anywhere.
    Do NOT seed any `Blacklisted` record (those are filtered pre-adapter — the seed simply never creates one).
  - Make the ~16 records DETERMINISTIC (fixed list, no randomness, no timestamps in the values you control — `upsert_lead` adds `updated_at` itself; the adapter must NOT emit `updated_at`).
  - Spread the records across GovBand / FitGrade / LeadKind buckets so the funnel + filters have variety (some `current_status="Active_Client"` → Existing, rest → New; mix `historical_social_incidents` across 0 / 1–2 / ≥3; mix `icp_count` across ≤1 / 2–3 / ≥4).
  - Idempotent: calling `seed_demo()` twice yields the same 16 records (upsert keyed on `uniq_id`), never 32.
- `SEED_STATS: dict` (or a `build_seed_stats()` function) — the `LeadDiscoveryStats` source numbers, self-consistent with the FE funnel. Keep them internally consistent: `goal ≥ discovered`, `discovered - filteredByIcp = retained`, `retained - belowFloor = aboveFloor`, `newCount + existingCount = retained`, `strong + review + weak = retained`. (These are run-level funnel totals — they do NOT have to equal the 16 seeded pool rows; the pool tabs and the funnel are different views, per the FE NOTES.)

### 2. Create `api_adapters.py` (repo root) — PURE functions, no I/O, fully unit-testable, no backend imports at module top-level
Module constants for the LOCKED thresholds (named, not magic inline):
- **GovBand** from `historical_social_incidents`: `>= 3 → "Heavy Gov"`, `1` or `2` → `"Light Gov"`, `0 → "No Gov"`.
- **FitGrade** from `icp_count`: `>= 4 → "Strong"`, `2` or `3` → `"Medium"`, `<= 1 → "Weak"`.
- **LeadKind** from `current_status`: `"Active_Client" → "Existing"`, else `"New"`.

Functions:
- `gov_band(incidents: int) -> str`
- `fit_grade(icp_count: int) -> str`
- `lead_kind(current_status: str) -> str`
- `crm_lead_to_ui(record: dict) -> dict` returning a `Lead` (camelCase) with EXACTLY these keys:
  `{"id": record["uniq_id"], "company": record["company"], "domain": record["domain"], "score": round(record["win_prob"]*100), "fit": fit_grade(record["icp_count"]), "gov": gov_band(record["historical_social_incidents"]), "kind": lead_kind(record["current_status"]), "stage": record["stage"], "tags": record["profile"]["icp_tags"], "winProb": record["win_prob"]}`.
  - **MUST strip `contact_ids`** — it must NOT appear in the output (INTG5).
  - **MUST NEVER emit `corporate_access_key`** at any depth (INTG5 / G4).
  - Use safe `.get()` with sensible defaults so a record missing an optional key does not crash (e.g. `tags` defaults to `[]`, `score` to 0).
- `icp_doc_to_ui(seed: dict) -> dict` returning an `IcpDocument` (camelCase):
  `id="icp-v1"`, `title=seed["vertical"]`, `description=f"DTC brands in the {seed['vertical']} space, {seed['geo']}, {seed['size_band']} segment"`, `source="Companies"`, `keywords=seed["want_signals"]`, `industryVerticals=[seed["vertical"]]`, `geographicFocus=[seed["geo"]]`, `qualificationCriteria` = (each want_signal → `{"criterion": s, "importance": "High"}`) + (each avoid_signal → `{"criterion": "Avoid: "+s, "importance": "Low"}`), `anchorCompanies=seed["anchor_companies"]` (pass-through list of `{name,domain,why}`).
- `stats_to_ui(stats: dict) -> dict` returning a `LeadDiscoveryStats` (camelCase): map the seed stats keys to the FE field names exactly (`goal, discovered, filteredByIcp, retained, belowFloor, aboveFloor, newCount, existingCount, alreadyInCrm, strong, review, weak, strictness`). Keep all keys present.

### 3. Add routes to `api_server.py`
Import `crm_store`, `api_seed`, `api_adapters` LAZILY inside the handlers (or near the top of the function), NEVER at module top-level (preserves INTG1 import-safety).
- `GET /api/leads` → `list[Lead]`: read `crm_store.all_leads()`, filter OUT any record whose `current_status == "Blacklisted"` (pre-adapter), map each via `crm_lead_to_ui`. Deterministic order (sort by `uniq_id` or keep seed order).
- `GET /api/leads/stats` → `LeadDiscoveryStats`: `api_adapters.stats_to_ui(api_seed.SEED_STATS)`.
- `POST /api/leads/find-more` — request body model `{"existing_domains": list[str], "target": int}`. Return a deduped `list[Lead]`: from the seed pool, exclude any lead whose `domain` (lowercased) is in the lowercased `existing_domains` set; return up to `target` of the remaining, mapped via `crm_lead_to_ui`. (Offline/deterministic — it just returns un-seen seed pool rows; no live discovery.) Use a Pydantic model for the body.
- `GET /api/icp` → `IcpDocument`: `api_adapters.icp_doc_to_ui(api_seed.SEED_ICP)`.
- `GET /api/icp/suggestions` → `list[str]`: `api_seed.SEED_ICP["want_signals"]`.

### 4. Wire the seed into the lifespan
- In `api_server.py`'s `lifespan`, replace the `# I2: call api_seed.seed_demo() here` no-op with a lazy `import api_seed; api_seed.seed_demo()` call on startup (inside the `lifespan` body, BEFORE the `yield`). This MUST keep `import api_server` side-effect-free — the seed fires only on ASGI startup (lifespan), never at import. Do NOT call `seed_demo()` at module scope.

### 5. Extend `tests/test_api.py` with INTG4–INTG6 checks (mark QA IDs in comments)
- Use `fastapi.testclient.TestClient(api_server.app)` **as a context manager** (`with TestClient(api_server.app) as client:`) so the lifespan (and thus `seed_demo()`) actually runs for the endpoint tests. (A plain `TestClient(...)` without the `with` does NOT trigger lifespan — the leads list would be empty.)
- `INTG4`: `GET /api/leads` → 200, a non-empty list; each item has the camelCase Lead keys; `GET /api/leads/stats` → 200 with all `LeadDiscoveryStats` keys; `POST /api/leads/find-more` with `{"existing_domains":[<one seeded domain>],"target":5}` → 200, a list excluding that domain, length ≤ 5.
- `INTG5` (adapter unit tests, no server needed): assert `gov_band`/`fit_grade`/`lead_kind` at every boundary (incidents 0→No, 1→Light, 2→Light, 3→Heavy; icp_count 1→Weak, 2→Medium, 3→Medium, 4→Strong; status Active_Client→Existing, Unreached_Prospect→New). Assert `crm_lead_to_ui` on a record WITH a non-empty `contact_ids` and a stray `corporate_access_key` key → output has NO `contact_ids` and NO `corporate_access_key`, and `score == round(win_prob*100)`. Add a recursive/string-search assert that the JSON of EVERY `/api/leads` response item contains neither the substring `contact_ids` nor `corporate_access_key`.
- `INTG6`: `GET /api/icp` → 200, an `IcpDocument` with all keys; `title == SEED_ICP["vertical"]`; `qualificationCriteria` length == len(want_signals)+len(avoid_signals); `source == "Companies"`. `GET /api/icp/suggestions` → 200, == `SEED_ICP["want_signals"]`. (Assert the route does NOT import or call `build_icp_document` — ICP comes from the seed dict.)
- Add an import-safety regression: `import api_seed` and `import api_adapters` from an empty dir, no key, do NOT initialize `crm_store._leads_collection` (extend the existing INTG1-style in-process check, or add a subprocess probe).

## Constraints (from CLAUDE.md)
- **Import-safety / ENV4 is graded.** `import api_server`, `import api_seed`, `import api_adapters` must ALL be side-effect-free (no `crm_store`/`lead_store`/`main` work, no file reads, no network at import). The seed fires ONLY in the lifespan. `import main, lead_store, rag_engine, crm_store` must still be clean. `main.py` must NOT be edited and must NOT import `api_server`/`api_seed`/`api_adapters`.
- **No catalog literals (G2).** Use invented brand names/domains in the seed — NO value from the real `brands_catalog.csv`.
- **No secrets (G4).** No `corporate_access_key` value anywhere in the seed, the adapters, or any response.
- No raw `eval`/`exec`. OS-agnostic paths. camelCase out (the FE `api.ts` does `r.json()` only — all conversion is in `api_adapters.py`).
- The 4 FE-mock methods (`getReachSeries`, `getAgentEvents`, `runDiscovery`, `getSwarmStages`) get NO backend route here.

## Inputs / files you may touch
CREATE `api_seed.py`, `api_adapters.py`. EDIT `api_server.py` (add routes + wire lifespan seed). EDIT `tests/test_api.py` (add INTG4–INTG6 tests). Do NOT touch `main.py`, `crm_store.py`, `lead_store.py`, `rag_engine.py`, `tests/conftest.py`, or `frontend/`.

Reference shapes (already on disk — read them, do not change them):
- `crm_store.all_leads()` returns `list[dict]` of records (no mongo `_id`); record shape at `crm_store.py:104–117`; `upsert_lead` at `crm_store.py:124`.
- FE TypeScript contract: `frontend/src/types/index.ts` (`Lead`, `LeadDiscoveryStats`, `IcpDocument`).

## Do NOT
Add the outreach endpoints (Stage I3); add the 4 FE-mock routes; do live `build_icp_document`/`answer_question` calls; advance past this stage; change a tool signature / schema / policy constant / the loop contract / a graded literal — surface those as DECISION-NEEDED.

## NOTE on verification
Your sandbox cannot run pytest — the PM runs it. Write the code + tests; in your handback, quote the exact files/functions created and state clearly what you wrote vs verified. If a check fails when the PM runs it and you are re-briefed, use the `systematic-debugging` skill.

Deliver: write `handbacks/stage-I2.md` in the standard format; return it as your final message.
