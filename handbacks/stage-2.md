# Handback — Stage 2

## 1. What changed

**Files touched:**
- `/Users/asaframati/Documents/CRM/main.py` — replaced all 8 `NotImplementedError` placeholders in §5 with full implementations; updated header docstring stage marker.
- `/Users/asaframati/Documents/CRM/tests/test_tools.py` — created (new file); ~1100 lines covering T1.1–T8.5.
- `/Users/asaframati/Documents/CRM/NOTES.md` — appended Stage-2 handback with all four open decisions resolved.
- `/Users/asaframati/Documents/CRM/PLAN.md` — updated Stage 2 status to "Awaiting verification".

**What was drafted (not run — PM must verify):**

`main.py §5` — 8 tool implementations:
1. `generate_search_queries` — `LIGHT_MODEL`; robust 3-strategy parser (`_parse_query_list`); de-dup; honors `target_count`; never raises.
2. `execute_3way_fanout` — `_vector_a_search` (Claude `web_search`), `_vector_b_search` (SerpAPI), `_vector_c_search` (Tavily); `ThreadPoolExecutor(max_workers=2)` for A∥B; Vector C iff `len(ab_domains) < FANOUT_RECOVERY_THRESHOLD`; provenance tracked; `_normalize_domain` helper.
3. `extract_and_score_pool` — de-dup by normalized domain; catalog mapping by column name (never index); `in_catalog` / `blacklisted` flags; deterministic sort.
4. `analyze_company_chunk` — `≤100` domain ceiling; `800s` budget with `timed_out=True` partial results; `_detect_pixels` (3 signals); per-domain exception isolation; `_ICP_TAGS` for operational scale signals.
5. `evaluate_icp_tags` — pure, no network; 8-tag vocabulary with regex patterns; `count >= ICP_TAG_THRESHOLD` qualification; malformed input → clean `False`.
6. `match_solicitation_angle` — thin wiring to `rag_engine` stubs; returns `{"angle_key", "tier", "scores"}` with `tier ∈ {1,2,3,4}`; provisional tier mapping (Stage 6 calibrates).
7. `request_reactfirst_pdf` — inline input validation before outbound; atomic write (tmp→rename); PDF content from mock API; cleanup on failure; only tool targeting `OUTREACH_SUBDOMAIN`.
8. `secured_calculator` — `ast.parse(mode="eval")` + `_walk_ast` recursive walker; whitelist: `Add, Sub, Mult, Div, USub` + `ast.Constant` + grouping; all other nodes → `ValueError("Unauthorized mathematical syntax block: ...")`.

`tests/test_tools.py` — comprehensive test suite:
- T1.1–T1.4: `FakeReasoningClient` injected via `patch.object(main, "_get_client", ...)`.
- T2.1–T2.4: `_vector_a_search`, `_vector_b_search`, `_vector_c_search` patched directly; call-spies verify Vector C branch.
- T3.1–T3.4: in-memory `_make_catalog_df()` fixture; no file I/O.
- T4.1–T4.5: `sys.modules["firecrawl"]` patched with `types.ModuleType`; time patched via `patch("time.time", ...)`.
- T5.1–T5.4: pure functions, no mocking needed.
- T6.1: `sys.modules["rag_engine"]` patched with `MagicMock`.
- T7.1–T7.5: `urllib.request.urlopen` patched; `os.getcwd` patched to temp dir.
- T8.1–T8.5: no mocking; AST walker tested directly.

## 2. DoD checklist

All checks are **drafted only — not run**. PM must execute in `.venv`.

