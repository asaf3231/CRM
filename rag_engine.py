"""
rag_engine.py — ReactFirst AI Proactive Outbound Engine
ChromaDB (all-MiniLM-L6-v2) + BM25 + RRF tiering — the lazy local vector store.

Import-safe: import of this module has ZERO side effects.
Heavy work (SentenceTransformer model load, Chroma collection open/build, corpus seed)
happens lazily inside _get_embedder() / _get_collection() / seed_corpus_if_empty()
on first call.

Stage 6 additions:
  - bm25_query:  real BM25 ranker (TF-IDF style, independent of Chroma)
  - rrf_fuse:    Reciprocal Rank Fusion (RRF(d) = Σ 1/(k+rank_r(d)), k=60)
  - Tier mapping: fused score → Tier 1 (Critical Fit) / Tier 2 (Strong Fit) /
                  Tier 3 (Watchlist) / Tier 4 (No Match)
  - Lazy corpus seeding: synthetic crisis-case-study corpus seeded into Chroma on first use

RRF k and tier thresholds (OQ-4, resolved Stage 6):
  k = 60 (standard RRF default)
  Tier 1 (Critical Fit):   top fused score >= 0.025
  Tier 2 (Strong Fit):     top fused score >= 0.015
  Tier 3 (Watchlist):      top fused score >= 0.005
  Tier 4 (No Match):       top fused score <  0.005

  Calibration rationale (2 rankers, k=60):
    Max possible score (rank 1 in both):      2 * 1/(60+1) ≈ 0.0328
    Strong single-ranker (rank 1, absent):    1/61         ≈ 0.0164
    Tier 1 threshold 0.025 requires strong agreement from both rankers.
    Tier 2 threshold 0.015 captures single-strong-ranker hits.
    Tier 3 threshold 0.005 captures weak/partial overlap.
    Tier 4 below 0.005 is effectively no meaningful overlap.

Semantic relevance floor (OQ-4 addendum — Stage 6 r1):
  SEMANTIC_RELEVANCE_CEILING = 0.80 (cosine distance; lower = more similar)
  If the top semantic result's cosine distance EXCEEDS 0.80, the query has no
  meaningful overlap with the corpus. Tier 4 "No Match" is returned immediately
  regardless of the RRF rank score (which with k=60 is always ≈ 0.033 for rank-1
  even for noise). The floor only pushes DOWN — it never upgrades a tier.

BM25 formula:
    Term Frequency (TF):  tf(t,d) = count(t in d) / len(d)
    Inverse Document Freq (IDF): idf(t) = log((N - df(t) + 0.5) / (df(t) + 0.5) + 1)
    BM25 score: Σ_t  idf(t) * tf(t,d) * (k1 + 1) / (tf(t,d) + k1 * (1 - b + b * dl/avgdl))
    Parameters: k1 = 1.5, b = 0.75 (BM25 standard defaults)

Tie-breaking in rrf_fuse: when two documents have equal RRF score, the one with the
lexicographically smaller id comes first (deterministic, documentable).
"""

import os
import re
import math
import pathlib
import json

# ---------------------------------------------------------------------------
# Lazy singletons — all None until first use
# ---------------------------------------------------------------------------
_embedder_instance = None
_collection_instance = None
_corpus_seeded = False  # tracks whether the corpus has been seeded this run

# ---------------------------------------------------------------------------
# Constants (mirrored from main.py; defined here to keep rag_engine self-contained)
# ---------------------------------------------------------------------------
EMBED_MODEL = "all-MiniLM-L6-v2"
CHROMA_PERSIST_DIR = ".chroma"
COLLECTION_NAME = "reactfirst_angles"

# RRF parameter (OQ-4 resolved — Stage 6)
RRF_K = 60

# Tier thresholds for fused RRF score (OQ-4 resolved — Stage 6)
# Calibrated for 2 rankers with k=60
TIER1_THRESHOLD = 0.025   # Critical Fit
TIER2_THRESHOLD = 0.015   # Strong Fit
TIER3_THRESHOLD = 0.005   # Watchlist / Speculative
# Below TIER3_THRESHOLD → Tier 4 No Match

# Semantic relevance floor (OQ-4 addendum — Stage 6 r1)
# If the best semantic result's cosine distance EXCEEDS this ceiling, the query has
# no meaningful overlap with the corpus and must return Tier 4 "No Match" regardless
# of the RRF rank score (which is always ≈ 0.033 for rank-1 with k=60, even for noise).
#
# Calibration (12-doc crisis corpus, all-MiniLM-L6-v2, hnsw:space="cosine"):
#   - distance = 1 - cosine_similarity (lower = more similar)
#   - Genuine crisis queries ("viral product recall backlash on social media"):
#       top semantic distance ≈ 0.10 – 0.45  → BELOW the ceiling → RRF score applies
#   - Nonsense / off-domain ("zxqw nonsense unrelated quantum gardening",
#     "underwater basket weaving supply chain"):
#       top semantic distance > 0.80         → ABOVE the ceiling → forced Tier 4
#   - Chosen ceiling 0.80 leaves a comfortable margin between the two populations.
#     The floor can ONLY push DOWN to Tier 4; it never upgrades a tier.
SEMANTIC_RELEVANCE_CEILING = 0.80   # cosine distance; above this → Tier 4 "No Match"

