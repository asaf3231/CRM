"""
tests/test_rag.py — Stage 6: Hybrid RAG / RRF angle engine tests

Covers: RAG1-RAG5, T6.1-T6.5

RAG1: lazy local store (cross-check ENV4)
RAG2: all-MiniLM-L6-v2; correct vector dimensionality (384)
RAG3: BM25 exact path independent of semantic
RAG4: RRF math verified against hand-computed example; k=60; deterministic ties
RAG5: fused score → Tier 1/2/3/4; boundary values tested; Tier 4 → Policy-6 fallback
T6.1: match_solicitation_angle returns {"angle_key","tier","scores"}, tier ∈ {1,2,3,4}
T6.2: both semantic and BM25 rankers contribute to fused result
T6.3: RRF correctness: hand-computed Σ 1/(k+rank)
T6.4: tier mapping boundary values
T6.5: Tier 4 routes to Policy-6 fallback

All tests using Chroma use a throwaway temp dir (tmp_chroma fixture).
Live model load (sentence-transformers) is allowed — it's local, no API key.
"""

import sys
import os
import json
import math
import pathlib
import importlib
import tempfile
import shutil

import pytest


# ---------------------------------------------------------------------------
# Helpers to reset rag_engine state between tests
# ---------------------------------------------------------------------------

def _reset_rag_engine():
    """Force rag_engine to be re-imported fresh (clears lazy singletons)."""
    for mod_name in list(sys.modules.keys()):
        if mod_name.startswith("rag_engine") or mod_name == "rag_engine":
            del sys.modules[mod_name]
    if "main" in sys.modules:
        del sys.modules["main"]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def tmp_chroma(tmp_path, monkeypatch):
    """Provide a throwaway Chroma persist directory, isolated per test.

    Monkeypatches rag_engine.CHROMA_PERSIST_DIR and resets lazy singletons
    so each test gets a fresh, empty collection.
    """
    _reset_rag_engine()
    import rag_engine

    chroma_dir = str(tmp_path / ".chroma_test")
    monkeypatch.setattr(rag_engine, "CHROMA_PERSIST_DIR", chroma_dir)
    monkeypatch.setattr(rag_engine, "_collection_instance", None)
    monkeypatch.setattr(rag_engine, "_embedder_instance", None)
    monkeypatch.setattr(rag_engine, "_corpus_seeded", False)
    # Also override getcwd to tmp_path so any path resolution goes there
    monkeypatch.chdir(tmp_path)
    yield tmp_path
    # Cleanup (chroma dir may have been created)
    if os.path.exists(chroma_dir):
        shutil.rmtree(chroma_dir, ignore_errors=True)
    _reset_rag_engine()


@pytest.fixture()
def small_corpus():
    """A minimal 4-document corpus for RRF and BM25 tests."""
    return [
        {
            "id": "doc_alpha",
            "text": "social media crisis brand controversy paid advertising DTC ecommerce",
        },
        {
            "id": "doc_beta",
            "text": "product recall brand reputation management performance marketing",
        },
        {
            "id": "doc_gamma",
            "text": "influencer scandal viral backlash Meta Pixel TikTok tracking ecommerce",
        },
        {
            "id": "doc_delta",
            "text": "industrial B2B manufacturing procurement no social media presence",
        },
    ]


# ---------------------------------------------------------------------------
# §RAG1 — Lazy local store (import-safety cross-check)
# ---------------------------------------------------------------------------

class TestRAG1LazyStore:
    """RAG1: Chroma is not built at import time; builds on first use."""

    def test_import_does_not_build_collection(self):
        """Importing rag_engine must not open Chroma or load the embedder."""
        _reset_rag_engine()
        import rag_engine
        # After a clean import, both lazy singletons must be None
        assert rag_engine._collection_instance is None, (
            "RAG1 FAIL: _collection_instance is not None after import"
        )
        assert rag_engine._embedder_instance is None, (
            "RAG1 FAIL: _embedder_instance is not None after import"
        )

    def test_collection_builds_on_first_use(self, tmp_chroma):
        """_get_collection() builds the collection on first call."""
        import rag_engine
        assert rag_engine._collection_instance is None
        col = rag_engine._get_collection()
        assert col is not None, "RAG1 FAIL: _get_collection() returned None"
        assert rag_engine._collection_instance is not None, (
            "RAG1 FAIL: singleton not set after first call"
        )

    def test_collection_singleton_identity(self, tmp_chroma):
        """_get_collection() returns the same object on repeated calls."""
        import rag_engine
        col1 = rag_engine._get_collection()
        col2 = rag_engine._get_collection()
        assert col1 is col2, "RAG1 FAIL: collection singleton identity broken"

    def test_collection_persists_under_chroma_dir(self, tmp_chroma):
        """Chroma persist dir is created under .chroma/ relative to cwd."""
        import rag_engine
        rag_engine._get_collection()
        chroma_path = pathlib.Path(str(tmp_chroma)) / rag_engine.CHROMA_PERSIST_DIR
        assert chroma_path.exists(), (
            f"RAG1 FAIL: Chroma persist dir not created at {chroma_path}"
        )


# ---------------------------------------------------------------------------
# §RAG2 — Embedding model: all-MiniLM-L6-v2, 384-dim vectors
# ---------------------------------------------------------------------------

