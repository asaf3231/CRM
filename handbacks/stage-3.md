# Handback — Stage 3

## 1. What changed

**Files touched:**
- `/Users/asaframati/Documents/CRM/main.py` — §6 (`TOOL_SCHEMAS`) and §7 (`TOOL_DISPATCH` + import-time assert) **written** (replaced placeholders).
- `/Users/asaframati/Documents/CRM/tests/test_schemas.py` — **written** (new file, ~640 lines).
- `/Users/asaframati/Documents/CRM/NOTES.md` — Stage-3 handback entry appended, including the Stage-4 `catalog_df` injection requirement.
- `/Users/asaframati/Documents/CRM/handbacks/stage-3.md` — this file.

**What was done:**

`main.py §6` — 8 Anthropic-shaped schemas in `TOOL_SCHEMAS`:
- Each is `{"name", "description", "input_schema": {"type":"object","properties":{},"required":[]}}`. No OpenAI `{"type":"function",...}` wrapper.
- Schema 1 (`generate_search_queries`): `vertical_seed` (string, required); `target_count` (integer, optional — has Python default 15, NOT in required).
- Schema 2 (`execute_3way_fanout`): `queries` (array of string, required). Description states the Vector C rule verbatim: "fewer than 2 distinct domains".
- Schema 3 (`extract_and_score_pool`): exposes only `raw_pool` (array, required). `catalog_df` is NOT in properties or required — it is runtime-injected. Description states catalog mapping happens internally.
- Schema 4 (`analyze_company_chunk`): `domains` (array of string, required). Description states CHUNK_MAX_DOMAINS=100, CHUNK_TIME_BUDGET_S=800, all three pixel booleans (tiktok_pixel, meta_pixel, gtm), partial results on timeout.
- Schema 5 (`evaluate_icp_tags`): `company_profile_data` (string, required). Description states ">= 3" ICP tag threshold verbatim; mentions Trust-Gated path for exactly 3.
- Schema 6 (`match_solicitation_angle`): `scraped_narrative_context` and `category_path` (both string, both required). Description states Tier 1–4 range; Tier 4 → Policy 6 fallback; MAX_ANGLES=3 ceiling; category_path must come from catalog.
- Schema 7 (`request_reactfirst_pdf`): `target_domain` (string), `validated_angle_key` (string), `calculated_risk_score` (number — not integer). All required. Description states ONLY outbound tool; NEVER Tier 4; MAX_ANGLES=3 ceiling.
- Schema 8 (`secured_calculator`): `expression` (string, required). Description states "NO eval/exec"; whitelist `+ - * /` + parentheses; forbids `**` (power) and function calls; includes SOP smoke `(1700 + 450) * 1.15`; Policy 3 premium pricing context.

`main.py §7` — `TOOL_DISPATCH` dict (8 entries) + import-time three-way assert:
- Asserts `len(TOOL_SCHEMAS) == 8`, `len(TOOL_DISPATCH) == 8`, schema names == dispatch keys, and each schema name resolves to the module-level function of the same name.
- Assert uses only already-defined Python dicts/function objects — ENV4-safe (no network, no file I/O, no heavy object construction).
- Temporary names used in the assert block (`_schema_names`, `_dispatch_names`, `_this_module`, `_s`, `_fn`) are deleted with `del` to keep the module namespace clean.

`tests/test_schemas.py` — structured as:
- `TestS0` — 9 tests covering exactly 8 schemas; three-way name identity; import-time assert passes; no OpenAI wrapper; all have Anthropic keys; input_schema.type == "object"; non-empty properties; required is a list; required fields exist in properties.
- `TestS1` through `TestS8` — per-tool schema tests (name, required fields, property types, key description contents per S9).
- `TestS9` — cross-schema description quality tests (all descriptions ≥50 chars, all state "use this tool", tool-specific key constraint checks).
- `TestS10` — live API smoke, gated with `@pytest.mark.skipif(not os.environ.get("ANTHROPIC_API_KEY"), ...)`.

**Not touched:** §5 tool bodies, §3/§4 config/loader, §8/§9/§10/§11 placeholders, `lead_store.py`, `rag_engine.py`.

---

## 2. DoD checklist

