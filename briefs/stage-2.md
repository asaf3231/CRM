# Brief — Stage 2: Tool layer (the 8 tools)
Read first: CLAUDE.md → PLAN.md → QA_checklist.md → NOTES.md, then this brief.

Goal: Implement the 8 tool functions in `main.py` §5 to their exact contracts, test-first,
each verified in isolation with **mocked** services. No live LLM/network/crawl in unit tests.

## Context you must know (do not relitigate — these are settled)
- **Stage 1 is ✅ closed and verified** (43/43 QA pass). `main.py` §3 Configuration + §4 Catalog
  loader, `lead_store.py` (Policy 4 gate), `rag_engine.py` (lazy Chroma scaffold + `bm25_query`/
  `rrf_fuse` **stubs**) all exist and are import-safe. Build on them; do not rewrite them.
- The 8 tool functions already exist in `main.py` §5 as `NotImplementedError` **placeholders with
  their signatures**. KEEP those exact signatures — they are the contract (schemas in Stage 3 must
  match). Signatures:
  `generate_search_queries(vertical_seed, target_count=DEFAULT_QUERY_COUNT)`,
  `execute_3way_fanout(queries)`, `extract_and_score_pool(raw_pool, catalog_df)`,
  `analyze_company_chunk(domains)`, `evaluate_icp_tags(company_profile_data)`,
  `match_solicitation_angle(scraped_narrative_context, category_path)`,
  `request_reactfirst_pdf(target_domain, validated_angle_key, calculated_risk_score)`,
  `secured_calculator(expression)`.
- **LLM provider is Claude** via the `anthropic` SDK, used through the existing lazy `_get_client()`.
  Models: tool 1 + tool 3 → `LIGHT_MODEL`; tool 4 → `ANALYZER_MODEL`. Use the Anthropic Messages API
  shape (`client.messages.create(...)`). Do NOT construct the client at import; only inside the tool.
- `ANTHROPIC_API_KEY` is NOT set on this machine. Therefore **every** LLM-touching test MUST inject a
  fake client (monkeypatch `main._get_client` to return a `FakeReasoningClient`, or pass a client in) —
  a test that reaches the real client will `KeyError` on the env var. That is your forcing function:
  zero live calls.
- The three input fixtures are the source of truth; never hardcode their brand/domain/key values.

## Scope (do ONLY this stage)
Implement the 8 tool bodies in `main.py` §5 + write `tests/test_tools.py`. Each tool per CLAUDE.md §6:

1. **generate_search_queries** — `LIGHT_MODEL`; returns `list[str]`, 10–20 entries, a *variation
   matrix* (distinct intent/modifier axes, not N copies of the seed), unique after de-dup, honors
   `target_count`. Robust parse: model output wrapped in prose/fences/JSON still yields a clean list
   or a clean error — never an uncaught exception. (`T1.1`–`T1.4`)
2. **execute_3way_fanout** — Vectors A (Claude `web_search`/`web_fetch`) ∥ B (SerpAPI+Maps) run
   **concurrently** via `concurrent.futures`. Vector C (Tavily) fires **iff** `A∪B` yields
   `< FANOUT_RECOVERY_THRESHOLD (=2)` distinct domains — assert BOTH branches with a call-spy.
   Per-vector failure isolation (one vector raising ≠ whole tool down). Output: dict of pooled,
   **normalized** domains (lowercase, strip scheme/`www`) + per-domain provenance + per-vector status.
   Record your domain-normalization rule and concurrency model (pool size, per-vector timeout) in
   NOTES.md. (`T2.1`–`T2.4`; skip the live `T2.5`.)
3. **extract_and_score_pool(raw_pool, catalog_df)** — de-dup by normalized `Primary_Domain`; annotate
   catalog matches with the 9-column context **by name**; retain non-catalog candidates flagged
   `in_catalog=False`; deterministic ordering, no hidden randomness. May use `LIGHT_MODEL` for scoring
   but keep the de-dup/mapping deterministic and testable without a live call. (`T3.1`–`T3.4`)
4. **analyze_company_chunk(domains)** — `ANALYZER_MODEL` + Firecrawl (mock it). Hard ceilings:
   process **≤100** domains/chunk (excess deferred, documented); respect the **800s** wall-clock budget
   and return **partial** results flagged `timed_out=True` rather than raising (test this with a mocked
   slow clock — do NOT actually sleep 800s); per-domain crawl failure isolated to that domain's record
   (`{"error":...}`). Emit explicit booleans `tiktok_pixel` / `meta_pixel` / **`gtm`** (Google Tag
   Manager) using the signatures in NOTES.md (detect over raw HTML). (`T4.1`–`T4.5`)
5. **evaluate_icp_tags(company_profile_data: str)** — PURE, no network; deterministic for a fixed
   profile **string**; `qualified == True` **iff** matched-tag count `>= ICP_TAG_THRESHOLD (=3)`
   (test at 2→fail, 3→pass, 4→pass); returns the matched tag list + integer count; malformed/empty →
   `qualified=False` with a clean reason, never an exception. Decide and record the concrete ICP tag
   vocabulary in NOTES.md (NOTES flags this as a Stage-2 decision). (`T5.1`–`T5.4`)