class TestRAG2EmbeddingModel:
    """RAG2: all-MiniLM-L6-v2 is used; vectors have 384 dimensions."""

    def test_embed_model_constant(self):
        """EMBED_MODEL constant is exactly 'all-MiniLM-L6-v2'."""
        _reset_rag_engine()
        import rag_engine
        assert rag_engine.EMBED_MODEL == "all-MiniLM-L6-v2", (
            f"RAG2 FAIL: EMBED_MODEL={rag_engine.EMBED_MODEL!r}"
        )

    def test_embedder_is_not_loaded_at_import(self):
        """The SentenceTransformer model is not loaded at import time."""
        _reset_rag_engine()
        import rag_engine
        assert rag_engine._embedder_instance is None, (
            "RAG2 FAIL: embedder loaded at import"
        )

    def test_embed_texts_returns_384_dim_vectors(self, tmp_chroma):
        """embed_texts returns 384-dimensional vectors (all-MiniLM-L6-v2)."""
        import rag_engine
        vecs = rag_engine.embed_texts(["social media crisis brand outreach"])
        assert len(vecs) == 1, "RAG2 FAIL: expected 1 embedding"
        assert len(vecs[0]) == 384, (
            f"RAG2 FAIL: embedding dim = {len(vecs[0])}, expected 384"
        )

    def test_embed_multiple_texts_correct_count_and_dim(self, tmp_chroma):
        """Multiple texts each produce a 384-dim vector."""
        import rag_engine
        texts = ["crisis narrative", "brand recovery", "paid social advertising"]
        vecs = rag_engine.embed_texts(texts)
        assert len(vecs) == 3, f"RAG2 FAIL: expected 3 embeddings, got {len(vecs)}"
        for i, v in enumerate(vecs):
            assert len(v) == 384, (
                f"RAG2 FAIL: embedding[{i}] dim = {len(v)}, expected 384"
            )

    def test_embedder_singleton(self, tmp_chroma):
        """_get_embedder() returns the same object on repeated calls."""
        import rag_engine
        e1 = rag_engine._get_embedder()
        e2 = rag_engine._get_embedder()
        assert e1 is e2, "RAG2 FAIL: embedder singleton identity broken"


# ---------------------------------------------------------------------------
# §RAG3 — BM25 exact path, independent of semantic
# ---------------------------------------------------------------------------

class TestRAG3BM25:
    """RAG3: bm25_query returns a ranked list independent of Chroma/semantic."""

    def test_bm25_returns_list(self, small_corpus):
        """bm25_query returns a list."""
        import rag_engine
        docs = [e["text"] for e in small_corpus]
        ids = [e["id"] for e in small_corpus]
        result = rag_engine.bm25_query("crisis brand", docs, ids, n_results=10)
        assert isinstance(result, list), "RAG3 FAIL: bm25_query must return a list"

    def test_bm25_ranks_relevant_docs_higher(self, small_corpus):
        """Documents containing the query terms rank above those that don't."""
        import rag_engine
        docs = [e["text"] for e in small_corpus]
        ids = [e["id"] for e in small_corpus]
        result = rag_engine.bm25_query("crisis brand DTC ecommerce", docs, ids, n_results=10)
        # doc_alpha and doc_gamma contain crisis/brand/DTC/ecommerce; doc_delta does not
        result_ids = [r["id"] for r in result]
        assert "doc_delta" not in result_ids or result_ids.index("doc_delta") > 0, (
            "RAG3 FAIL: doc_delta (B2B, no crisis) should not rank first"
        )
        # doc_alpha or doc_gamma should be at the top (both have "crisis", "brand", "ecommerce")
        assert result_ids[0] in ("doc_alpha", "doc_gamma"), (
            f"RAG3 FAIL: top result is {result_ids[0]!r}, expected doc_alpha or doc_gamma"
        )

    def test_bm25_result_shape(self, small_corpus):
        """Each BM25 result has 'id', 'document', 'score' keys."""
        import rag_engine
        docs = [e["text"] for e in small_corpus]
        ids = [e["id"] for e in small_corpus]
        result = rag_engine.bm25_query("brand crisis", docs, ids, n_results=10)
        assert len(result) > 0, "RAG3 FAIL: expected at least one result"
        for item in result:
            assert "id" in item, "RAG3 FAIL: result missing 'id'"
            assert "document" in item, "RAG3 FAIL: result missing 'document'"
            assert "score" in item, "RAG3 FAIL: result missing 'score'"
            assert item["score"] > 0.0, "RAG3 FAIL: zero-score doc should be excluded"

    def test_bm25_empty_documents_returns_empty(self):
        """bm25_query returns [] when documents is empty."""
        import rag_engine
        result = rag_engine.bm25_query("query text", [], [], n_results=5)
        assert result == [], "RAG3 FAIL: expected [] for empty corpus"

    def test_bm25_empty_query_returns_empty(self, small_corpus):
        """bm25_query returns [] when query is empty string."""
        import rag_engine
        docs = [e["text"] for e in small_corpus]
        ids = [e["id"] for e in small_corpus]
        result = rag_engine.bm25_query("", docs, ids, n_results=5)
        assert result == [], "RAG3 FAIL: expected [] for empty query"

    def test_bm25_no_matching_terms_returns_empty(self, small_corpus):
        """bm25_query returns [] when query terms have zero IDF signal."""
        import rag_engine
        docs = [e["text"] for e in small_corpus]
        ids = [e["id"] for e in small_corpus]
        # "zzzyyyxxx" is guaranteed not in any doc
        result = rag_engine.bm25_query("zzzyyyxxx", docs, ids, n_results=5)
        assert result == [], "RAG3 FAIL: expected [] for unknown query terms"

    def test_bm25_honors_n_results(self, small_corpus):
        """bm25_query respects the n_results limit."""
        import rag_engine
        docs = [e["text"] for e in small_corpus]
        ids = [e["id"] for e in small_corpus]
        result = rag_engine.bm25_query("brand ecommerce", docs, ids, n_results=2)
        assert len(result) <= 2, f"RAG3 FAIL: expected ≤2 results, got {len(result)}"

    def test_bm25_independent_of_chroma(self, small_corpus):
        """bm25_query does NOT call _get_collection() — verified by checking
        that _collection_instance stays None when only bm25_query is called."""
        _reset_rag_engine()
        import rag_engine
        # Do NOT call _get_collection() at all
        assert rag_engine._collection_instance is None
        docs = [e["text"] for e in small_corpus]
        ids = [e["id"] for e in small_corpus]
        rag_engine.bm25_query("crisis brand", docs, ids, n_results=5)
        # _collection_instance must still be None — BM25 is independent
        assert rag_engine._collection_instance is None, (
            "RAG3 FAIL: bm25_query touched Chroma (collection_instance is not None)"
        )

    def test_bm25_sorted_descending(self, small_corpus):
        """BM25 results are sorted by score descending."""
        import rag_engine
        docs = [e["text"] for e in small_corpus]
        ids = [e["id"] for e in small_corpus]
        result = rag_engine.bm25_query("brand crisis DTC", docs, ids, n_results=10)
        scores = [r["score"] for r in result]
        assert scores == sorted(scores, reverse=True), (
            "RAG3 FAIL: BM25 results not sorted descending"
        )

    def test_bm25_mismatched_lengths_raises(self, small_corpus):
        """bm25_query raises ValueError when len(documents) != len(doc_ids)."""
        import rag_engine
        docs = [e["text"] for e in small_corpus]
        ids = [e["id"] for e in small_corpus][:2]  # shorter than docs
        with pytest.raises(ValueError, match="bm25_query"):
            rag_engine.bm25_query("crisis", docs, ids, n_results=5)


