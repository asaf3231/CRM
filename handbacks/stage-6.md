# Handback — Stage 6

## 1. What changed

### Files written + verified (drafted only — PM runs in .venv)

**`/Users/asaframati/Documents/CRM/rag_engine.py`** — Complete rewrite filling in the Stage-1 stubs:
- Added module-level constants: `RRF_K = 60`, `TIER1_THRESHOLD = 0.025`, `TIER2_THRESHOLD = 0.015`, `TIER3_THRESHOLD = 0.005`, `_BM25_K1 = 1.5`, `_BM25_B = 0.75`, `_CORPUS_FILENAME`.
- Added BM25 helpers (pure Python, no external deps): `_tokenize()`, `_compute_idf()`, `_bm25_score()`.
- Replaced `bm25_query()` stub with real BM25 implementation (independent of Chroma — RAG3). Returns `[{"id","document","score"}, ...]` sorted descending. Zero-score docs excluded. Validates parallel list lengths.
- Replaced `rrf_fuse()` stub with real RRF: `RRF(d) = Σ 1/(k+rank_r(d))`, k=60, rank 1-based, deterministic tie-break by lexicographic id. Returns `[{"id","rrf_score","semantic_rank","bm25_rank"}, ...]`.
- Added `score_to_tier(rrf_score: float) -> int` — maps fused top score to tier 1/2/3/4 per OQ-4 thresholds.
- Added `seed_corpus_if_empty()` — lazy, idempotent corpus seeder. Reads `angle_corpus.json` from cwd, upserts into Chroma on first use. Idempotent: session-flag + `collection.count()` guard prevent double-insert.
- Updated `semantic_query()` — guards against empty collection (returns [] to avoid ChromaDB error); clamps `n_results` to `collection.count()`.

**`/Users/asaframati/Documents/CRM/main.py`** — Section 5, `match_solicitation_angle` only:
- Replaced thin Stage-2 stub with full hybrid pipeline: seed corpus → semantic_query → BM25 over full corpus → rrf_fuse(k=60) → score_to_tier → return `{"angle_key","tier","scores"}`.
- Signature unchanged: `(scraped_narrative_context: str, category_path: str) -> dict`.
- Return keys unchanged: `{"angle_key","tier","scores"}`, `tier` is int ∈ {1,2,3,4}.
- `tier==4` still routes to Policy-6 fallback via `is_zero_match` (FB2 preserved).
- Both rankers always contribute when corpus is non-empty (T6.2 guaranteed architecturally).

**`/Users/asaframati/Documents/CRM/angle_corpus.json`** — New internal RAG asset (NOT one of the 3 bounded runtime inputs):
- 12 synthetic crisis-case-study entries.
- Generic DTC/paid-social/brand-reputation narratives. No real catalog brand names/domains/GTINs (CAT5/G2 clean).
- Covers all 4 tiers across the corpus.
- Lazily seeded by `seed_corpus_if_empty()` on first call to `match_solicitation_angle`.

**`/Users/asaframati/Documents/CRM/tests/test_rag.py`** — New test file, 50 tests:
- `TestRAG1LazyStore` (4 tests): import-safety, first-use build, singleton, persist-dir creation.
- `TestRAG2EmbeddingModel` (5 tests): EMBED_MODEL constant, not loaded at import, 384-dim vectors, multiple-text, singleton.
- `TestRAG3BM25` (10 tests): list return, ranking relevance, shape, empty-corpus, empty-query, unknown-terms, n_results, Chroma-independence, descending order, mismatched-lengths.
- `TestRAG4RRFFusion` (8 tests): hand-computed 2-ranker example, rank ordering, deterministic tie-break, single-semantic-only, single-bm25-only, empty-both, semantic/bm25_rank fields, k-parameter effect, default-k=60.
- `TestRAG5TierClassification` (8 tests): Tier 1/2/3/4 score ranges, exact boundary values, Tier-4→Policy-6 via is_zero_match, Tier-1→not-zero-match, threshold constants.
- `TestT6MatchSolicitationAngle` (8 tests): return shape (empty corpus), Tier-4 on empty corpus, return shape with corpus, both rankers contribute, RRF max-score bound, tier boundary values, Tier-4 → is_zero_match, FALLBACK_MESSAGE constant.
- `TestCorpusSeeding` (4 tests): not-seeded-at-import, missing-file-no-crash, idempotent (2-call count stays 2), flag set.
- `TestEnv4CrossCheck` (2 tests): rag_engine side-effect-free import, all-3-modules side-effect-free.

