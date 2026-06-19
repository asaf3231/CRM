# Brief — Stage 6: Hybrid RAG / RRF angle engine
Read first: CLAUDE.md (§6 tool 6) → PLAN.md → QA_checklist.md → NOTES.md (RRF tier section + OQ-4), then this brief.

Goal: Build the `rag_engine.py` Chroma + BM25 + RRF stack behind `match_solicitation_angle`, with
verifiable fusion math and tier mapping, and wire tool 6 to it. Resolve OQ-4 (k + tier thresholds).

## Context you must know (settled — do not relitigate)
- **Stages 1–5 are ✅ PM-verified.** Full-regression baseline: **370 passed, 1 skipped (S10)**.
- `rag_engine.py` already has the lazy scaffold (`_get_embedder`, `_get_collection`, `embed_texts`,
  `upsert_documents`, `semantic_query`) verified import-safe (RAG1). `bm25_query` and `rrf_fuse` are
  **stubs returning `[]`** — Stage 6 fills them in.
- `main.py` §5 `match_solicitation_angle(scraped_narrative_context, category_path)` is currently a
  **thin Stage-2 wiring** returning `{"angle_key","tier","scores"}`. Stage 6 wires it to the FULL
  hybrid pipeline. **Keep the signature and the return-key set unchanged** (the loop + `is_zero_match`
  read `tier`; `tier ∈ {1,2,3,4}` and `tier == 4` must keep routing to the Policy-6 fallback — FB2).
- **OQ-4 is resolved at THIS stage (not a halt)** — same pattern as OQ-2 at Stage 1. Default `k = 60`
  (standard RRF). You calibrate the four tier thresholds numerically against the corpus and **record
  k + the exact thresholds + Tier 2/3 labels in NOTES.md** before claiming RAG4/RAG5.
- **The crisis-case-study angle corpus is an INTERNAL RAG asset, NOT one of the 3 bounded runtime
  inputs** (`brands_catalog.csv`/`contacts.json`/`gtm_policies.txt`). You MAY author a small synthetic
  corpus (e.g. 6–12 entries: each a past crisis/PR narrative → an `angle_key` + tier-defining text).
  Keep it generic — NO real catalog brand names/domains/GTINs (CAT5/G2 stay clean). Record its
  provenance + contents summary in NOTES.

## Scope (do ONLY this stage) — `rag_engine.py` + `main.py` §5 tool 6 + `tests/test_rag.py`
- **`bm25_query(query_text, documents, doc_ids, n_results)` (RAG3)** — a real BM25 (or a clean,
  documented exact-term TF/IDF-style) ranker, **independent of** the semantic path; returns a ranked
  `[{"id","document","score"}, ...]`, highest first. Pure/in-memory (no Chroma). Document the formula
  + any params in NOTES.
- **`rrf_fuse(semantic_results, bm25_results, k=60)` (RAG4)** — Reciprocal Rank Fusion:
  `RRF(d) = Σ_rankers 1/(k + rank_r(d))`, **rank 1-based**. Returns a fused ranked list
  `[{"id","rrf_score", ...}, ...]` highest first; **deterministic tie-breaking** (document the tiebreak,
  e.g. by id). The k and the math must match a hand-computable example (the PM hand-verifies).
- **Tier mapping (RAG5)** — map the fused top result to **Tier 1 Critical Fit / Tier 2 / Tier 3 /
  Tier 4 No Match** per thresholds you calibrate + record in NOTES. **Boundary values tested.**
  Tier 4 = No Match must route to the Policy-6 fallback at the output boundary (the loop already does
  this via `is_zero_match` reading `tier == 4` — keep tool 6 returning integer `tier`).
- **Corpus seeding** — seed the synthetic crisis-case-study corpus into Chroma **lazily on first use**
  (import-safety / RAG1 must still hold — nothing at import). Idempotent (don't double-insert on
  re-seed).
- **`match_solicitation_angle` (main.py §5)** — wire it: build the semantic ranking (`semantic_query`)
  AND the BM25 ranking (`bm25_query`) over the corpus, fuse via `rrf_fuse`, map to a tier, and return
  `{"angle_key", "tier", "scores"}` with `tier ∈ {1,2,3,4}`. **Both rankers must contribute** (T6.2 —
  not one or the other). `category_path` participates (e.g. as a BM25 exact-term signal).
- **`tests/test_rag.py`** — cover RAG2 (model = `all-MiniLM-L6-v2`, correct vector dimensionality),
  RAG3 (BM25 independent ranked list), RAG4 (**RRF fused scores equal a hand-computed
  `Σ 1/(k+rank)`** for known input rankings; deterministic ties), RAG5 (tier boundaries; Tier 4 →
  fallback cross-check), T6.1–T6.5. Use a throwaway Chroma persist dir (`tmp_chroma`). Live model load
  is allowed here (it's local, no API key) but keep it minimal.

## QA checks to PASS (run, not inspect — by the PM)
`RAG1` (cross-check still holds), `RAG2`, `RAG3`, `RAG4`, `RAG5`, `T6.1`–`T6.5`. **Your sandbox cannot
run Python** — write the code + tests, mark *drafted only*; the PM runs them in `.venv` (the PM will
load the real embedder to confirm RAG2 dim and will hand-verify the RRF arithmetic for RAG4).

## Constraints (from CLAUDE.md that bite this stage)
- **Import-safety (ENV4) holds** — embedder/Chroma/corpus all lazy; nothing at import. RAG1 must still pass.
- Embeddings stay **local** (`all-MiniLM-L6-v2`, `EMBED_MODEL`) — no API key, no network for embeddings.
- `match_solicitation_angle` signature + return keys unchanged; `tier` stays an int; `tier==4` keeps
  routing to Policy-6 (do not break FB2 / the full regression).
- No `eval`/`exec`; no framework; no real catalog values in the corpus or code (CAT5/G2).
- Record OQ-4 resolution (k, the 4 thresholds, Tier 2/3 labels, corpus provenance) in NOTES **before**
  claiming RAG4/RAG5.

## Inputs / files you may touch
Create/edit: `rag_engine.py` (`bm25_query`, `rrf_fuse`, tier mapping, lazy corpus seeding), `main.py`
§5 `match_solicitation_angle` only (do NOT touch the other 7 tools / §6 schemas / §8 governance / §10
loop), an optional small corpus data file, `tests/test_rag.py`, and the NOTES OQ-4 entry.

## Do NOT
Advance past Stage 6. Change `match_solicitation_angle`'s signature/return-key set, any other tool, a
schema, a policy constant, the loop contract, or a graded literal. If the corpus or thresholds seem to
require an Asaf decision beyond "author a small synthetic corpus + calibrate k=60 defaults", STOP and
surface **DECISION-NEEDED**.

## Deliver
Write `handbacks/stage-6.md` in the standard format; separate *drafted only* from *written and
test-verified* (all drafted-only — PM verifies). List every `RAG*`/`T6.*` check covered + the recorded
k/thresholds. Return it as your final message.