# ---------------------------------------------------------------------------
# §RAG4 — RRF fusion math: hand-computed verification
# ---------------------------------------------------------------------------

class TestRAG4RRFFusion:
    """RAG4: RRF(d) = Σ 1/(k+rank_r(d)); k=60; hand-verified; deterministic ties."""

    def _make_semantic(self, ordered_ids):
        """Build a fake semantic_results list from an ordered list of ids."""
        return [{"id": doc_id, "distance": 0.1 * (i + 1)} for i, doc_id in enumerate(ordered_ids)]

    def _make_bm25(self, ordered_ids):
        """Build a fake bm25_results list from an ordered list of ids."""
        return [{"id": doc_id, "document": f"doc {doc_id}", "score": 10.0 - i}
                for i, doc_id in enumerate(ordered_ids)]

    def test_rrf_hand_computed_two_rankers(self):
        """RRF scores match hand-computed Σ 1/(60+rank) for known rankings.

        Setup:
            Semantic: [A(rank1), B(rank2), C(rank3)]
            BM25:     [B(rank1), A(rank2), C(rank3)]

        Expected RRF scores (k=60):
            A: 1/(60+1) + 1/(60+2) = 1/61 + 1/62 = 0.016393... + 0.016129... = 0.032522...
            B: 1/(60+2) + 1/(60+1) = 1/62 + 1/61 = 0.016129... + 0.016393... = 0.032522...
            C: 1/(60+3) + 1/(60+3) = 1/63 + 1/63 = 0.015873... + 0.015873... = 0.031746...

        A and B have equal scores; tie-break by id (A < B alphabetically) → A first.
        """
        import rag_engine

        semantic = self._make_semantic(["doc_A", "doc_B", "doc_C"])
        bm25 = self._make_bm25(["doc_B", "doc_A", "doc_C"])

        k = 60
        fused = rag_engine.rrf_fuse(semantic, bm25, k=k)

        # Hand-computed scores
        expected_A = 1 / (k + 1) + 1 / (k + 2)  # sem rank 1, bm25 rank 2
        expected_B = 1 / (k + 2) + 1 / (k + 1)  # sem rank 2, bm25 rank 1
        expected_C = 1 / (k + 3) + 1 / (k + 3)  # sem rank 3, bm25 rank 3

        # Note: A == B (same score, different order)
        assert abs(expected_A - expected_B) < 1e-12, "Test setup error"

        fused_by_id = {item["id"]: item["rrf_score"] for item in fused}

        assert "doc_A" in fused_by_id, "RAG4 FAIL: doc_A missing from fused results"
        assert "doc_B" in fused_by_id, "RAG4 FAIL: doc_B missing from fused results"
        assert "doc_C" in fused_by_id, "RAG4 FAIL: doc_C missing from fused results"

        tol = 1e-10
        assert abs(fused_by_id["doc_A"] - expected_A) < tol, (
            f"RAG4 FAIL: doc_A RRF score {fused_by_id['doc_A']:.10f} "
            f"!= hand-computed {expected_A:.10f}"
        )
        assert abs(fused_by_id["doc_B"] - expected_B) < tol, (
            f"RAG4 FAIL: doc_B RRF score {fused_by_id['doc_B']:.10f} "
            f"!= hand-computed {expected_B:.10f}"
        )
        assert abs(fused_by_id["doc_C"] - expected_C) < tol, (
            f"RAG4 FAIL: doc_C RRF score {fused_by_id['doc_C']:.10f} "
            f"!= hand-computed {expected_C:.10f}"
        )

    def test_rrf_rank_ordering(self):
        """Fused list is sorted by rrf_score descending."""
        import rag_engine

        semantic = self._make_semantic(["doc_A", "doc_B", "doc_C"])
        bm25 = self._make_bm25(["doc_A", "doc_B", "doc_C"])
        fused = rag_engine.rrf_fuse(semantic, bm25, k=60)

        scores = [item["rrf_score"] for item in fused]
        assert scores == sorted(scores, reverse=True), (
            "RAG4 FAIL: fused list not sorted by rrf_score descending"
        )

    def test_rrf_deterministic_tiebreak_by_id(self):
        """Equal RRF scores: lexicographically smaller id comes first."""
        import rag_engine

        # doc_A and doc_B will have identical RRF scores:
        # Semantic: [doc_A(1), doc_B(2)]; BM25: [doc_B(1), doc_A(2)]
        # A: 1/61 + 1/62 = 0.032522...; B: 1/62 + 1/61 = 0.032522...
        semantic = self._make_semantic(["doc_A", "doc_B"])
        bm25 = self._make_bm25(["doc_B", "doc_A"])
        fused = rag_engine.rrf_fuse(semantic, bm25, k=60)

        scores = [item["rrf_score"] for item in fused]
        assert abs(scores[0] - scores[1]) < 1e-12, (
            "Test setup error: expected tie"
        )
        # Tie-break: 'doc_A' < 'doc_B' lexicographically → doc_A first
        assert fused[0]["id"] == "doc_A", (
            f"RAG4 FAIL: tie-break expected doc_A first, got {fused[0]['id']!r}"
        )
        assert fused[1]["id"] == "doc_B", (
            f"RAG4 FAIL: tie-break expected doc_B second, got {fused[1]['id']!r}"
        )

    def test_rrf_single_ranker_only_semantic(self):
        """A doc in only one ranker gets score 1/(k+rank) from that ranker only."""
        import rag_engine

        semantic = self._make_semantic(["doc_X"])  # only in semantic at rank 1
        bm25 = []  # not in BM25

        k = 60
        fused = rag_engine.rrf_fuse(semantic, bm25, k=k)

        assert len(fused) == 1, "RAG4 FAIL: expected 1 fused result"
        expected_score = 1 / (k + 1)
        assert abs(fused[0]["rrf_score"] - expected_score) < 1e-12, (
            f"RAG4 FAIL: single-ranker score {fused[0]['rrf_score']} != {expected_score}"
        )

    def test_rrf_single_ranker_only_bm25(self):
        """A doc in only BM25 at rank 1 gets exactly 1/(k+1)."""
        import rag_engine

        semantic = []
        bm25 = self._make_bm25(["doc_Y"])

        k = 60
        fused = rag_engine.rrf_fuse(semantic, bm25, k=k)

        assert len(fused) == 1, "RAG4 FAIL: expected 1 fused result"
        expected_score = 1 / (k + 1)
        assert abs(fused[0]["rrf_score"] - expected_score) < 1e-12, (
            f"RAG4 FAIL: BM25-only score {fused[0]['rrf_score']} != {expected_score}"
        )

    def test_rrf_empty_both_returns_empty(self):
        """rrf_fuse returns [] when both inputs are empty."""
        import rag_engine
        fused = rag_engine.rrf_fuse([], [], k=60)
        assert fused == [], "RAG4 FAIL: expected [] for empty inputs"

    def test_rrf_fused_contains_semantic_rank_and_bm25_rank(self):
        """Fused results carry semantic_rank and bm25_rank for auditability."""
        import rag_engine

        semantic = self._make_semantic(["doc_A", "doc_B"])
        bm25 = self._make_bm25(["doc_B", "doc_A"])
        fused = rag_engine.rrf_fuse(semantic, bm25, k=60)

        for item in fused:
            assert "semantic_rank" in item, "RAG4 FAIL: missing semantic_rank"
            assert "bm25_rank" in item, "RAG4 FAIL: missing bm25_rank"

    def test_rrf_k_parameter_used_correctly(self):
        """Changing k changes the RRF scores proportionally (sanity check)."""
        import rag_engine

        semantic = self._make_semantic(["doc_A"])
        bm25 = self._make_bm25(["doc_A"])

        k30 = 30
        k60 = 60
        fused_k30 = rag_engine.rrf_fuse(semantic, bm25, k=k30)
        fused_k60 = rag_engine.rrf_fuse(semantic, bm25, k=k60)

        # k=30 → 2/(30+1) ≈ 0.0645; k=60 → 2/(60+1) ≈ 0.0328
        # So k=30 should yield a higher score than k=60
        assert fused_k30[0]["rrf_score"] > fused_k60[0]["rrf_score"], (
            "RAG4 FAIL: smaller k should yield higher RRF score"
        )

    def test_rrf_default_k_is_60(self):
        """rrf_fuse uses k=60 by default (matches OQ-4 resolution)."""
        import rag_engine

        semantic = [{"id": "doc_Z", "distance": 0.1}]
        bm25 = [{"id": "doc_Z", "document": "doc", "score": 5.0}]

        fused_default = rag_engine.rrf_fuse(semantic, bm25)  # no k arg
        fused_explicit = rag_engine.rrf_fuse(semantic, bm25, k=60)

        assert abs(fused_default[0]["rrf_score"] - fused_explicit[0]["rrf_score"]) < 1e-12, (
            "RAG4 FAIL: default k does not equal 60"
        )
        assert rag_engine.RRF_K == 60, "RAG4 FAIL: RRF_K constant is not 60"