6. **match_solicitation_angle(scraped_narrative_context, category_path)** — Stage 2 = thin wiring to
   `rag_engine` returning `{"angle_key","tier","scores"}` with `tier ∈ {1,2,3,4}`. The full hybrid
   Chroma+BM25→RRF→tier math is **Stage 6** — leave `rag_engine.bm25_query`/`rrf_fuse` as the existing
   stubs; just prove the shape and the call path here. Do NOT finalize `k`/tier thresholds (that is OQ-4,
   a Stage-6 decision). (`T6.1` shape only; `T6.2`–`T6.5` are Stage 6.)
7. **request_reactfirst_pdf(target_domain, validated_angle_key, calculated_risk_score)** — mock the
   ReactFirst API; save a **health-valid** PDF (`%PDF-` header, non-zero length, `%%EOF` marker) under
   `assets/` (build the path with `os.path`/`pathlib`); return `{"path","ok":True}`. Reject a
   null domain / malformed `angle_key` / non-numeric risk score **before** any outbound call with
   **minimal inline input validation** (the consolidated single `gateway_validate` chokepoint is wired
   in **Stage 5** — do not build it now; leave its placeholder). This is the ONLY tool that targets
   `OUTREACH_SUBDOMAIN`. API failure → `{"ok":False,"error":...}`, no partial/corrupt file left, no
   raise. (`T7.1`–`T7.5`)
8. **secured_calculator(expression)** — AST isolated walk: `ast.parse(expr, mode="eval")` + recursive
   `_walk` over a whitelist of **exactly** `Add, Sub, Mult, Div, USub` + numeric `ast.Constant` +
   parenthesized grouping. Any other node (`**`/Pow, calls, names, attributes, subscripts,
   comprehensions, lambdas) → `ValueError("Unauthorized mathematical syntax block: ...")`. Use
   `ast.Constant` (not `ast.Num`). **No raw `eval`/`exec` anywhere** (grep-clean). SOP smoke:
   `secured_calculator("(1700 + 450) * 1.15")` → correct value as a `str`. (`T8.1`–`T8.5`)

## QA checks to PASS (run, not inspect)
`T1.1`–`T1.4`, `T2.1`–`T2.4`, `T3.1`–`T3.4`, `T4.1`–`T4.5`, `T5.1`–`T5.4`, `T6.1` (shape only),
`T7.1`–`T7.5`, `T8.1`–`T8.5`. Use the §0 fixtures pattern (`tmp_catalog_csv`, `FakeReasoningClient`,
`MockSerp`/`MockTavily`/`MockFirecrawl`/`MockReactFirst`). All tests under `tests/test_tools.py`.
**Note:** the executer sandbox cannot run Python — write the tests, state clearly that they are
*drafted only / not run*; the PM runs and verifies them in `.venv`.

## Constraints (from CLAUDE.md that bite this stage)
- Import-safety still holds: clients/models/Chroma stay lazy; nothing new runs at import (ENV4 must
  still pass after your changes).
- No raw `eval`/`exec`; no framework imports anywhere (grep clean) — even though the loop is Stage 4.
- Catalog access by NAME never index; no catalog/sample values hardcoded in code or prompts.
- OS-agnostic paths only (`os.path`/`pathlib`); `assets/` built relative to cwd.
- Tools fail LOUDLY-as-data: a vector/crawler/API error becomes a structured `{"error":...}` result,
  never an uncaught exception (the loop in Stage 4 depends on this).
- Do NOT touch schemas/dispatch (Stage 3), the agentic loop (Stage 4), or the gateway/policy helpers
  (Stage 5). Leave their placeholders intact.

## Inputs / files you may touch
Create/edit: `main.py` §5 (the 8 tool bodies only), `tests/test_tools.py`. You MAY add small private
helpers in `main.py` §5 and read `rag_engine.py`'s public API. Do NOT edit `lead_store.py`, the §3/§4
config/loader, or the Stage-3/4/5 placeholder sections.

## Do NOT
Advance past Stage 2. Change a tool signature / JSON schema / policy constant / the loop contract /
a graded literal (`FALLBACK_MESSAGE`) — if one seems necessary, STOP and surface it as
**DECISION-NEEDED** in your handback (the PM turns it into a halt). Record routine Stage-2 design
choices (domain normalization, concurrency model, ICP tag vocabulary, pixel-signature confirmations)
in NOTES.md — those are yours to decide, not halts.

## Deliver
Write `handbacks/stage-2.md` in the standard handback format (CLAUDE.md §12 / PLAN.md). Separate
*drafted only* from *written and test-verified* (everything here is drafted-only — PM verifies).
List every `T*` check you wrote a test for. Return the handback as your final message.