# BM25 parameters (standard defaults)
_BM25_K1 = 1.5
_BM25_B = 0.75

# Corpus file (internal RAG asset — not one of the 3 bounded runtime inputs)
_CORPUS_FILENAME = "angle_corpus.json"


# ---------------------------------------------------------------------------
# Private lazy getters
# ---------------------------------------------------------------------------

def _get_embedder():
    """Return the SentenceTransformer embedder, loading the model on first call.

    Import-safe: the model is NOT loaded at import time.
    """
    global _embedder_instance
    if _embedder_instance is None:
        from sentence_transformers import SentenceTransformer  # lazy import
        _embedder_instance = SentenceTransformer(EMBED_MODEL)
    return _embedder_instance


def _get_collection():
    """Return the ChromaDB collection, building/opening it on first call.

    Persists under .chroma/ relative to the cwd.
    Import-safe: Chroma is NOT opened at import time.

    RAG1: collection builds on first use and persists under .chroma/.
    """
    global _collection_instance
    if _collection_instance is None:
        import chromadb  # lazy import
        persist_path = str(pathlib.Path(os.getcwd()) / CHROMA_PERSIST_DIR)
        client = chromadb.PersistentClient(path=persist_path)
        _collection_instance = client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
    return _collection_instance


# ---------------------------------------------------------------------------
# BM25 helpers (pure Python, no external deps)
# ---------------------------------------------------------------------------

def _tokenize(text: str) -> list:
    """Lowercase word tokenizer (split on non-alphanumeric).

    Args:
        text: input string.

    Returns:
        List of lowercase token strings.
    """
    return re.findall(r"[a-z0-9]+", text.lower())


def _compute_idf(tokenized_corpus: list) -> dict:
    """Compute IDF scores for all terms in a corpus.

    IDF formula: log((N - df + 0.5) / (df + 0.5) + 1)
    where N = number of documents, df = number of docs containing the term.

    Args:
        tokenized_corpus: list of token lists (one per document).

    Returns:
        Dict mapping term -> IDF score.
    """
    n = len(tokenized_corpus)
    df = {}
    for tokens in tokenized_corpus:
        for term in set(tokens):
            df[term] = df.get(term, 0) + 1
    idf = {}
    for term, freq in df.items():
        idf[term] = math.log((n - freq + 0.5) / (freq + 0.5) + 1)
    return idf


def _bm25_score(query_tokens: list, doc_tokens: list, idf: dict,
                avg_dl: float, k1: float = _BM25_K1, b: float = _BM25_B) -> float:
    """Compute BM25 score for one document given a query.

    BM25(d,q) = Σ_t idf(t) * tf(t,d)*(k1+1) / (tf(t,d) + k1*(1 - b + b*dl/avgdl))

    Args:
        query_tokens: tokenized query terms.
        doc_tokens:   tokenized document terms.
        idf:          IDF dict for the corpus.
        avg_dl:       average document length in tokens.
        k1, b:        BM25 parameters.

    Returns:
        BM25 score (float >= 0).
    """
    dl = len(doc_tokens)
    tf_counts: dict = {}
    for t in doc_tokens:
        tf_counts[t] = tf_counts.get(t, 0) + 1

    score = 0.0
    for term in query_tokens:
        if term not in idf:
            continue
        tf = tf_counts.get(term, 0)
        numerator = tf * (k1 + 1)
        denominator = tf + k1 * (1.0 - b + b * (dl / avg_dl))
        score += idf[term] * (numerator / denominator)
    return score


# ---------------------------------------------------------------------------
# Corpus seeding (lazy, idempotent)
# ---------------------------------------------------------------------------