# ---------------------------------------------------------------------------
# §RAG5 — Tier classification: boundaries tested; Tier 4 → Policy-6 fallback
# ---------------------------------------------------------------------------

class TestRAG5TierClassification:
    """RAG5: fused top score maps to Tier 1/2/3/4; boundary values tested."""

    def test_score_to_tier_tier1_critical_fit(self):
        """score >= 0.025 → Tier 1 Critical Fit."""
        import rag_engine
        assert rag_engine.score_to_tier(0.025) == 1, "RAG5 FAIL: 0.025 should be Tier 1"
        assert rag_engine.score_to_tier(0.030) == 1, "RAG5 FAIL: 0.030 should be Tier 1"
        assert rag_engine.score_to_tier(0.033) == 1, "RAG5 FAIL: 0.033 should be Tier 1"

    def test_score_to_tier_tier2_strong_fit(self):
        """0.015 <= score < 0.025 → Tier 2 Strong Fit."""
        import rag_engine
        assert rag_engine.score_to_tier(0.015) == 2, "RAG5 FAIL: 0.015 should be Tier 2"
        assert rag_engine.score_to_tier(0.020) == 2, "RAG5 FAIL: 0.020 should be Tier 2"
        assert rag_engine.score_to_tier(0.0249) == 2, "RAG5 FAIL: 0.0249 should be Tier 2"

    def test_score_to_tier_tier3_watchlist(self):
        """0.005 <= score < 0.015 → Tier 3 Watchlist."""
        import rag_engine
        assert rag_engine.score_to_tier(0.005) == 3, "RAG5 FAIL: 0.005 should be Tier 3"
        assert rag_engine.score_to_tier(0.010) == 3, "RAG5 FAIL: 0.010 should be Tier 3"
        assert rag_engine.score_to_tier(0.0149) == 3, "RAG5 FAIL: 0.0149 should be Tier 3"

    def test_score_to_tier_tier4_no_match(self):
        """score < 0.005 → Tier 4 No Match → routes to Policy-6 fallback."""
        import rag_engine
        assert rag_engine.score_to_tier(0.004) == 4, "RAG5 FAIL: 0.004 should be Tier 4"
        assert rag_engine.score_to_tier(0.0) == 4, "RAG5 FAIL: 0.0 should be Tier 4"
        assert rag_engine.score_to_tier(0.0049) == 4, "RAG5 FAIL: 0.0049 should be Tier 4"

    def test_score_to_tier_boundary_at_threshold(self):
        """Exact threshold values are inclusive at the upper tier."""
        import rag_engine
        # 0.025 exactly → Tier 1 (>= threshold)
        assert rag_engine.score_to_tier(0.025) == 1
        # 0.015 exactly → Tier 2 (>= threshold, < Tier 1 threshold)
        assert rag_engine.score_to_tier(0.015) == 2
        # 0.005 exactly → Tier 3 (>= threshold, < Tier 2 threshold)
        assert rag_engine.score_to_tier(0.005) == 3
        # Just below 0.005 → Tier 4
        assert rag_engine.score_to_tier(0.00499) == 4

    def test_tier4_routes_to_policy6_in_main(self, tmp_chroma):
        """Tier 4 from match_solicitation_angle triggers is_zero_match=True
        in main.py (cross-check T6.5 / FB2).

        This test verifies the integration: if all angles resolve to Tier 4,
        is_zero_match detects it and the engine would emit FALLBACK_MESSAGE.
        """
        _reset_rag_engine()
        import main

        # A Tier-4 result dict (simulates what match_solicitation_angle returns)
        tier4_result = {"tool_name": "match_solicitation_angle", "result": {"angle_key": "no_match", "tier": 4, "scores": {}}}
        assert main.is_zero_match([tier4_result]), (
            "RAG5/T6.5 FAIL: is_zero_match should be True for a Tier-4 angle result"
        )

    def test_tier1_does_not_trigger_is_zero_match(self, tmp_chroma):
        """Tier 1 result does NOT trigger the Policy-6 fallback."""
        _reset_rag_engine()
        import main

        tier1_result = {"tool_name": "match_solicitation_angle", "result": {"angle_key": "crisis_fit_001", "tier": 1, "scores": {}}}
        assert not main.is_zero_match([tier1_result]), (
            "RAG5 FAIL: is_zero_match should be False for a Tier-1 result"
        )

    def test_threshold_constants_recorded(self):
        """Tier threshold constants exist and are in the expected order."""
        import rag_engine
        assert rag_engine.TIER1_THRESHOLD == 0.025, "RAG5: TIER1_THRESHOLD must be 0.025"
        assert rag_engine.TIER2_THRESHOLD == 0.015, "RAG5: TIER2_THRESHOLD must be 0.015"
        assert rag_engine.TIER3_THRESHOLD == 0.005, "RAG5: TIER3_THRESHOLD must be 0.005"
        assert rag_engine.TIER1_THRESHOLD > rag_engine.TIER2_THRESHOLD > rag_engine.TIER3_THRESHOLD, (
            "RAG5: tier thresholds must be strictly descending"
        )