| QA ID | Status | How verified |
|---|---|---|
| `S0` | ⚠️ Drafted only — PM must run | `TestS0` (9 tests): exactly 8 schemas; schema names == function names == dispatch keys; import-time assert covers three-way identity; no OpenAI wrapper |
| `S1` | ⚠️ Drafted only — PM must run | `TestS1`: name, required (vertical_seed only), target_count is integer but not required, descriptions steer discovery use |
| `S2` | ⚠️ Drafted only — PM must run | `TestS2`: name, queries array of string required, description states Vector C < 2 rule and parallel execution |
| `S3` | ⚠️ Drafted only — PM must run | `TestS3`: name, only raw_pool in required, catalog_df absent from schema, description states internal catalog mapping |
| `S4` | ⚠️ Drafted only — PM must run | `TestS4`: name, domains array of string required, description states 100-domain ceiling, 800s budget, 3 pixels, partial timeout |
| `S5` | ⚠️ Drafted only — PM must run | `TestS5`: name, company_profile_data string required, description states ">= 3" threshold, pure/deterministic, trust-gate |
| `S6` | ⚠️ Drafted only — PM must run | `TestS6`: name, both params string+required, description states Tier 1–4 + Tier 4 fallback + MAX_ANGLES=3 + catalog for category_path |
| `S7` | ⚠️ Drafted only — PM must run | `TestS7`: name, all 3 params required, calculated_risk_score is `number` (not integer), description states ONLY outbound + NEVER Tier 4 + MAX_ANGLES=3 |
| `S8` | ⚠️ Drafted only — PM must run | `TestS8`: name, expression string required, description states NO eval, operator whitelist, Policy 3 premium pricing, SOP smoke `(1700+450)*1.15`, `**` forbidden |
| `S9` | ⚠️ Drafted only — PM must run | `TestS9`: cross-schema description quality (≥50 chars, "use this tool", tool-specific key constraints); per-tool tests in `TestS1`–`TestS8` also cover S9 |
| `S10` | SKIPPED (gated) | `TestS10.test_schemas_accepted_by_anthropic_api` is guarded by `@pytest.mark.skipif(not os.environ.get("ANTHROPIC_API_KEY"), ...)` — no `ANTHROPIC_API_KEY` set; not failed |

---

## 3. QA results

**Cannot run Python in this sandbox.** All checks are drafted only.

The PM must run:
```
cd /Users/asaframati/Documents/CRM
.venv/bin/python -m pytest tests/test_schemas.py -v
```

Expected:
- `S0`–`S9` tests: **pass** (the schemas, dispatch, and assert are consistent with what the tests check).
- `S10`: **SKIPPED** with reason "ANTHROPIC_API_KEY not set; SKIPPED (not failed)".
- `ENV4` re-verification: `import main, lead_store, rag_engine` from an empty tmp dir should still exit 0 — the assert is over pre-defined dicts/functions, no side effects.

---

## 4. Decisions made

1. **`target_count` is `integer` and not in `required`.** Python function has `target_count: int = 15`. Schema correctly types it as `integer` and omits it from `required` so the model can omit it and the default applies.

2. **`calculated_risk_score` is `number` (not `integer`).** The Policy 3 calculation `base * 1.15` produces a float. JSON Schema `number` covers both int and float; `integer` would be incorrect.

3. **`raw_pool` items typed as `object` in Schema 3.** The raw pool consists of dicts with `domain` and `provenance` fields. Typed as `array` of `object` rather than trying to specify the nested schema — appropriate since the Anthropic loop will produce this from tool output.

4. **Assert block cleanup.** The temporary vars created by the assert (`_schema_names`, `_dispatch_names`, `_this_module`, `_s`, `_fn`) are deleted with `del` at the end of the §7 block to keep the module namespace clean. The assert uses `sys.modules[__name__]` via the already-imported top-level `sys` from §2 — no extra import.

5. **Stage 4 `catalog_df` injection requirement (for NOTES.md / Stage-4 executer):** When the agentic loop dispatches `extract_and_score_pool`, the model-supplied `tool_input` dict will contain only `raw_pool`. The Stage-4 loop must inject `catalog_df` before calling the function: `TOOL_DISPATCH["extract_and_score_pool"](**{**tool_input, "catalog_df": catalog_df})` where `catalog_df` comes from `answer_question`'s parameter. This is NOT a schema change — the schema correctly exposes only `raw_pool`.

---

## 5. DECISION-NEEDED

None. No tool signature changes, no loop contract changes, no policy constant changes, no graded literal changes were needed. The `catalog_df` wrinkle is handled as specified in the brief (schema-only exposing `raw_pool`; Stage 4 injects at dispatch time).

---

## 6. Deviations

None from the brief. All 8 schemas implemented exactly as specified. `S10` is marked SKIPPED (not failed) as required. The assert block uses `sys.modules[__name__]` via the top-level `import sys` already present in §2 — no redundant re-import needed.

---

## 7. Blockers / risks

- **Cannot run Python in this sandbox.** All checks are drafted only; PM must verify in `.venv`.
- The assert block uses `sys.modules[__name__]` via the already-imported top-level `sys` (§2). No redundant imports.
- `S10` remains gated on `ANTHROPIC_API_KEY` (OQ-7) — will stay SKIPPED until a key is provided.

---

## 8. Next recommended action

PM runs `tests/test_schemas.py` in `.venv`:

```
cd /Users/asaframati/Documents/CRM
.venv/bin/python -m pytest tests/test_schemas.py -v
```

If `S0`–`S9` pass and `S10` is SKIPPED (not failed), mark Stage 3 ✅ and advance to Stage 4 (agentic loop, `briefs/stage-4.md`). The Stage-4 executer must implement the `catalog_df` injection for `extract_and_score_pool` dispatch (see NOTES.md entry above).