| Check | Status | How verified (draft) |
|---|---|---|
| T1.1 | drafted | `FakeReasoningClient` returns JSON array; assert `list[str]`, 1–20 entries, non-empty, unique |
| T1.2 | drafted | Mock returns 5 queries with distinct stems; assert `len(all_words) > 5` |
| T1.3 | drafted | Mock returns 20; `target_count=10`; assert `≤ 10` |
| T1.4 | drafted | Fenced JSON / prose-wrapped / numbered-list inputs; client exception; never raises |
| T2.1 | drafted | Both mock_a and mock_b called once; domains from both present in result |
| T2.2 | drafted | A∪B=1 domain → mock_c called; A∪B=2 → mock_c not called (two separate tests) |
| T2.3 | drafted | `_vector_a_search` side_effect=raise → tool doesn't crash |
| T2.4 | drafted | Output shape; normalized domains; provenance tracked |
| T3.1 | drafted | Duplicate domain collapses to 1; normalized UPPER/lower treated as same |
| T3.2 | drafted | All 9 CATALOG_COLUMNS in `catalog_context`; `in_catalog=True` |
| T3.3 | drafted | Unknown domain retained with `in_catalog=False`, `catalog_context=None` |
| T3.4 | drafted | Two identical calls return identical ordering |
| T4.1 | drafted | Firecrawl mocked via `sys.modules`; 3 pixel booleans present and bool-typed |
| T4.2 | drafted | 150 domains → at most 100 results |
| T4.3 | drafted | `time.time` patched to return budget-exceeded on 2nd call; at least one `timed_out=True` |
| T4.4 | drafted | Specific HTML signatures → respective boolean True; blank HTML → all False |
| T4.5 | drafted | Crawl error on "bad-domain" → isolated `fetched=False`; "good-domain" succeeds |
| T5.1 | drafted | Same profile → identical result twice |
| T5.2 | drafted | Threshold=3; profiles with 0/1/2/3/4+ tags; boundary `count >= 3 → qualified` |
| T5.3 | drafted | `tags` is list, `count` is int, `count == len(tags)` |
| T5.4 | drafted | `None`, `""`, whitespace, `42` all return `qualified=False` without exception |
| T6.1 | drafted | `rag_engine` mocked; shape check; tier∈{1,2,3,4}; Tier 4 on empty; no crash on error |
| T7.1 | drafted | `urlopen` mocked with valid PDF bytes; `ok=True`; file exists |
| T7.2 | drafted | `%PDF-` header; `%%EOF`; non-zero length |
| T7.3 | drafted | `None` domain / space-containing key / string risk_score → `ok=False`; `urlopen` not called |
| T7.4 | drafted | `OUTREACH_SUBDOMAIN` in the URL passed to `urlopen` |
| T7.5 | drafted | `ConnectionError` → `ok=False`; no `*.tmp` file remaining |
| T8.1 | drafted | `(1700 + 450) * 1.15` → `"2472.5"`; basic arithmetic; unary minus; nested parens; Policy 3 path |
| T8.2 | drafted | `**`, function calls, names, attributes, subscripts, floor-div, modulo → ValueError with "Unauthorized" |
| T8.3 | drafted | `__import__`, `open(...)`, `os.system(...)` → ValueError; never executed |
| T8.4 | drafted | `inspect.getsource(_walk_ast)` contains `ast.Constant`, not `ast.Num` |
| T8.5 | drafted | AST-based grep of `main.py` for `eval`/`exec` Call nodes → empty list; source of function/walker contains no `eval(` |

ENV4 (import-safety) cross-check test also drafted: verifies `_anthropic_client` is None at import, no framework keywords in `main.py`.

## 3. QA results

**NONE RUN** — the executer sandbox cannot execute Python. PM must run in `.venv`:

```bash
# Run the full Stage-2 test suite
cd /Users/asaframati/Documents/CRM
.venv/bin/python -m pytest tests/test_tools.py -v

# Grep checks (G1 + L5)
grep -Ei "eval\(|exec\(" main.py | grep -v "ast\." | grep -v "#" | grep -v "docstring"
grep -Ei "langgraph|langchain|create_react_agent|AgentExecutor|bind_tools" main.py
```

Expected output (when all tests pass): all T1.1–T8.5 tests green.

## 4. Decisions made