# ---------------------------------------------------------------------------
# §T6 — match_solicitation_angle integration tests
# ---------------------------------------------------------------------------

class TestT6MatchSolicitationAngle:
    """T6.1–T6.5: match_solicitation_angle wired to the full hybrid pipeline."""

    @pytest.fixture(autouse=True)
    def reset_and_chroma(self, tmp_path, monkeypatch):
        """Set up isolated Chroma dir, reset rag_engine singletons, chdir to tmp_path."""
        # Ensure rag_engine is freshly imported
        _reset_rag_engine()
        import rag_engine

        chroma_dir = str(tmp_path / ".chroma_t6")
        monkeypatch.setattr(rag_engine, "CHROMA_PERSIST_DIR", chroma_dir)
        monkeypatch.setattr(rag_engine, "_collection_instance", None)
        monkeypatch.setattr(rag_engine, "_embedder_instance", None)
        monkeypatch.setattr(rag_engine, "_corpus_seeded", False)
        monkeypatch.chdir(tmp_path)
        self.tmp_path = tmp_path
        self._rag = rag_engine

        yield

        # Cleanup
        if os.path.exists(chroma_dir):
            shutil.rmtree(chroma_dir, ignore_errors=True)
        _reset_rag_engine()

    def _seed_small_corpus(self, small_corpus_data):
        """Seed a small corpus into the test Chroma collection."""
        docs = [e["text"] for e in small_corpus_data]
        ids = [e["id"] for e in small_corpus_data]
        metadatas = [{"angle_key": e["id"], "category_hint": ""} for e in small_corpus_data]
        self._rag.upsert_documents(docs, ids, metadatas)

    def test_t6_1_return_shape_empty_corpus(self):
        """T6.1: match_solicitation_angle returns correct shape even with empty corpus."""
        import main
        result = main.match_solicitation_angle("some narrative", "Apparel > Athleisure")
        assert isinstance(result, dict), "T6.1 FAIL: result must be a dict"
        assert "angle_key" in result, "T6.1 FAIL: missing 'angle_key'"
        assert "tier" in result, "T6.1 FAIL: missing 'tier'"
        assert "scores" in result, "T6.1 FAIL: missing 'scores'"
        assert result["tier"] in {1, 2, 3, 4}, f"T6.1 FAIL: tier {result['tier']} not in {{1,2,3,4}}"

    def test_t6_1_empty_corpus_yields_tier4(self):
        """T6.1: empty corpus → Tier 4 (no results)."""
        import main
        result = main.match_solicitation_angle("brand crisis narrative", "Apparel > Fashion")
        assert result["tier"] == 4, (
            f"T6.1 FAIL: empty corpus should yield tier=4, got {result['tier']}"
        )
        assert result["angle_key"] == "no_match", (
            f"T6.1 FAIL: empty corpus should yield angle_key='no_match', got {result['angle_key']!r}"
        )

    def test_t6_1_return_shape_with_corpus(self, small_corpus):
        """T6.1: with seeded corpus, return shape is correct."""
        self._seed_small_corpus(small_corpus)
        import main
        result = main.match_solicitation_angle(
            "social media crisis brand controversy", "Apparel > Athleisure"
        )
        assert isinstance(result, dict), "T6.1 FAIL: result must be a dict"
        assert "angle_key" in result, "T6.1 FAIL: missing 'angle_key'"
        assert "tier" in result, "T6.1 FAIL: missing 'tier'"
        assert "scores" in result, "T6.1 FAIL: missing 'scores'"
        assert result["tier"] in {1, 2, 3, 4}, (
            f"T6.1 FAIL: tier {result['tier']} not in {{1,2,3,4}}"
        )

    def test_t6_2_both_rankers_contribute(self, small_corpus):
        """T6.2: both semantic and BM25 rankers produce non-empty results
        when the corpus has relevant documents.

        Verified by inspecting the scores dict for non-zero counts from both.
        """
        self._seed_small_corpus(small_corpus)
        import main
        result = main.match_solicitation_angle(
            "crisis brand reputation social media ecommerce", "Apparel > DTC"
        )
        scores = result.get("scores", {})
        # Both rankers should find results for this strongly-matching query
        assert scores.get("semantic_results", 0) > 0, (
            "T6.2 FAIL: semantic ranker returned 0 results (both rankers must contribute)"
        )
        assert scores.get("bm25_results", 0) > 0, (
            "T6.2 FAIL: BM25 ranker returned 0 results (both rankers must contribute)"
        )
        assert scores.get("fused_results", 0) > 0, (
            "T6.2 FAIL: fused results are 0 (fusion must run)"
        )

    def test_t6_3_rrf_correctness_integration(self, small_corpus):
        """T6.3: hand-computable example — top fused score matches Σ 1/(k+rank).

        For a strongly-relevant query, the top doc appears near rank 1 in both
        rankers, giving an RRF score close to 2/(k+1) = 2/61 ≈ 0.0328.
        We verify the reported top_rrf_score is > 0 and ≤ 2/(k+1)+epsilon.
        """
        self._seed_small_corpus(small_corpus)
        import main
        result = main.match_solicitation_angle(
            "social media crisis brand controversy ecommerce DTC", "Apparel > DTC"
        )
        top_rrf = result["scores"].get("top_rrf_score", 0.0)
        max_possible = 2.0 / (60 + 1)  # ≈ 0.0328
        assert top_rrf > 0, "T6.3 FAIL: top_rrf_score must be > 0 with relevant corpus"
        assert top_rrf <= max_possible + 1e-9, (
            f"T6.3 FAIL: top_rrf_score {top_rrf:.6f} > max possible {max_possible:.6f}"
        )

    def test_t6_4_tier_mapping_boundary(self):
        """T6.4: tier maps to documented thresholds from NOTES.md."""
        import rag_engine
        # Directly test score_to_tier at boundaries (comprehensive, fast)
        assert rag_engine.score_to_tier(0.025) == 1, "T6.4: 0.025 → Tier 1"
        assert rag_engine.score_to_tier(0.0249) == 2, "T6.4: 0.0249 → Tier 2"
        assert rag_engine.score_to_tier(0.015) == 2, "T6.4: 0.015 → Tier 2"
        assert rag_engine.score_to_tier(0.0149) == 3, "T6.4: 0.0149 → Tier 3"
        assert rag_engine.score_to_tier(0.005) == 3, "T6.4: 0.005 → Tier 3"
        assert rag_engine.score_to_tier(0.0049) == 4, "T6.4: 0.0049 → Tier 4"
        assert rag_engine.score_to_tier(0.0) == 4, "T6.4: 0.0 → Tier 4"

    def test_t6_5_tier4_cross_checks_policy6(self):
        """T6.5: Tier 4 from match_solicitation_angle → is_zero_match=True (FB2 cross-check)."""
        import main
        # Simulate a Tier-4 result as the loop would record it
        history = [
            {"tool_name": "match_solicitation_angle",
             "result": {"angle_key": "no_match", "tier": 4, "scores": {}}},
        ]
        assert main.is_zero_match(history), (
            "T6.5 FAIL: is_zero_match must return True for all-Tier-4 angle results"
        )

    def test_t6_5_all_tier4_triggers_fallback_constant(self):
        """T6.5: the fallback message constant is the Policy-6 byte-exact string."""
        import main
        assert main.FALLBACK_MESSAGE == "We have no product available today that fits your request", (
            "T6.5 FAIL: FALLBACK_MESSAGE byte-exact constant mismatch"
        )