def seed_corpus_if_empty():
    """Seed the synthetic crisis-case-study corpus into Chroma on first use.

    Idempotent: checks the collection count before inserting.
    Import-safe: nothing called at module import time.

    The corpus is loaded from angle_corpus.json (relative to cwd),
    an internal RAG asset (NOT one of the 3 bounded runtime inputs).
    """
    global _corpus_seeded
    if _corpus_seeded:
        return  # already seeded this Python session

    collection = _get_collection()
    # Check if already populated (idempotent across runs)
    if collection.count() > 0:
        _corpus_seeded = True
        return

    corpus_path = pathlib.Path(os.getcwd()) / _CORPUS_FILENAME
    if not corpus_path.exists():
        # Corpus file absent — skip seeding (tests may inject their own corpus)
        return

    with open(str(corpus_path), "r", encoding="utf-8") as f:
        corpus = json.load(f)

    documents = [entry["text"] for entry in corpus]
    ids = [entry["id"] for entry in corpus]
    metadatas = [
        {
            "angle_key": entry.get("angle_key", entry["id"]),
            "category_hint": entry.get("category_hint", ""),
            "tier_label": entry.get("tier_label", ""),
        }
        for entry in corpus
    ]

    upsert_documents(documents, ids, metadatas)
    _corpus_seeded = True


# ---------------------------------------------------------------------------
# Public API — used by main.py's match_solicitation_angle (tool 6)
# ---------------------------------------------------------------------------

def embed_texts(texts: list) -> list:
    """Embed a list of strings using all-MiniLM-L6-v2.

    Returns a list of embedding vectors (list[list[float]]).
    Triggers the model load on first call.
    """
    embedder = _get_embedder()
    return embedder.encode(texts, convert_to_numpy=True).tolist()


def upsert_documents(documents: list, ids: list, metadatas: list = None):
    """Upsert documents into the Chroma collection.

    Args:
        documents: list of text strings to embed and store.
        ids:       unique string IDs, one per document.
        metadatas: optional list of dicts (one per document).
    """
    collection = _get_collection()
    embedder = _get_embedder()
    embeddings = embedder.encode(documents, convert_to_numpy=True).tolist()
    collection.upsert(
        documents=documents,
        embeddings=embeddings,
        ids=ids,
        metadatas=metadatas or [{} for _ in documents],
    )


def semantic_query(query_text: str, n_results: int = 10) -> list:
    """Semantic search in the Chroma collection.

    Returns a ranked list of dicts: [{"id", "document", "distance", "metadata"}, ...].
    Triggers model + Chroma load on first call.
    Returns [] if the collection is empty (no documents to query against).
    """
    collection = _get_collection()
    if collection.count() == 0:
        return []
    embedder = _get_embedder()
    query_embedding = embedder.encode([query_text], convert_to_numpy=True).tolist()[0]
    # n_results cannot exceed the number of documents in the collection
    actual_n = min(n_results, collection.count())
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=actual_n,
        include=["documents", "distances", "metadatas"],
    )
    output = []
    if results and results.get("ids"):
        for i, doc_id in enumerate(results["ids"][0]):
            output.append({
                "id": doc_id,
                "document": results["documents"][0][i],
                "distance": results["distances"][0][i],
                "metadata": results["metadatas"][0][i] if results.get("metadatas") else {},
            })
    return output


def bm25_query(query_text: str, documents: list, doc_ids: list, n_results: int = 10) -> list:
    """BM25 exact-match ranking over a list of documents.

    Pure in-memory — does NOT use Chroma. Independent of the semantic path (RAG3).

    Formula: BM25(d,q) = Σ_t idf(t) * tf(t,d)*(k1+1) / (tf(t,d) + k1*(1 - b + b*dl/avgdl))
    Parameters: k1 = 1.5 (term saturation), b = 0.75 (length normalization).
    IDF: log((N - df + 0.5) / (df + 0.5) + 1).

    Args:
        query_text:  the query string to match.
        documents:   list of document strings to rank.
        doc_ids:     list of unique IDs, one per document (parallel to documents).
        n_results:   maximum number of results to return.

    Returns:
        Ranked list of dicts: [{"id", "document", "score"}, ...]  (highest score first).
        Documents with score 0.0 are excluded from the result.
        Returns an empty list if documents is empty or no query terms match.
    """
    if not documents or not query_text:
        return []
    if len(documents) != len(doc_ids):
        raise ValueError(
            f"bm25_query: len(documents)={len(documents)} != len(doc_ids)={len(doc_ids)}"
        )

    # Tokenize all documents
    tokenized_corpus = [_tokenize(doc) for doc in documents]
    # Average document length
    lengths = [len(toks) for toks in tokenized_corpus]
    avg_dl = sum(lengths) / len(lengths) if lengths else 1.0
    # Compute IDF over the corpus
    idf = _compute_idf(tokenized_corpus)
    # Tokenize query
    query_tokens = _tokenize(query_text)

    if not query_tokens:
        return []

    # Score each document
    scored = []
    for idx, (doc, doc_id) in enumerate(zip(documents, doc_ids)):
        score = _bm25_score(query_tokens, tokenized_corpus[idx], idf, avg_dl)
        if score > 0.0:
            scored.append({"id": doc_id, "document": doc, "score": score})

    # Sort highest first, then by id for deterministic ties
    scored.sort(key=lambda x: (-x["score"], x["id"]))
    return scored[:n_results]