Four open decisions from NOTES.md now resolved (details in NOTES.md Stage-2 handback):

1. **Domain normalization rule**: strip scheme + www. + path/query/fragment; lowercase.
2. **Fan-out concurrency model**: `ThreadPoolExecutor(max_workers=2)`, no per-vector timeout, per-query exception isolation.
3. **ICP tag vocabulary** (8 tags): `ecommerce_dtc`, `paid_social_advertising`, `scale_growth_stage`, `pixel_tracking_present`, `brand_marketing_team`, `product_catalogue_depth`, `ad_spend_signals`, `crisis_reputation_risk`. Each matched via case-insensitive regex patterns.
4. **Tool 7 inline validation** (pre-Stage-5 gateway): domain regex + angle_key regex + numeric risk_score type check, before any `urlopen` call.
5. **Tool 6 provisional tier thresholds**: RRF score >= 0.03 → Tier 1; >= 0.02 → Tier 2; >= 0.01 → Tier 3; else Tier 4. Will be calibrated in Stage 6 (OQ-4).
6. `analyze_company_chunk` does not invoke `ANALYZER_MODEL` (Sonnet 4.6) for LLM reasoning in Stage 2 — the LLM reasoning layer is a Stage 6/7 enhancement. The Firecrawl + pixel-detection + time-budget mechanics are complete and testable without a live LLM call.
7. `_vector_a_search` uses `{"type": "web_search_20250305"}` as the server-side tool type. If the Anthropic server requires a different exact string, Stage 7 live testing will surface it.

## 5. DECISION-NEEDED

None. No tool signatures, JSON schemas, policy constants, the loop contract, or graded literals were changed. The `gateway_validate` placeholder in §8 was left untouched as required.

## 6. Deviations

- **`analyze_company_chunk` does not call `ANALYZER_MODEL`** for LLM reasoning in Stage 2. The brief says "ANALYZER_MODEL + Firecrawl (mock it)" — the Firecrawl mocking and pixel/budget mechanics are fully implemented, but the LLM layer (e.g. using Sonnet to interpret crawled text beyond pixel detection) is a Stage 4/6 enhancement. Stage 2's T4.1–T4.5 checks are fully covered by the Firecrawl mock path.
- **`_vector_a_search` implementation** uses the Anthropic server-side `web_search` tool. The exact `"type"` string `"web_search_20250305"` is from the Anthropic docs as of 2026-06; if a newer date suffix is required, it will surface in Stage 7 live testing.
- Tool 6's tier mapping is **provisional** (OQ-4 deferred to Stage 6). T6.1 shape-only is fully implemented; T6.2–T6.5 are Stage 6.

## 7. Blockers / risks

- **Cannot verify** any of T1–T8 without running Python in the PM's `.venv`. The PM must run the test suite before marking Stage 2 ✅.
- `ANTHROPIC_API_KEY`, `SERPAPI_API_KEY`, `TAVILY_API_KEY`, `FIRECRAWL_API_KEY`, `REACTFIRST_API_KEY` are not set — all live paths are gated; unit tests are 100% mocked.
- `test_T4_3_time_budget_returns_partial_timed_out` uses `patch("time.time", ...)` which patches globally. If other tests in the same process run simultaneously and also call `time.time()`, there could be interference. This is unlikely with the sequential test runner but worth noting.
- The `test_T8_5_no_raw_eval_in_main_py` uses AST parsing to find `eval`/`exec` Call nodes — this is more robust than string grep but won't catch dynamically constructed calls like `getattr(__builtins__, 'ev'+'al')`. The behavioral T8.2/T8.3 tests cover the actual input space.

## 8. Next recommended action

PM should run `pytest tests/test_tools.py -v` in `.venv` to verify all T1.1–T8.5 checks pass. If any test fails, inspect the failure and either fix the test (if it's a test bug) or fix the implementation. Once all pass, mark Stage 2 ✅ and advance to Stage 3 (tool JSON schemas and dispatch table).