# ---------------------------------------------------------------------------
# §SemanticRelevanceFloor — Stage 6 r1 defect fix
# Tests: irrelevant query → Tier 4 (FB2 cross-check); relevant query → Tier 1-3.
# ---------------------------------------------------------------------------

class TestSemanticRelevanceFloor:
    """Stage 6 r1: semantic relevance floor prevents nonsense → Tier 1.

    THE DEFECT (fixed): match_solicitation_angle was choosing the tier from the
    RRF rank score alone. With k=60 over the small corpus the top fused score
    is always ≈ 0.033 (there's always a rank-1 doc), so EVERY query (even
    nonsense) returned Tier 1. Tier 4 was unreachable for real queries.

    THE FIX: check_semantic_relevance() gates on the top semantic result's cosine
    distance vs SEMANTIC_RELEVANCE_CEILING (0.80). If the best match is beyond
    the ceiling (no meaningful overlap), Tier 4 is returned regardless of RRF.

    These tests use the real embedder + the real angle_corpus.json corpus so
    that semantic distances are authentic (not mocked). The corpus file must
    be present at the cwd.
    """

    @pytest.fixture(autouse=True)
    def setup_with_real_corpus(self, tmp_path, monkeypatch):
        """Set up isolated Chroma + copy the real corpus to tmp_path for the floor tests."""
        _reset_rag_engine()
        import rag_engine

        chroma_dir = str(tmp_path / ".chroma_floor_test")
        monkeypatch.setattr(rag_engine, "CHROMA_PERSIST_DIR", chroma_dir)
        monkeypatch.setattr(rag_engine, "_collection_instance", None)
        monkeypatch.setattr(rag_engine, "_embedder_instance", None)
        monkeypatch.setattr(rag_engine, "_corpus_seeded", False)

        # Copy the real angle_corpus.json from the project root to tmp_path
        # so seed_corpus_if_empty() can find it.
        project_root = pathlib.Path(__file__).parent.parent
        corpus_src = project_root / "angle_corpus.json"
        if corpus_src.exists():
            shutil.copy(str(corpus_src), str(tmp_path / "angle_corpus.json"))
        # else: tests will skip gracefully

        monkeypatch.chdir(tmp_path)
        self.tmp_path = tmp_path
        self._rag = rag_engine

        yield

        if os.path.exists(chroma_dir):
            shutil.rmtree(chroma_dir, ignore_errors=True)
        _reset_rag_engine()

    def _corpus_available(self):
        """Return True if the corpus file was successfully copied."""
        return (self.tmp_path / "angle_corpus.json").exists()

    def test_check_semantic_relevance_constant_exists(self):
        """SEMANTIC_RELEVANCE_CEILING constant exists in rag_engine."""
        import rag_engine
        assert hasattr(rag_engine, "SEMANTIC_RELEVANCE_CEILING"), (
            "FLOOR FAIL: SEMANTIC_RELEVANCE_CEILING constant missing from rag_engine"
        )
        ceiling = rag_engine.SEMANTIC_RELEVANCE_CEILING
        assert isinstance(ceiling, float), (
            f"FLOOR FAIL: SEMANTIC_RELEVANCE_CEILING must be float, got {type(ceiling)}"
        )
        # Ceiling must be in a sane range (0 < ceiling < 1.0 for cosine distance)
        assert 0.0 < ceiling < 1.0, (
            f"FLOOR FAIL: SEMANTIC_RELEVANCE_CEILING={ceiling} out of valid range (0, 1)"
        )

    def test_check_semantic_relevance_helper_exists(self):
        """check_semantic_relevance() function exists in rag_engine."""
        import rag_engine
        assert hasattr(rag_engine, "check_semantic_relevance"), (
            "FLOOR FAIL: check_semantic_relevance function missing from rag_engine"
        )

    def test_check_semantic_relevance_below_ceiling_is_true(self):
        """check_semantic_relevance returns True when top distance is below ceiling."""
        import rag_engine
        # Simulate a close match (distance = 0.2, well within 0.80)
        semantic_results = [{"id": "doc1", "distance": 0.2, "document": "text"}]
        assert rag_engine.check_semantic_relevance(semantic_results) is True, (
            "FLOOR FAIL: distance 0.2 should be within the ceiling (returns True)"
        )

    def test_check_semantic_relevance_above_ceiling_is_false(self):
        """check_semantic_relevance returns False when top distance exceeds ceiling."""
        import rag_engine
        # Simulate a distant (irrelevant) match (distance = 0.95, above 0.80)
        semantic_results = [{"id": "doc1", "distance": 0.95, "document": "text"}]
        assert rag_engine.check_semantic_relevance(semantic_results) is False, (
            "FLOOR FAIL: distance 0.95 should exceed the ceiling (returns False)"
        )

    def test_check_semantic_relevance_at_ceiling_is_true(self):
        """check_semantic_relevance returns True when top distance equals the ceiling exactly."""
        import rag_engine
        ceiling = rag_engine.SEMANTIC_RELEVANCE_CEILING
        semantic_results = [{"id": "doc1", "distance": ceiling, "document": "text"}]
        # Boundary: at exactly the ceiling, check uses <=, so returns True
        assert rag_engine.check_semantic_relevance(semantic_results) is True, (
            f"FLOOR FAIL: distance exactly at ceiling={ceiling} should be within (returns True)"
        )

    def test_check_semantic_relevance_empty_is_false(self):
        """check_semantic_relevance returns False when semantic_results is empty."""
        import rag_engine
        assert rag_engine.check_semantic_relevance([]) is False, (
            "FLOOR FAIL: empty semantic_results should return False (no relevant match)"
        )

    def test_irrelevant_query_yields_tier4(self):
        """Stage 6 r1 core test: a nonsense query → Tier 4 (floor triggers).

        This is the FB2 cross-check: is_zero_match(result) must be True.

        Requires the real corpus + embedder to produce authentic cosine distances.
        """
        if not self._corpus_available():
            pytest.skip("angle_corpus.json not available — skipping floor integration test")

        import main
        import rag_engine

        # Seed the corpus so distances are computed against real documents
        rag_engine.seed_corpus_if_empty()
        if rag_engine._get_collection().count() == 0:
            pytest.skip("Corpus did not seed (corpus file issue) — skipping")

        # Genuinely irrelevant query: nonsense tokens with no semantic overlap
        # to any crisis/DTC/marketing document in the 12-entry corpus.
        nonsense_query = "zxqw nonsense unrelated quantum gardening"
        result = main.match_solicitation_angle(nonsense_query, "quantum_gardening > unrelated")

        assert result["tier"] == 4, (
            f"FLOOR FAIL (r1 core): nonsense query returned tier={result['tier']}, "
            f"expected tier=4. top_rrf_score={result['scores'].get('top_rrf_score', 'N/A')}, "
            f"relevance_floor_triggered={result['scores'].get('relevance_floor_triggered', False)}. "
            f"The semantic relevance floor is not working."
        )

        # FB2 cross-check: is_zero_match must be True for this Tier-4 result
        history = [{"tool_name": "match_solicitation_angle", "result": result}]
        assert main.is_zero_match(history), (
            "FLOOR FAIL (FB2 cross-check): is_zero_match should be True for nonsense-query Tier-4 result"
        )

    def test_strongly_relevant_query_yields_tier_1_2_or_3(self):
        """Stage 6 r1 core test: a strongly-relevant crisis query → Tier 1, 2, or 3 (NOT 4).

        Verifies the floor does not over-reject legitimate queries.
        """
        if not self._corpus_available():
            pytest.skip("angle_corpus.json not available — skipping floor integration test")

        import main
        import rag_engine

        # Seed the corpus
        rag_engine.seed_corpus_if_empty()
        if rag_engine._get_collection().count() == 0:
            pytest.skip("Corpus did not seed (corpus file issue) — skipping")

        # Strongly relevant query — matches the crisis/DTC/social media corpus well.
        # Uses terminology densely present across the top-tier corpus documents.
        relevant_query = (
            "viral product recall backlash and refund crisis on social media "
            "brand reputation paid advertising DTC ecommerce"
        )
        result = main.match_solicitation_angle(
            relevant_query, "Apparel > Athleisure > DTC"
        )

        assert result["tier"] in {1, 2, 3}, (
            f"FLOOR FAIL (r1 over-reject): strongly-relevant query returned tier={result['tier']}, "
            f"expected tier in {{1,2,3}}. "
            f"top_rrf_score={result['scores'].get('top_rrf_score', 'N/A')}, "
            f"relevance_floor_triggered={result['scores'].get('relevance_floor_triggered', False)}. "
            f"The relevance floor is set too aggressively (ceiling too low)."
        )