**`/Users/asaframati/Documents/CRM/NOTES.md`** — OQ-4 entry updated (RESOLVED), Stage-6 handback appended.

**`/Users/asaframati/Documents/CRM/PLAN.md`** — Stage 6 status updated to 🟡 Awaiting verification.

## 2. DoD checklist

| Check ID | Status | How verified |
|---|---|---|
| `RAG1` | ⚠️ drafted only | `TestRAG1LazyStore` (4 tests): import sets no singletons; first-use builds; singleton identity; .chroma dir created |
| `RAG2` | ⚠️ drafted only | `TestRAG2EmbeddingModel` (5 tests): EMBED_MODEL=="all-MiniLM-L6-v2"; 384-dim vectors; not loaded at import |
| `RAG3` | ⚠️ drafted only | `TestRAG3BM25` (10 tests): pure in-memory, Chroma-independent (singleton stays None), ranked descending, correct result shape |
| `RAG4` | ⚠️ drafted only | `TestRAG4RRFFusion::test_rrf_hand_computed_two_rankers`: hand-computed Σ 1/(60+rank) for 3-doc/2-ranker example; tie-break verified; PM hand-verifies arithmetic |
| `RAG5` | ⚠️ drafted only | `TestRAG5TierClassification` (8 tests): all 4 tier boundaries; Tier-4 → is_zero_match=True cross-check; threshold constants |
| `T6.1` | ⚠️ drafted only | `test_t6_1_*`: shape `{"angle_key","tier","scores"}`; tier ∈ {1,2,3,4}; empty corpus → tier=4 |
| `T6.2` | ⚠️ drafted only | `test_t6_2_both_rankers_contribute`: scores.semantic_results > 0 AND scores.bm25_results > 0 when corpus non-empty |
| `T6.3` | ⚠️ drafted only | `test_t6_3_rrf_correctness_integration`: top_rrf_score > 0 and ≤ 2/61 (max possible) for strongly-matched query |
| `T6.4` | ⚠️ drafted only | `test_t6_4_tier_mapping_boundary`: score_to_tier at 7 boundary values |
| `T6.5` | ⚠️ drafted only | `test_t6_5_tier4_cross_checks_policy6` + `test_t6_5_all_tier4_triggers_fallback_constant`: is_zero_match True on Tier-4; FALLBACK_MESSAGE byte-exact |

All checks are **drafted only**. PM must run in `.venv` to verify.

## 3. QA results

**None — sandbox cannot run Python.** All checks listed above are drafted code + drafted tests. PM verifies:

```bash
# Run Stage 6 checks only:
.venv/bin/pytest tests/test_rag.py -v

# Full regression (must still pass 370 + new tests):
.venv/bin/pytest tests/ -v

# ENV4 cross-check (import from empty dir):
python -c "import main, lead_store, rag_engine; print('ok')"

# Hand-verify RAG4 arithmetic (k=60, 3 docs, 2 rankers):
# doc_A: sem=rank1, bm25=rank2 → 1/61 + 1/62 = 0.032522...
# doc_B: sem=rank2, bm25=rank1 → 1/62 + 1/61 = 0.032522...
# doc_C: sem=rank3, bm25=rank3 → 1/63 + 1/63 = 0.031746...
# tie-break: doc_A < doc_B lexicographically → doc_A first

# Anti-leakage (no real catalog values, no eval/exec, no framework):
grep -rn "eval(\|exec(" main.py rag_engine.py tests/test_rag.py
grep -rn "northwind\|Crater Cola\|Access99" rag_engine.py tests/test_rag.py angle_corpus.json
```

## 4. Decisions made

