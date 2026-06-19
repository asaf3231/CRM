# Brief — Stage 9 (retry r1): fix 1 real defect + 3 test bugs
Read first: CLAUDE.md → PLAN.md → QA_checklist.md → NOTES.md → briefs/stage-9.md (original), then this.

Stage-9 attempt 1 is **95% correct** (27/30 new tests pass; INT2/INT3/H3/H4/H5 + most of INT1 are
good — do NOT redo them). PM diagnosed the 3 failures. Apply exactly these 4 fixes.

## Fix 1 — REAL CODE DEFECT: `extract_and_score_pool` emits non-JSON-serializable numpy `int64`
`main.py` §5 `extract_and_score_pool` builds each candidate's `catalog_context` from the catalog row;
`Historical_Social_Incidents` comes through as **`numpy.int64`** (the loader coerces via `.astype(int)`).
The agentic loop serializes every tool result with **`json.dumps(raw_result)`** (~lines 2525/2546/2553),
so a real discovery run with a **catalog-matched** candidate raises
`TypeError: Object of type int64 is not JSON serializable` (RS5 catches it, but the run fails).

**Fix:** make `extract_and_score_pool`'s return value JSON-clean — coerce numpy scalars to native Python
types when building `catalog_context` (e.g. `int(row["Historical_Social_Incidents"])`, and `float(...)`
for any float; or a small `_to_native(v)` helper using `v.item()` for numpy scalars applied to every
catalog field). Keep the signature, return-key set, and all existing T3 behavior unchanged — only the
value *types* become native. **Add a regression test** (in `tests/test_tools.py` or
`tests/test_integration.py`): for a candidate whose domain matches the real/synthetic catalog,
`json.dumps(extract_and_score_pool(raw_pool, catalog_df))` succeeds (no `TypeError`).

## Fix 2 — TEST BUG: INT1b/INT1e count a docstring mention as an egress reference
`tests/test_integration.py::TestINT1SubdomainRouting::test_int1b_only_tool7_references_subdomain_in_main`
flags `gateway_validate` because its **docstring** contains the literal "outreach.reactfirst.ai".
`gateway_validate` has **zero** `OUTREACH_SUBDOMAIN` references and makes no network call — it is not an
egress. The real egress is `request_reactfirst_pdf` referencing the `OUTREACH_SUBDOMAIN` **Name**.

**Fix:** in the `SubdomainFinder`, **count only `ast.Name` references to `OUTREACH_SUBDOMAIN`** (the
egress mechanism) — drop the `visit_Constant` string-literal matching (docstring/comment mentions of the
host are not egress; hardcoded host literals are already banned by G2/G3). After the fix, the only
referencing function is `request_reactfirst_pdf`. Keep the assertion that `request_reactfirst_pdf` IS in
the set. (INT1e: the `json.dumps(result3)` line will pass once Fix 1 lands; if you prefer, also make that
assertion use `str(result3)` for robustness.)

## Fix 3 — TEST BUG: H1 mis-handles a local module + the serpapi→google-search-results mapping
`tests/test_integration.py::TestH1PinnedDependencies::test_h1_third_party_imports_are_pinned` flags
`serpapi` and `rag_engine`:
- `rag_engine` is a **local first-party module** (like `main`/`lead_store`) — exclude it from the
  third-party set (add to the local-modules exclusion alongside `main`, `lead_store`, `rag_engine`).
- `serpapi` is the import name **provided by the pinned `google-search-results==2.4.2`** — the test's
  `variants` dict has a **duplicate key** (`"google_search_results"` twice) that drops the
  `serpapi`→`google_search_results` mapping. Fix the mapping so `serpapi` resolves to
  `google-search-results` (and `firecrawl`→`firecrawl-py`, `tavily`→`tavily-python` if needed).

  All 8 real third-party imports ARE pinned (PM-verified): anthropic, chromadb, sentence-transformers,
  mongomock, pandas, firecrawl-py, google-search-results (serpapi), tavily-python.

## Must stay true after the fixes (PM re-runs everything)
- Full regression green: **488 → all pass** (461 prior + the Stage-9 tests), 1 skipped (S10), 0 failed.
- INT1 single-egress, INT2 interop+auth-gate, INT3 idempotent, H1/H3/H4/H5 all pass.
- `extract_and_score_pool` signature/return-keys unchanged; T3 tests still green; ENV4 holds; no
  eval/framework; no secret/catalog leak.

## Do NOT
Change any tool signature / schema / policy constant / loop contract / graded literal. Fix 1 changes
only value *types* (int64→int), not the contract. If a "fix" seems to require a contract change, STOP
and surface DECISION-NEEDED.

## Deliver
Update `handbacks/stage-9.md` (or write `handbacks/stage-9-r1.md`) listing the 4 fixes; mark *drafted
only* (PM re-runs). Return it as your final message.