# ---------------------------------------------------------------------------
# §Corpus seeding — lazy and idempotent
# ---------------------------------------------------------------------------

class TestCorpusSeeding:
    """seed_corpus_if_empty() is lazy (not at import) and idempotent."""

    def test_corpus_not_seeded_at_import(self):
        """_corpus_seeded flag is False at import (nothing loaded)."""
        _reset_rag_engine()
        import rag_engine
        assert rag_engine._corpus_seeded is False, (
            "CORPUS FAIL: _corpus_seeded must be False at import"
        )

    def test_seed_corpus_without_file_does_not_crash(self, tmp_chroma):
        """seed_corpus_if_empty() gracefully handles missing corpus file."""
        import rag_engine
        # No angle_corpus.json in tmp_chroma — must not raise
        rag_engine.seed_corpus_if_empty()
        # Collection stays empty
        col = rag_engine._get_collection()
        assert col.count() == 0, (
            "CORPUS FAIL: collection should be empty when corpus file is absent"
        )

    def test_seed_corpus_idempotent(self, tmp_chroma):
        """Calling seed_corpus_if_empty() twice does not double-insert."""
        corpus_data = [
            {"id": "c1", "text": "crisis brand", "angle_key": "c1",
             "category_hint": "", "tier_label": "Critical Fit"},
            {"id": "c2", "text": "social media backlash", "angle_key": "c2",
             "category_hint": "", "tier_label": "Strong Fit"},
        ]
        corpus_path = tmp_chroma / "angle_corpus.json"
        corpus_path.write_text(json.dumps(corpus_data), encoding="utf-8")

        import rag_engine
        rag_engine.seed_corpus_if_empty()
        count_after_first = rag_engine._get_collection().count()

        rag_engine.seed_corpus_if_empty()
        count_after_second = rag_engine._get_collection().count()

        assert count_after_first == 2, (
            f"CORPUS FAIL: expected 2 docs after first seed, got {count_after_first}"
        )
        assert count_after_second == 2, (
            f"CORPUS FAIL: expected 2 docs after second seed (idempotent), got {count_after_second}"
        )

    def test_seed_corpus_sets_flag(self, tmp_chroma):
        """seed_corpus_if_empty() sets _corpus_seeded=True after seeding."""
        corpus_data = [
            {"id": "c1", "text": "crisis brand", "angle_key": "c1",
             "category_hint": "", "tier_label": "Critical Fit"},
        ]
        corpus_path = tmp_chroma / "angle_corpus.json"
        corpus_path.write_text(json.dumps(corpus_data), encoding="utf-8")

        import rag_engine
        assert rag_engine._corpus_seeded is False
        rag_engine.seed_corpus_if_empty()
        assert rag_engine._corpus_seeded is True, (
            "CORPUS FAIL: _corpus_seeded must be True after seeding"
        )


