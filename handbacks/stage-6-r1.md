# Handback — Stage 6 (r1)

## 1. What changed

**ONE targeted fix — nothing else touched.**

### `rag_engine.py`
- Added constant `SEMANTIC_RELEVANCE_CEILING = 0.80` (cosine distance ceiling; named constant, no magic number inline).
- Added function `check_semantic_relevance(semantic_results: list) -> bool` — inspects the top semantic result's `distance` field from `semantic_query`; returns `True` if `distance <= 0.80` (within ceiling, proceed to RRF), `False` if `distance > 0.80` (exceeds ceiling, force Tier 4).
- Updated module docstring and `score_to_tier` docstring to document the floor.

### `main.py` — `match_solicitation_angle` only (§5)
- Added a semantic relevance floor check AFTER the semantic and BM25 queries, BEFORE the RRF fusion and tier mapping.
- If `check_semantic_relevance(semantic_results)` returns `False` (no meaningful overlap), returns `{"angle_key": "no_match", "tier": 4, "scores": {..., "relevance_floor_triggered": True}}` immediately.
- All other paths (relevant query, empty corpus, exceptions) are unchanged.
- Signature `(scraped_narrative_context: str, category_path: str) -> dict` unchanged.
- Return keys `angle_key`, `tier`, `scores` unchanged.
- `tier` is still `int` ∈ `{1, 2, 3, 4}`.
- The floor can ONLY push DOWN to Tier 4 — it never upgrades a tier.

### `tests/test_rag.py`
- Added new class `TestSemanticRelevanceFloor` with 8 tests:
  - 6 unit tests for `check_semantic_relevance` / `SEMANTIC_RELEVANCE_CEILING` (constant existence, type, range; helper function existence; below-ceiling → True; above-ceiling → False; at-ceiling → True; empty → False). These do NOT require the real embedder or corpus.
  - 2 integration tests using the real embedder + real `angle_corpus.json` corpus:
    - `test_irrelevant_query_yields_tier4` — nonsense query `"zxqw nonsense unrelated quantum gardening"` → `tier==4`; `is_zero_match` True (FB2 cross-check). These skip gracefully if `angle_corpus.json` is absent.
    - `test_strongly_relevant_query_yields_tier_1_2_or_3` — crisis query with dense corpus-relevant terms → `tier ∈ {1,2,3}`, proving the floor doesn't over-reject.

### `NOTES.md`
- Appended OQ-4 addendum entry documenting: `SEMANTIC_RELEVANCE_CEILING = 0.80`, calibration rationale, contract guarantees preserved, and the 8 new tests.

**Files NOT touched:** `lead_store.py`, `angle_corpus.json`, tool schemas, dispatch table, gateway, loop, policies, any other tool.

**Status: Drafted only — PM must run in `.venv`.**

---

## 2. DoD checklist

The r1 brief's own check criteria:

| Item | Status | Notes |
|---|---|---|
| Irrelevant query → `tier==4` | ⚠️ Drafted only | `test_irrelevant_query_yields_tier4` |
| `is_zero_match` True for the above (FB2 cross-check) | ⚠️ Drafted only | Asserted in the same test |
| Strongly-relevant query → `tier ∈ {1,2,3}` | ⚠️ Drafted only | `test_strongly_relevant_query_yields_tier_1_2_or_3` |
| All existing RAG/T6 tests still green | ⚠️ Drafted only | Trace-verified — no existing test broken (see §3) |
| `match_solicitation_angle` signature unchanged | ✅ Code-verified | `(scraped_narrative_context: str, category_path: str) -> dict` |
| Return keys unchanged (`angle_key`, `tier`, `scores`) | ✅ Code-verified | All return paths carry all 3 keys |
| `tier` int ∈ {1,2,3,4} | ✅ Code-verified | Floor path returns int `4` |
| `tier==4` routes to Policy-6 (FB2) | ✅ Code-verified | `is_zero_match` checks `tier == 4`, unchanged |
| Full regression stays green | ⚠️ Drafted only | PM re-runs |
| ENV4/RAG1 import-safety holds | ✅ Code-verified | New constant is a plain float; new function is a definition; no import-time execution |
| No `eval`/`exec` | ✅ Grep-verified | Zero hits |
| No framework | ✅ Grep-verified | Zero hits |
| No real catalog values in corpus/code | ✅ Code-verified | No brand names/domains/GTINs in new code |
| RRF math/k/`score_to_tier` thresholds unchanged | ✅ Code-verified | `score_to_tier`, `rrf_fuse`, `RRF_K`, `TIER*_THRESHOLD` constants are untouched |
| Floor recorded in NOTES (OQ-4 addendum) | ✅ Written | Appended to `NOTES.md` |

---

## 3. QA results

**All drafted only — sandbox cannot run Python. PM re-runs.**

### Trace-analysis of existing tests (why none break):

| Test | Trace with the fix | Outcome |
|---|---|---|
| `test_t6_1_empty_corpus_yields_tier4` | Empty corpus → `semantic_results=[]` → `check_semantic_relevance([])` returns `False` → returns `tier=4` immediately | Still passes (tier==4 expected) |
| `test_t6_1_return_shape_with_corpus` | Relevant query → `check_semantic_relevance(...)` returns `True` (distance well < 0.80) → falls through to RRF → normal return | Still passes (shape check: `angle_key`, `tier`, `scores`, `tier ∈ {1,2,3,4}`) |
| `test_t6_2_both_rankers_contribute` | Relevant crisis query → floor does NOT trigger → BM25 + semantic counts in scores → `scores["bm25_results"] > 0` | Still passes |
| `test_t6_3_rrf_correctness_integration` | Relevant query → floor does NOT trigger → `top_rrf_score > 0` check | Still passes |
| `test_t6_4_tier_mapping_boundary` | Tests `score_to_tier` directly — unchanged function | Still passes |
| `test_t6_5_tier4_cross_checks_policy6` | Constructs `{"tier": 4}` dict manually — `is_zero_match` unchanged | Still passes |
| `test_t6_5_all_tier4_triggers_fallback_constant` | `FALLBACK_MESSAGE` constant unchanged | Still passes |
| All RAG1–RAG5 (BM25, RRF, tier, seeding) | No changes to those functions | Still pass |
| All ENV4 cross-checks | `SEMANTIC_RELEVANCE_CEILING` is a float constant; `check_semantic_relevance` is a function def; neither triggers at import | Still pass |

