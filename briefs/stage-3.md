# Brief — Stage 3: Tool JSON schemas & dispatch
Read first: CLAUDE.md → PLAN.md → QA_checklist.md → NOTES.md, then this brief.

Goal: Write the 8 Anthropic-shaped tool schemas (`TOOL_SCHEMAS`, `main.py` §6) with
descriptions sharp enough to steer tool choice, plus the dispatch table (`TOOL_DISPATCH`,
§7) with an import-time three-way name check.

## Context you must know (settled — do not relitigate)
- **Stages 1 & 2 are ✅ PM-verified.** The 8 tool functions are implemented in `main.py` §5
  and pass `tests/test_tools.py` (122/122). §6 currently has `TOOL_SCHEMAS = []` and §7 has
  `TOOL_DISPATCH = {}` as placeholders — replace those.
- **Anthropic tool shape (NOT OpenAI):** each schema is exactly
  `{"name": ..., "description": ..., "input_schema": {"type": "object", "properties": {...},
  "required": [...]}}`. Do NOT use the OpenAI `{"type":"function","function":{...}}` wrapper.
- **Three-way name identity (S0):** `len(TOOL_SCHEMAS) == 8`; every schema `name` ==
  a tool function name == a `TOOL_DISPATCH` key. Guard it with an **import-time `assert`**
  in §7 (an `assert` over already-defined constants is import-safe — ENV4 must still pass).
- The exact tool function signatures (the contract — schemas must match the **model-facing**
  params, see the wrinkle below):
  `generate_search_queries(vertical_seed, target_count=15)`,
  `execute_3way_fanout(queries)`, `extract_and_score_pool(raw_pool, catalog_df)`,
  `analyze_company_chunk(domains)`, `evaluate_icp_tags(company_profile_data)`,
  `match_solicitation_angle(scraped_narrative_context, category_path)`,
  `request_reactfirst_pdf(target_domain, validated_angle_key, calculated_risk_score)`,
  `secured_calculator(expression)`.

## Wrinkle you must handle (NOT a contract change — do not halt on it)
`extract_and_score_pool` takes `catalog_df` (a pandas DataFrame). That is a **runtime-injected
context object**, never supplied by the model. Its schema must expose **only `raw_pool`** in
`properties`/`required`; document in the description that catalog mapping happens internally
against the loaded catalog. The loop (Stage 4) injects `catalog_df` at dispatch time — note
that requirement in NOTES.md for Stage 4. Do NOT add `catalog_df` to the schema and do NOT
change the function signature. (If you believe the signature itself must change, STOP and
surface DECISION-NEEDED instead.)

## Scope (do ONLY this stage)
- `main.py` §6: the 8 schemas, kept **adjacent/ordered** so they cannot drift from the funcs.
- `main.py` §7: `TOOL_DISPATCH = {name: fn, ...}` for all 8 + the import-time three-way assert.
- `tests/test_schemas.py`: S0–S9 (see below). S10 is a gated live `messages.create` smoke —
  mark it SKIPPED (no `ANTHROPIC_API_KEY`); do not fail it.
- Type each `properties` entry correctly (`string`/`integer`/`number`/`array` with `items`,
  etc.); `target_count` is an optional `integer` (NOT in `required`); `calculated_risk_score`
  is a `number`; `queries`/`domains` are `array` of `string`.
- Descriptions (S9) must state *when to use* the tool AND its key constraint, e.g.:
  tool 2 → "Vector C only fires if A∪B yields < 2 domains"; tool 5 → "qualifies iff ≥3 ICP
  tags"; tool 8 → "safe arithmetic only, no eval"; mention the ≤3 angle ceiling awareness
  where relevant (tool 6/7). No vague filler text.

## QA checks to PASS (run, not inspect — by the PM)
`S0` (8 schemas; three-way name identity; import-time assert), `S1`–`S8` (each schema
well-formed Anthropic shape; typed properties; correct `required`), `S9` (descriptions steer
choice + state the key constraint). `S10` = SKIP (gated live call, no key — say so explicitly).
Put tests in `tests/test_schemas.py`. **Your sandbox cannot run Python** — write the tests and
mark them *drafted only, not run*; the PM runs them in `.venv`.

## Constraints (from CLAUDE.md that bite this stage)
- Import-safety holds: §6/§7 define constants + one `assert` only; nothing heavy runs at import
  (ENV4 must still pass).
- No framework, no `eval`/`exec` (grep clean) — unchanged.
- Schema `name` strings must be byte-identical to the function names and dispatch keys.
- Do NOT touch the agentic loop (Stage 4), the gateway/policy helpers (Stage 5), or the tool
  bodies (Stage 2, done). Leave their placeholders intact.

## Inputs / files you may touch
Create/edit: `main.py` §6 (`TOOL_SCHEMAS`) + §7 (`TOOL_DISPATCH` + assert), `tests/test_schemas.py`.
Do NOT edit the §5 tool bodies, §3/§4 config/loader, `lead_store.py`, or `rag_engine.py`.

## Do NOT
Advance past Stage 3. Change a tool signature / the loop contract / a policy constant / a graded
literal. If a schema can't faithfully represent a tool without changing its signature, STOP and
surface **DECISION-NEEDED**.

## Deliver
Write `handbacks/stage-3.md` in the standard format; separate *drafted only* from *written and
test-verified* (all drafted-only — PM verifies). List every `S*` check covered. Return it as
your final message.