# ---------------------------------------------------------------------------
# §ENV4 cross-check — import-safety
# ---------------------------------------------------------------------------

class TestEnv4CrossCheck:
    """Cross-check: import rag_engine has zero side effects (RAG1 / ENV4)."""

    def test_import_rag_engine_is_side_effect_free(self, tmp_path):
        """Importing rag_engine from an empty dir must have no side effects."""
        _reset_rag_engine()

        # Import rag_engine cleanly
        import rag_engine

        # No lazy singletons triggered
        assert rag_engine._embedder_instance is None, (
            "ENV4/RAG1: embedder loaded at import"
        )
        assert rag_engine._collection_instance is None, (
            "ENV4/RAG1: collection built at import"
        )
        assert rag_engine._corpus_seeded is False, (
            "ENV4/RAG1: corpus seeded at import"
        )

    def test_import_all_three_modules_side_effect_free(self, tmp_path):
        """Import main, lead_store, rag_engine simultaneously — no side effects."""
        _reset_rag_engine()
        for mod in ["main", "lead_store", "rag_engine"]:
            if mod in sys.modules:
                del sys.modules[mod]

        import main
        import lead_store
        import rag_engine

        # rag_engine singletons
        assert rag_engine._embedder_instance is None
        assert rag_engine._collection_instance is None
        # main lazy client
        assert main._anthropic_client is None
        # lead_store lazy collection
        assert lead_store._collection_instance is None