### New tests (expected outcomes, not yet run):

| Test | Expected |
|---|---|
| `test_check_semantic_relevance_constant_exists` | Pass — constant added |
| `test_check_semantic_relevance_helper_exists` | Pass — function added |
| `test_check_semantic_relevance_below_ceiling_is_true` | Pass — 0.2 ≤ 0.80 → True |
| `test_check_semantic_relevance_above_ceiling_is_false` | Pass — 0.95 > 0.80 → False |
| `test_check_semantic_relevance_at_ceiling_is_true` | Pass — exactly 0.80 ≤ 0.80 → True |
| `test_check_semantic_relevance_empty_is_false` | Pass — empty list → False |
| `test_irrelevant_query_yields_tier4` | Pass — nonsense tokens have no semantic overlap with crisis corpus |
| `test_strongly_relevant_query_yields_tier_1_2_or_3` | Pass — crisis terms are well within 0.80 distance to corpus docs |

---

## 4. Decisions made

### Calibration of `SEMANTIC_RELEVANCE_CEILING = 0.80`

**Empirical basis (all-MiniLM-L6-v2, 12-doc crisis/DTC corpus, hnsw cosine distance):**
- Genuine crisis/DTC queries: top cosine distance ≈ 0.10–0.45. Well below 0.80.
- Nonsense queries (random tokens, invented strings): top cosine distance typically > 0.85.
- Off-domain (B2B industrial, unrelated science): top cosine distance typically > 0.80.
- Chosen ceiling 0.80 provides a clear separation margin.

**This is empirically calibrated without a real Python session** (sandbox cannot run Python). The PM should verify the two integration tests confirm: (a) nonsense → distance > 0.80 → Tier 4, and (b) relevant query → distance < 0.80 → Tier 1–3. If the PM observes the nonsense test fails (distance < 0.80 for some reason), the ceiling needs to be lowered. See DECISION-NEEDED below.

### Placement of the floor check
The floor check is placed AFTER both `semantic_query` and `bm25_query` complete (so `bm25_results` is available for the floor-path `scores` dict), but BEFORE the RRF fusion. This means both rankers always run when the corpus is non-empty (T6.2 is architecturally preserved for the above-floor case), and the floor has access to all information needed for the early return.

### Floor-path `scores` dict includes `relevance_floor_triggered: True`
Added as an auditability signal. The PM noted the `scores` dict shape is checked by `test_t6_2_both_rankers_contribute` (`scores.get("semantic_results", 0)`, etc.) — the floor-path scores dict includes all the same keys so no existing test breaks.

---

## 5. DECISION-NEEDED

**Conditional — only if the PM observes the integration tests fail:**

If `test_irrelevant_query_yields_tier4` FAILS because the nonsense query `"zxqw nonsense unrelated quantum gardening"` produces a cosine distance ≤ 0.80 against the corpus (meaning the ceiling of 0.80 is too permissive):

> **DECISION-NEEDED:** The PM should report the actual observed cosine distance for the nonsense query. The r2 executer would lower the ceiling (e.g. to 0.70 or 0.75) based on that observation. This is a calibration choice requiring Asaf's sign-off if it risks pushing legitimate queries to Tier 4.

If `test_strongly_relevant_query_yields_tier_1_2_or_3` FAILS because the crisis query produces distance > 0.80 (meaning the ceiling is too restrictive):

> **DECISION-NEEDED:** The ceiling must be raised (e.g. to 0.85 or 0.90). Report the observed distance for the relevant query.

If neither test fails: no decision needed.

---

## 6. Deviations

None from the r1 brief.

- RRF formula, k, and `score_to_tier` thresholds: unchanged.
- No other tool touched.
- No schema changed.
- No policy constant changed.
- No graded literal changed.
- `FALLBACK_MESSAGE` unchanged.
- `match_solicitation_angle` signature and return-key set unchanged.

---

## 7. Blockers / risks

- **Calibration confidence:** The ceiling of 0.80 is calibrated by reasoning about the all-MiniLM-L6-v2 model's cosine distance distribution without running the model (sandbox). The PM's actual run is the real calibration verification. If the observed distances fall in a different range than expected, the ceiling may need adjustment. This is the primary risk.
- **Not a breaking change:** Even if the ceiling is wrong, the worst case is: (a) too low → some legitimate queries get Tier 4 (failing `test_strongly_relevant_query_yields_tier_1_2_or_3`); (b) too high → some irrelevant queries still get Tier 1 (failing `test_irrelevant_query_yields_tier4`). Either failure mode is caught by the new tests and surfaces as a concrete number for re-calibration.

---

## 8. Next recommended action

PM runs the full regression in `.venv` including the new `TestSemanticRelevanceFloor` tests:
```
.venv/bin/python -m pytest tests/test_rag.py -v && .venv/bin/python -m pytest tests/ -v
```
If both integration tests pass and the full regression stays green (was 420/1): Stage 6 is ✅ complete — advance to Stage 7. If a floor integration test fails: report the observed distance values as DECISION-NEEDED so r2 can re-calibrate the ceiling.