def rrf_fuse(semantic_results: list, bm25_results: list, k: int = RRF_K) -> list:
    """Fuse semantic and BM25 ranked lists using Reciprocal Rank Fusion.

    Formula: RRF(d) = Σ_rankers  1 / (k + rank_r(d))
    where rank is 1-based and k = 60 (standard default, OQ-4 resolved Stage 6).

    A document that appears in only one ranked list still gets credit from
    that list's rank; its contribution from the absent list is 0.

    Deterministic tie-breaking: equal RRF score → lexicographically smaller id
    comes first (documented).

    Args:
        semantic_results: ranked list from semantic_query (or any ranker returning
                          [{"id", ...}, ...] in ranked order, index 0 = best).
        bm25_results:     ranked list from bm25_query (same shape).
        k:                RRF smoothing constant (default 60).

    Returns:
        Fused ranked list: [{"id", "rrf_score", "semantic_rank", "bm25_rank"}, ...]
        sorted by rrf_score descending, then by id ascending for ties.
        Returns empty list if both inputs are empty.
    """
    if not semantic_results and not bm25_results:
        return []

    # Build rank lookup for each ranker (rank is 1-based)
    # semantic rank: position in semantic_results (0-indexed list → rank = idx+1)
    semantic_rank: dict = {}
    for idx, item in enumerate(semantic_results):
        doc_id = item.get("id", "")
        if doc_id:
            semantic_rank[doc_id] = idx + 1  # 1-based

    # BM25 rank: position in bm25_results (0-indexed list → rank = idx+1)
    bm25_rank: dict = {}
    for idx, item in enumerate(bm25_results):
        doc_id = item.get("id", "")
        if doc_id:
            bm25_rank[doc_id] = idx + 1  # 1-based

    # Union of all document IDs
    all_ids = set(semantic_rank.keys()) | set(bm25_rank.keys())

    # Compute RRF score for each document
    fused = []
    for doc_id in all_ids:
        sem_r = semantic_rank.get(doc_id)
        bm25_r = bm25_rank.get(doc_id)
        score = 0.0
        if sem_r is not None:
            score += 1.0 / (k + sem_r)
        if bm25_r is not None:
            score += 1.0 / (k + bm25_r)
        fused.append({
            "id": doc_id,
            "rrf_score": score,
            "semantic_rank": sem_r,
            "bm25_rank": bm25_r,
        })

    # Sort by rrf_score descending; ties broken by id ascending (deterministic)
    fused.sort(key=lambda x: (-x["rrf_score"], x["id"]))
    return fused


def score_to_tier(rrf_score: float) -> int:
    """Map a fused RRF score to an outreach priority tier.

    Thresholds (OQ-4 resolved — Stage 6, calibrated for 2 rankers, k=60):
        Tier 1 (Critical Fit):   score >= 0.025
        Tier 2 (Strong Fit):     score >= 0.015
        Tier 3 (Watchlist):      score >= 0.005
        Tier 4 (No Match):       score <  0.005  → routes to Policy-6 fallback

    NOTE: This function only applies when the semantic relevance floor has been
    cleared (see check_semantic_relevance). The floor can only push DOWN to Tier 4;
    it never upgrades a tier.

    Args:
        rrf_score: the top fused RRF score.

    Returns:
        Integer tier ∈ {1, 2, 3, 4}.
    """
    if rrf_score >= TIER1_THRESHOLD:
        return 1
    elif rrf_score >= TIER2_THRESHOLD:
        return 2
    elif rrf_score >= TIER3_THRESHOLD:
        return 3
    else:
        return 4


def check_semantic_relevance(semantic_results: list) -> bool:
    """Check whether the top semantic result is within the relevance ceiling.

    Uses SEMANTIC_RELEVANCE_CEILING (0.80 cosine distance) as the gate.
    With hnsw:space="cosine", distance = 1 - cosine_similarity; smaller = more similar.

    If the top semantic result's distance EXCEEDS the ceiling, the query has no
    meaningful overlap with the corpus (e.g. nonsense/off-domain query) and
    match_solicitation_angle must return Tier 4 regardless of the RRF score.

    The floor can only push DOWN to Tier 4 — it NEVER upgrades a tier.

    Args:
        semantic_results: ranked list from semantic_query (or []).

    Returns:
        True  — the best semantic distance is WITHIN the ceiling → proceed to RRF tier.
        False — the best semantic distance EXCEEDS the ceiling → force Tier 4 "No Match".
    """
    if not semantic_results:
        # No results at all → no relevant match
        return False
    best_distance = semantic_results[0].get("distance", 1.0)
    return best_distance <= SEMANTIC_RELEVANCE_CEILING