1. **OQ-4 RESOLVED — k=60, tier thresholds calibrated:**
   - k = 60 (standard RRF default, unchanged from provisional)
   - Tier 1 (Critical Fit): fused score >= 0.025
   - Tier 2 (Strong Fit): fused score >= 0.015
   - Tier 3 (Watchlist / Speculative): fused score >= 0.005
   - Tier 4 (No Match): fused score < 0.005
   - Calibration: 2 rankers, k=60 → max 2/61≈0.0328; Tier-1 at 0.025 requires both rankers to contribute meaningfully; Tier-2 at 0.015 captures strong single-ranker; Tier-3 at 0.005 captures weak overlap; Tier-4 below 0.005 is noise-floor.

2. **BM25 is pure Python (no rank-bm25 library):** avoids adding an unpinned dependency. Uses standard BM25 formula with k1=1.5, b=0.75.

3. **BM25 operates over the full Chroma corpus** (fetched via `collection.get()`): guarantees T6.2 (both rankers always see the same document set when corpus is non-empty).

4. **`score_to_tier()` is a public standalone function** (not nested) so RAG5 boundary tests can call it directly without running match_solicitation_angle end-to-end.

5. **`_corpus_seeded` flag + `collection.count()` guard**: `_corpus_seeded` prevents re-seeding within a Python session (fast); `collection.count() > 0` prevents re-seeding across sessions (persistent Chroma). Both checks together make seeding idempotent.

6. **Angle corpus (angle_corpus.json):** 12 synthetic entries, generic language (no catalog brand names/domains/GTINs). Covers all 4 tiers. Provenance recorded in NOTES.md.

7. **Tie-breaking:** lexicographically smaller `id` comes first when RRF scores are equal. Documented in module docstring and NOTES.md.

8. **`semantic_query()` guards against empty collection:** returns [] instead of raising a ChromaDB error when `collection.count() == 0`. Also clamps `n_results` to `collection.count()` to prevent ChromaDB's n_results > actual count error.

## 5. DECISION-NEEDED

None. All decisions were within the brief's scope ("author a small synthetic corpus + calibrate k=60 defaults"). OQ-4 resolved per the brief's instruction.

## 6. Deviations

None from the brief. Signature and return-key set of `match_solicitation_angle` unchanged. `tier` remains int ∈ {1,2,3,4}. `tier==4` routes to Policy-6 via `is_zero_match` (FB2 preserved). No other tool touched. No schema, policy constant, loop contract, or graded literal changed.

## 7. Blockers / risks

1. **ChromaDB n_results guard:** if ChromaDB 0.5.5 raises when `n_results > collection.count()`, the added `actual_n = min(n_results, collection.count())` guard in `semantic_query()` prevents this. PM should verify this edge case is handled.

2. **Tier thresholds may need recalibration** against the full 12-entry corpus + all-MiniLM-L6-v2 embeddings. Thresholds were derived analytically (2 rankers, k=60 math); real scores may cluster differently. PM's loading of the real embedder (RAG2 verification) will reveal the actual score distribution. If most queries fall in Tier 4 with a 12-doc corpus, thresholds should be lowered. This is a calibration decision, not a contract change.

3. **`collection.get(limit=...)` compatibility:** confirmed against ChromaDB 0.5.5 source (Collection.get accepts `limit` parameter). Should work correctly.

4. **Test isolation:** `TestT6MatchSolicitationAngle.reset_and_chroma` fixture uses `_reset_rag_engine()` + monkeypatch to ensure each test gets a fresh, isolated rag_engine. `match_solicitation_angle` does `import rag_engine` internally which correctly picks up the monkeypatched module from `sys.modules`. This pattern is consistent with the existing test suite.

## 8. Next recommended action

PM runs `tests/test_rag.py` in `.venv` (including loading all-MiniLM-L6-v2 to confirm RAG2 384-dim, and hand-verifying the RAG4 RRF arithmetic). If the full regression (370 + 50 new) passes clean, mark Stage 6 ✅ and proceed to Stage 7 (End-to-end single-vertical run, `E1`–`E4`).
