# Brief — Stage 6 (retry r1): RAG/RRF — add the No-Match relevance floor
Read first: CLAUDE.md (§6 tool 6) → PLAN.md → QA_checklist.md → NOTES.md (RRF tier section) → briefs/stage-6.md (original), then this.

The Stage-6 implementation is **mostly correct and PM-verified**: RAG2 (384-dim), **RAG4 RRF math is
hand-verified exact** (`Σ 1/(60+rank)`, deterministic tie-break), RAG3 BM25 independence, the `{"angle_key",
"tier","scores"}` shape, and `score_to_tier` boundaries all pass; full regression is 420 passed / 1
skipped. **Do NOT redo any of that.** One real functional defect must be fixed.

## The defect (PM found it via end-to-end probing; tests miss it)
`match_solicitation_angle` decides the tier **only** from the RRF rank score. With k=60 over the small
corpus, the top fused score is **always ≈ 2/61 ≈ 0.033** because there is always a rank-1 doc — even
for a totally irrelevant query. Result: **every query returns Tier 1 Critical Fit**, including
nonsense like `"zxqw nonsense unrelated quantum gardening"`. So **Tier 4 "No Match" is unreachable for
real queries** (only fires on an empty corpus). This:
- contradicts the documented Tier-4 semantics in NOTES ("below the fusion floor / **no meaningful
  overlap** → Tier 4"),
- deadens the FB2 zero-match-via-angle path (a brand with no relevant angle would wrongly proceed to
  outreach with a bogus Tier-1 angle).

Root cause: RRF is **rank-based** — it ignores match *magnitude*. The rank-1 semantic doc is rank 1
even when its cosine distance is huge. `semantic_query` already returns a `distance` per result; the
tier logic just never looks at it.

## Correction required (only this)
Add a **semantic relevance floor** to `match_solicitation_angle` (main.py §5) — and/or a small helper
in `rag_engine.py`:
- After computing `fused` and the top result, look at the **top semantic result's cosine `distance`**
  (from `semantic_query`; with `hnsw:space="cosine"`, smaller = more similar). If the best semantic
  match is **beyond the relevance ceiling** (i.e. no meaningful overlap), return **Tier 4 "No Match"**
  regardless of the RRF rank score.
- Choose the distance ceiling / similarity floor empirically against the 12-doc corpus so that:
  a genuinely **relevant** crisis query (e.g. "viral product recall backlash and refund crisis on
  social media") stays **Tier 1–3** (NOT 4), and a genuinely **irrelevant** query (e.g. "zxqw nonsense
  unrelated quantum gardening", or a clearly off-domain topic) maps to **Tier 4**. **Record the chosen
  floor + how you calibrated it in NOTES.md** (OQ-4 addendum).
- Keep the verified RRF math and `score_to_tier` for the relevant (above-floor) case — the floor is an
  ADDITIONAL gate that can only push a result DOWN to Tier 4, never up.

## Add tests (in tests/test_rag.py)
- An **irrelevant** query (e.g. the nonsense string) → `match_solicitation_angle(...)["tier"] == 4`
  (and therefore `is_zero_match([{"tool_name":"match_solicitation_angle","result":{"tier":4,...}}])`
  is True — FB2 cross-check).
- A **strongly-relevant** query → tier in `{1,2,3}` (NOT 4) — proves the floor doesn't over-reject.
- Keep all existing RAG/T6 tests green.

## Must stay true after the fix (PM re-verifies)
- RAG4 RRF math unchanged (still hand-verifiable). RAG2/RAG3/RAG5 boundaries unchanged.
- `match_solicitation_angle` signature + return-key set unchanged; `tier` stays an int ∈ {1,2,3,4};
  `tier==4` still routes to the Policy-6 fallback (FB2). Full regression (currently 420/1) stays green.
- ENV4/RAG1 import-safety holds (floor logic runs at call time, not import). No eval/framework. No real
  catalog values in the corpus/code.

## Do NOT
Change the RRF formula, k, `score_to_tier` thresholds (those are correct — the floor is separate), any
other tool, a schema, a policy constant, the loop contract, or a graded literal. If calibrating the
floor proves impossible without an Asaf decision, STOP and surface **DECISION-NEEDED** with the
observed distance distribution.

## Deliver
Update `handbacks/stage-6.md` (or write `handbacks/stage-6-r1.md`) noting the floor value + calibration
evidence; mark *drafted only* (PM re-runs). Return it as your final message.
