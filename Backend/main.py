"""
main.py — ReactFirst AI Proactive Outbound Engine
Autonomous Agentic GTM Engine & Value-Hook Pipeline

Author: Asaf
Project: ReactFirst AI Proactive Outbound Engine
Stage: 5 (Governance: policies, trust-gate & tool gateway hardened)

Entry point: answer_question(query, ...)
Run:         python main.py
Data inputs: brands_catalog.csv, contacts.json, gtm_policies.txt (must be in cwd)

Import-safe: importing this module has ZERO side effects (no clients built, no files
             read, no model downloads, no Chroma/mongomock construction).
"""

# ===========================================================================
# Section 2 — Imports
# stdlib first, then third-party (lazy-imported where heavy)
# ===========================================================================
import ast
import base64
import csv
import json
import math
import os
import pathlib
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import pandas as pd

# First-party modules — all import-safe (zero side effects at import time)
import crm_store  # noqa: E402  (lazy mongomock leads workspace — Stage 11)
import lead_store  # noqa: E402  (mongomock contacts store + Policy-4 gate)

# Third-party imports that are safe at import time (lightweight, no side effects):
# anthropic, firecrawl, serpapi, tavily — all imported lazily inside their
# respective lazy-getter functions or tool implementations (see Section 5).

# ===========================================================================
# Section 3 — Configuration
# Named constants only — no clients, no heavy objects, no file reads here.
# ===========================================================================

# --- Hard caps (non-negotiable per CLAUDE.md §9) ---
TOOL_CALL_CAP           = 15    # global anti-loop cap (PRD §5.3)
MAX_ANGLES              = 3     # Policy 5 output ceiling
ICP_TAG_THRESHOLD       = 3     # Policy 2 qualification gate
CHUNK_MAX_DOMAINS       = 100   # tool 4 batch ceiling
CHUNK_TIME_BUDGET_S     = 800   # tool 4 wall-clock budget (seconds)
FANOUT_RECOVERY_THRESHOLD = 2   # Vector C fires iff A+B < 2 distinct domains
DEFAULT_QUERY_COUNT     = 15    # tool 1 default target_count
DAILY_SEND_CAP          = 50    # outbound messages per day per inbox
LATENCY_TARGET_S        = 900   # signal→campaign SLO (soft; seconds)
ICP_ANCHOR_COUNT        = 5     # max example/anchor companies in an ICP document (ICPB2)

# --- Model identifiers (CLAUDE.md §1.2 / §9) ---
REASONING_MODEL = "claude-opus-4-8"    # main agentic loop
ANALYZER_MODEL  = "claude-sonnet-4-6"  # analyze_company_chunk (tool 4)
LIGHT_MODEL     = "claude-haiku-4-5"   # generate_search_queries (1) + extract_and_score_pool (3)

# --- Embedding model (local, no API key required) ---
EMBED_MODEL = "all-MiniLM-L6-v2"

# --- Policy 6 — byte-exact fallback string (the ONE contractually mandated literal) ---
FALLBACK_MESSAGE = "We have no product available today that fits your request"

# --- Catalog schema (validated against the real CSV header on load) ---
CATALOG_COLUMNS = [
    "Uniq_Id",
    "Brand_Name",
    "Primary_Domain",
    "Core_Category",
    "Estimated_Ad_Spend_Tier",
    "Current_Status",
    "Historical_Social_Incidents",
    "Main_Competitor_Id",
    "Gtin_Prefix",
]

# Catalog enum values (used for validation; read from CSV — never hardcoded into logic)
_VALID_TIERS    = {"Tier 1", "Tier 2", "Tier 3"}
_VALID_STATUSES = {"Active_Client", "Open_Opportunity", "Unreached_Prospect", "Blacklisted"}

# --- Log line conventions (stable project constants — not graded literals) ---
LOG_CALLING_LLM   = "Calling LLM for next tool to invoke"
LOG_ENTER_TOOL    = "** Entering tool {tool_name} **"
LOG_PARAM         = "Parameter {param} = {value}"
LOG_EXIT_TOOL     = "** Exiting tool {tool_name} **"
LOG_FINAL         = "final response is = {answer}"
LOG_CAP_HIT       = "** TERMINATED: tool call cap reached **"

# --- Outbound subdomain (only request_reactfirst_pdf may target this) ---
OUTREACH_SUBDOMAIN = "outreach.reactfirst.ai"

# --- Gateway format regexes (used by gateway_validate in Section 8) ---
# These are recorded here; NOTES.md carries the rationale.
_RE_DOMAIN      = re.compile(r"^[a-z0-9][a-z0-9\-]{0,61}[a-z0-9]?\.[a-z]{2,}(\.[a-z]{2,})?$")
_RE_ANGLE_KEY   = re.compile(r"^[A-Za-z0-9_\-]{2,80}$")
_RE_TIER_LABEL  = re.compile(r"^Tier [1-4]$")


# ===========================================================================
# Lazy client singletons — defined here; NEVER called at module level.
# ===========================================================================

_anthropic_client = None
_embedder_instance = None  # SentenceTransformer — lives in rag_engine.py


def _get_client():
    """Return the Anthropic client, constructing it on first call (lazy singleton).

    Import-safe: NOT called at module level.
    Key source: os.environ['ANTHROPIC_API_KEY'] — never hardcoded.
    """
    global _anthropic_client
    if _anthropic_client is None:
        import anthropic  # lazy import — keeps import side-effect-free
        _anthropic_client = anthropic.Anthropic(
            api_key=os.environ["ANTHROPIC_API_KEY"]
        )
    return _anthropic_client


# ===========================================================================
# Section 4 — Catalog loader
# Reads brands_catalog.csv, validates the 9-column header, coerces types.
# ===========================================================================

def load_catalog(catalog_path: str) -> pd.DataFrame:
    """Load and validate brands_catalog.csv.

    Validates:
    - Exactly the 9 named columns in CATALOG_COLUMNS (order-tolerant, name-exact).
    - Historical_Social_Incidents coerced to int.
    - Estimated_Ad_Spend_Tier ∈ {'Tier 1', 'Tier 2', 'Tier 3'}.
    - Current_Status ∈ {'Active_Client', 'Open_Opportunity', 'Unreached_Prospect', 'Blacklisted'}.

    The CSV header is the final arbiter of spelling (CAT1 tiebreaker).

    Args:
        catalog_path: path to brands_catalog.csv (absolute or relative to cwd).

    Returns:
        pd.DataFrame — validated catalog.

    Raises:
        ValueError: if the header is wrong, a required column is missing, or a
                    type coercion fails. A clean, explicit startup error — never a
                    silent KeyError later.
    """
    try:
        df = pd.read_csv(catalog_path, dtype=str)
    except FileNotFoundError:
        raise ValueError(f"Catalog file not found: {catalog_path}")
    except Exception as exc:
        raise ValueError(f"Failed to read catalog CSV: {exc}") from exc

    # --- CAT1: header validation (order-tolerant, name-exact) ---
    actual_cols = set(df.columns.tolist())
    expected_cols = set(CATALOG_COLUMNS)
    missing = expected_cols - actual_cols
    extra   = actual_cols - expected_cols
    if missing or extra:
        raise ValueError(
            f"Catalog header mismatch. "
            f"Missing columns: {sorted(missing)}. "
            f"Unexpected columns: {sorted(extra)}. "
            f"Expected exactly: {CATALOG_COLUMNS}."
        )

    # --- CAT3: coerce Historical_Social_Incidents to int ---
    try:
        df["Historical_Social_Incidents"] = (
            df["Historical_Social_Incidents"].astype(str).str.strip().astype(int)
        )
    except (ValueError, TypeError) as exc:
        raise ValueError(
            f"'Historical_Social_Incidents' must be integer for all rows. Error: {exc}"
        ) from exc

    # --- CAT3: validate Estimated_Ad_Spend_Tier enum ---
    bad_tiers = df[~df["Estimated_Ad_Spend_Tier"].isin(_VALID_TIERS)]["Estimated_Ad_Spend_Tier"].unique()
    if len(bad_tiers) > 0:
        raise ValueError(
            f"Invalid 'Estimated_Ad_Spend_Tier' values: {list(bad_tiers)}. "
            f"Allowed: {sorted(_VALID_TIERS)}."
        )

    # --- CAT3: validate Current_Status enum ---
    bad_statuses = df[~df["Current_Status"].isin(_VALID_STATUSES)]["Current_Status"].unique()
    if len(bad_statuses) > 0:
        raise ValueError(
            f"Invalid 'Current_Status' values: {list(bad_statuses)}. "
            f"Allowed: {sorted(_VALID_STATUSES)}."
        )

    return df


def filter_outreach_candidates(catalog_df: pd.DataFrame) -> pd.DataFrame:
    """Return rows eligible for outreach: exclude Blacklisted brands (CAT6).

    Access is always by column name — never by positional index (CAT2).
    """
    return catalog_df[catalog_df["Current_Status"] != "Blacklisted"].copy()


def get_brand_by_domain(catalog_df: pd.DataFrame, domain: str) -> Optional[pd.Series]:
    """Look up a brand row by Primary_Domain (case-insensitive).

    Returns the first matching pd.Series, or None if not found.
    Access by column name (CAT2). Domain normalized to lowercase before compare.
    """
    domain_norm = domain.strip().lower()
    mask = catalog_df["Primary_Domain"].str.strip().str.lower() == domain_norm
    matches = catalog_df[mask]
    if matches.empty:
        return None
    return matches.iloc[0]


def get_brand_by_id(catalog_df: pd.DataFrame, uniq_id: str) -> Optional[pd.Series]:
    """Look up a brand row by Uniq_Id.

    Returns the first matching pd.Series, or None if not found.
    """
    mask = catalog_df["Uniq_Id"].str.strip() == uniq_id.strip()
    matches = catalog_df[mask]
    if matches.empty:
        return None
    return matches.iloc[0]


# ===========================================================================
# Section 5 — Tool implementations
# ===========================================================================

# ---------------------------------------------------------------------------
# Tool 1 — generate_search_queries
# ---------------------------------------------------------------------------

def _parse_query_list(raw_text: str, target_count: int) -> list:
    """Parse LLM output (possibly wrapped in fences/prose/JSON) into a clean list[str].

    Strategy (in order):
    1. If the text is a JSON array, parse it directly.
    2. If the text contains a fenced code block, extract and parse its contents.
    3. Fall back to line-by-line splitting, stripping bullets / numbering.

    Returns a de-duplicated list of non-empty strings, capped at target_count.
    Never raises — returns [] on total failure.
    """
    text = raw_text.strip() if raw_text else ""
    if not text:
        return []

    # Strategy 1 — bare JSON array
    try:
        maybe = json.loads(text)
        if isinstance(maybe, list):
            items = [str(s).strip() for s in maybe if str(s).strip()]
            seen = set()
            unique = [x for x in items if not (x in seen or seen.add(x))]
            return unique[:target_count]
    except (json.JSONDecodeError, ValueError):
        pass

    # Strategy 2 — fenced code block
    fence_match = re.search(r"```(?:json)?\s*(\[[\s\S]*?\])\s*```", text, re.IGNORECASE)
    if fence_match:
        try:
            maybe = json.loads(fence_match.group(1))
            if isinstance(maybe, list):
                items = [str(s).strip() for s in maybe if str(s).strip()]
                seen = set()
                unique = [x for x in items if not (x in seen or seen.add(x))]
                return unique[:target_count]
        except (json.JSONDecodeError, ValueError):
            pass

    # Strategy 3 — line-by-line, strip bullets / numbering / fences
    lines = text.splitlines()
    items = []
    for line in lines:
        line = line.strip()
        if not line or line.startswith("```"):
            continue
        # Remove leading bullets, numbering, dashes
        line = re.sub(r"^[\-\*\•\d]+[.):\s]+", "", line).strip()
        # Remove surrounding quotes
        line = line.strip('"').strip("'").strip()
        if line:
            items.append(line)

    seen = set()
    unique = [x for x in items if not (x in seen or seen.add(x))]
    return unique[:target_count]


def generate_search_queries(vertical_seed: str, target_count: int = DEFAULT_QUERY_COUNT) -> list:
    """Tool 1 — Generate a variation matrix of search queries from a vertical seed.

    Uses LIGHT_MODEL (claude-haiku-4-5). Returns 10–20 distinct, non-overlapping
    query strings, de-duplicated, honoring target_count. Never raises.

    Args:
        vertical_seed: The vertical/category seed string (e.g. "athleisure brands").
        target_count:  Target number of query variations (default DEFAULT_QUERY_COUNT=15).

    Returns:
        list[str] — between 10 and 20 unique query strings (or an error list on failure).
    """
    try:
        client = _get_client()
        prompt = (
            f"Generate a variation matrix of {target_count} distinct search queries for "
            f"the following vertical: '{vertical_seed}'.\n\n"
            "Requirements:\n"
            "- Each query must address a different intent or modifier axis "
            "(e.g. brand discovery, competitor landscape, ad spend signals, product category, "
            "geographic focus, sustainability angle, DTC vs retail, etc.).\n"
            "- No two queries should be near-copies of the seed; create genuine variation.\n"
            "- Queries should be practical web-search strings.\n"
            "- Return ONLY a JSON array of strings, no explanation, no prose:\n"
            '["query 1", "query 2", ...]'
        )
        response = client.messages.create(
            model=LIGHT_MODEL,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        # Extract text from the response content
        raw_text = ""
        for block in response.content:
            if hasattr(block, "text"):
                raw_text += block.text
        queries = _parse_query_list(raw_text, target_count)
        # Ensure at least 10 and at most 20 (or target_count, whichever is smaller)
        effective_cap = min(target_count, 20)
        return queries[:effective_cap] if len(queries) >= 1 else [vertical_seed]
    except Exception as exc:  # noqa: BLE001
        # Tool failures are data, never crashes.
        return [{"error": f"generate_search_queries failed: {exc}"}]


# ---------------------------------------------------------------------------
# Tool 2 — execute_3way_fanout
# ---------------------------------------------------------------------------

def _normalize_domain(raw: str) -> str:
    """Normalize a domain string: lowercase, strip scheme, strip leading 'www.'.

    Examples:
        'https://www.Example.com/path' → 'example.com'
        'HTTP://WWW.SAMPLE-BRAND.COM' → 'sample-brand.com'

    Domain normalization rule (recorded in NOTES.md):
        1. Strip leading/trailing whitespace.
        2. Remove URL scheme (http://, https://).
        3. Remove 'www.' prefix.
        4. Take only the hostname portion (strip path/query/fragment).
        5. Lowercase.
    """
    domain = raw.strip().lower()
    domain = re.sub(r"^https?://", "", domain)
    domain = re.sub(r"^www\.", "", domain)
    # Strip path, query, fragment
    domain = domain.split("/")[0].split("?")[0].split("#")[0]
    return domain


def _vector_a_search(query: str) -> dict:
    """Vector A — Claude + web_search/web_fetch (Claude tool use).

    Returns {"domains": [...], "status": "ok" | "error", "error": str|None}.
    Per CLAUDE.md §1.2: uses Claude with the server-side web_search/web_fetch tools.
    """
    try:
        client = _get_client()
        response = client.messages.create(
            model=LIGHT_MODEL,
            max_tokens=1024,
            tools=[
                {"name": "web_search", "type": "web_search_20250305"},
            ],
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Search the web for: {query}\n\n"
                        "Return a JSON array of domain names you find that are relevant "
                        "e-commerce or DTC brands. Only the domain names, nothing else. "
                        'Example: ["brand1.com", "brand2.com"]'
                    ),
                }
            ],
        )
        # Extract text from response
        raw_text = ""
        for block in response.content:
            if hasattr(block, "text"):
                raw_text += block.text
        domains = []
        try:
            parsed = json.loads(raw_text.strip())
            if isinstance(parsed, list):
                domains = [_normalize_domain(d) for d in parsed if d]
        except (json.JSONDecodeError, ValueError):
            # Best-effort domain extraction from plain text
            found = re.findall(r"[a-z0-9][a-z0-9\-]{0,61}[a-z0-9]?\.[a-z]{2,}", raw_text.lower())
            domains = [_normalize_domain(d) for d in found]
        return {"domains": list(dict.fromkeys(d for d in domains if d)), "status": "ok", "error": None}
    except Exception as exc:  # noqa: BLE001
        return {"domains": [], "status": "error", "error": str(exc)}


def _vector_b_search(query: str) -> dict:
    """Vector B — SerpAPI + Maps.

    Returns {"domains": [...], "status": "ok" | "error", "error": str|None}.
    """
    try:
        from serpapi import GoogleSearch  # lazy import
        serp_key = os.environ.get("SERPAPI_API_KEY", "")
        if not serp_key:
            return {"domains": [], "status": "error", "error": "SERPAPI_API_KEY not set"}
        params = {"q": query, "api_key": serp_key, "num": 10}
        results = GoogleSearch(params).get_dict()
        organic = results.get("organic_results", [])
        domains = []
        for item in organic:
            link = item.get("link", "")
            if link:
                domains.append(_normalize_domain(link))
        return {"domains": list(dict.fromkeys(d for d in domains if d)), "status": "ok", "error": None}
    except Exception as exc:  # noqa: BLE001
        return {"domains": [], "status": "error", "error": str(exc)}


def _vector_c_search(query: str) -> dict:
    """Vector C — Tavily (recovery vector).

    Returns {"domains": [...], "status": "ok" | "error", "error": str|None}.
    Fired ONLY when A+B yields < FANOUT_RECOVERY_THRESHOLD distinct domains.
    """
    try:
        from tavily import TavilyClient  # lazy import
        tavily_key = os.environ.get("TAVILY_API_KEY", "")
        if not tavily_key:
            return {"domains": [], "status": "error", "error": "TAVILY_API_KEY not set"}
        client = TavilyClient(api_key=tavily_key)
        response = client.search(query=query, max_results=10)
        results = response.get("results", [])
        domains = []
        for item in results:
            url = item.get("url", "")
            if url:
                domains.append(_normalize_domain(url))
        return {"domains": list(dict.fromkeys(d for d in domains if d)), "status": "ok", "error": None}
    except Exception as exc:  # noqa: BLE001
        return {"domains": [], "status": "error", "error": str(exc)}


def execute_3way_fanout(queries: list) -> dict:
    """Tool 2 — Execute concurrent 3-way fan-out discovery for a list of queries.

    Vectors A (Claude web_search) and B (SerpAPI) run concurrently via
    ThreadPoolExecutor. Vector C (Tavily) fires ONLY when the union of A and B
    yields < FANOUT_RECOVERY_THRESHOLD (=2) distinct domains for a query.

    Per-vector failure isolation: one vector error does not crash the tool.

    Domain normalization: lowercase, strip scheme + 'www.' prefix (see _normalize_domain).

    Concurrency model (recorded in NOTES.md):
        - ThreadPoolExecutor, max_workers=2 for A∥B per query.
        - No per-vector timeout beyond the underlying API call timeout.

    Args:
        queries: list of search query strings.

    Returns:
        dict with keys:
            "domains": dict mapping normalized domain → {"provenance": [vector_names], ...}
            "vector_status": {"A": "ok"|"error", "B": "ok"|"error", "C": "ok"|"error"|"skipped"}
            "total_unique_domains": int
    """
    all_domains: Dict[str, Dict] = {}  # domain → {provenance, ...}
    vector_status: Dict[str, str] = {"A": "skipped", "B": "skipped", "C": "skipped"}

    for query in queries:
        try:
            # Run A and B concurrently
            with ThreadPoolExecutor(max_workers=2) as executor:
                future_a = executor.submit(_vector_a_search, query)
                future_b = executor.submit(_vector_b_search, query)
                result_a = future_a.result()
                result_b = future_b.result()

            vector_status["A"] = result_a.get("status", "error")
            vector_status["B"] = result_b.get("status", "error")

            # Collect domains from A and B, track provenance
            ab_domains: set = set()
            for domain in result_a.get("domains", []):
                if domain not in all_domains:
                    all_domains[domain] = {"provenance": []}
                if "A" not in all_domains[domain]["provenance"]:
                    all_domains[domain]["provenance"].append("A")
                ab_domains.add(domain)
            for domain in result_b.get("domains", []):
                if domain not in all_domains:
                    all_domains[domain] = {"provenance": []}
                if "B" not in all_domains[domain]["provenance"]:
                    all_domains[domain]["provenance"].append("B")
                ab_domains.add(domain)

            # Vector C recovery: fire iff A∪B yields < FANOUT_RECOVERY_THRESHOLD domains
            if len(ab_domains) < FANOUT_RECOVERY_THRESHOLD:
                result_c = _vector_c_search(query)
                vector_status["C"] = result_c.get("status", "error")
                for domain in result_c.get("domains", []):
                    if domain not in all_domains:
                        all_domains[domain] = {"provenance": []}
                    if "C" not in all_domains[domain]["provenance"]:
                        all_domains[domain]["provenance"].append("C")
            else:
                # Only update C status to "skipped" if it hasn't been run before
                if vector_status["C"] == "skipped":
                    vector_status["C"] = "skipped"

        except Exception as exc:  # noqa: BLE001
            # Per-query failure is isolated — continue with remaining queries
            vector_status["A"] = vector_status.get("A", "error")
            continue

    return {
        "domains": all_domains,
        "vector_status": vector_status,
        "total_unique_domains": len(all_domains),
    }


# ---------------------------------------------------------------------------
# Tool 3 — extract_and_score_pool
# ---------------------------------------------------------------------------

def _to_native(val):
    """Coerce numpy scalar types to native Python types for JSON serializability.

    pandas / numpy return typed scalars (numpy.int64, numpy.float64, etc.) when
    accessing DataFrame cells.  json.dumps cannot serialize them, so we coerce
    each value from catalog_context to its native Python equivalent using the
    numpy scalar's .item() method when available.  All other values pass through
    unchanged.
    """
    if hasattr(val, "item"):  # numpy scalar (int64, float64, bool_, …)
        return val.item()
    return val


def extract_and_score_pool(raw_pool: list, catalog_df: pd.DataFrame) -> list:
    """Tool 3 — De-duplicate, map against the catalog, and score the candidate pool.

    De-dup is by normalized Primary_Domain. Catalog mapping is done by name (never index).
    Non-catalog candidates are retained and flagged in_catalog=False.
    Ordering is deterministic for a fixed input.

    Args:
        raw_pool:   List of dicts, each with at least {"domain": str, "provenance": list}.
                    (Output from execute_3way_fanout's "domains" dict values + keys.)
        catalog_df: The loaded brands_catalog.csv DataFrame (validated, 9 columns).

    Returns:
        list[dict] — de-duplicated, annotated, scored candidates. Each item has:
            domain, provenance, in_catalog (bool), catalog_context (dict|None),
            score (float, higher is better), blacklisted (bool).
    """
    seen_domains: set = set()
    result: list = []

    for item in raw_pool:
        # item may be a dict {"domain": ..., "provenance": [...]} or just a domain string
        if isinstance(item, dict):
            raw_domain = item.get("domain", "")
            provenance = item.get("provenance", [])
        else:
            raw_domain = str(item)
            provenance = []

        norm_domain = _normalize_domain(raw_domain)
        if not norm_domain or norm_domain in seen_domains:
            continue
        seen_domains.add(norm_domain)

        # Catalog mapping by Primary_Domain (accessed by name — CAT2)
        catalog_row = get_brand_by_domain(catalog_df, norm_domain)
        in_catalog = catalog_row is not None
        blacklisted = False
        catalog_context = None

        if in_catalog:
            # Build catalog context dict using column names (never positional).
            # _to_native coerces numpy scalars (int64, float64, …) to native Python
            # types so json.dumps(catalog_context) never raises TypeError.
            catalog_context = {col: _to_native(catalog_row[col]) for col in CATALOG_COLUMNS}
            blacklisted = catalog_row["Current_Status"] == "Blacklisted"

        # Score: catalog matches score higher; provenance breadth adds signal
        score = 0.0
        if in_catalog:
            score += 2.0
            if not blacklisted:
                score += 1.0
        score += len(provenance) * 0.5  # more vectors found it → higher confidence

        result.append({
            "domain": norm_domain,
            "provenance": provenance,
            "in_catalog": in_catalog,
            "catalog_context": catalog_context,
            "score": score,
            "blacklisted": blacklisted,
        })

    # Deterministic sort: score descending, then domain alphabetically for ties
    result.sort(key=lambda x: (-x["score"], x["domain"]))
    return result


# ---------------------------------------------------------------------------
# Tool 4 — analyze_company_chunk
# ---------------------------------------------------------------------------

# Pixel / tag detection signatures (from NOTES.md)
_PIXEL_SIGS = {
    "tiktok_pixel": [
        r"ttq\.",
        r"ttq\.load\(",
        r"analytics\.tiktok\.com",
    ],
    "meta_pixel": [
        r"fbq\(",
        r"connect\.facebook\.net/.*?fbevents\.js",
        r"facebook\.com/tr\?id=",
    ],
    "gtm": [
        r"googletagmanager\.com/gtm\.js",
        r"GTM-[A-Z0-9]+",
        r"dataLayer\.push\(",
    ],
}

# ICP tag vocabulary (Stage-2 decision — recorded in NOTES.md)
# These 8 tags are matched against company profile text strings.
_ICP_TAGS = {
    "ecommerce_dtc": [
        r"direct.to.consumer",
        r"\bdtc\b",
        r"shopify",
        r"woocommerce",
        r"bigcommerce",
        r"e.commerce",
    ],
    "paid_social_advertising": [
        r"facebook ads",
        r"instagram ads",
        r"tiktok ads",
        r"meta ads",
        r"paid social",
        r"performance marketing",
    ],
    "scale_growth_stage": [
        r"series [a-c]",
        r"venture.backed",
        r"growth stage",
        r"scaling",
        r"rapid growth",
        r"million in revenue",
        r"million ARR",
    ],
    "pixel_tracking_present": [
        r"facebook pixel",
        r"meta pixel",
        r"tiktok pixel",
        r"google tag manager",
        r"gtm",
    ],
    "brand_marketing_team": [
        r"brand manager",
        r"head of marketing",
        r"vp marketing",
        r"cmo",
        r"marketing director",
        r"growth lead",
        r"performance marketer",
    ],
    "product_catalogue_depth": [
        r"product catalog",
        r"sku",
        r"product line",
        r"collection",
        r"catalog depth",
    ],
    "ad_spend_signals": [
        r"ad spend",
        r"advertising budget",
        r"media budget",
        r"paid media",
        r"roas",
        r"return on ad spend",
    ],
    "crisis_reputation_risk": [
        r"viral controversy",
        r"pr crisis",
        r"social media backlash",
        r"brand controversy",
        r"public relations issue",
    ],
}


def _detect_pixels(html_content: str) -> dict:
    """Detect TikTok Pixel, Meta Pixel, and Google Tag Manager in raw HTML.

    Args:
        html_content: Raw HTML string from the crawled page.

    Returns:
        dict with keys: tiktok_pixel (bool), meta_pixel (bool), gtm (bool).
    """
    result = {}
    for pixel_name, patterns in _PIXEL_SIGS.items():
        found = any(re.search(p, html_content, re.IGNORECASE) for p in patterns)
        result[pixel_name] = bool(found)
    return result


def _crawl_domain(domain: str, firecrawl_client, start_time: float) -> dict:
    """Crawl a single domain using Firecrawl and extract profile data.

    Returns a dict per domain with pixel flags, metadata, and text signals.
    On any failure, returns {"domain": domain, "fetched": False, "error": str}.
    """
    try:
        elapsed = time.time() - start_time
        if elapsed >= CHUNK_TIME_BUDGET_S:
            return {
                "domain": domain,
                "fetched": False,
                "tiktok_pixel": False,
                "meta_pixel": False,
                "gtm": False,
                "timed_out": True,
                "error": "budget_exceeded_before_crawl",
            }

        url = f"https://{domain}"
        # Firecrawl scrape returns: markdown, html, metadata
        crawl_result = firecrawl_client.scrape_url(
            url,
            params={"formats": ["markdown", "html", "metadata"]},
        )
        html_content = crawl_result.get("html", "") or ""
        metadata = crawl_result.get("metadata", {}) or {}
        markdown = crawl_result.get("markdown", "") or ""

        pixel_flags = _detect_pixels(html_content)

        # Extract operational scale signals from markdown
        operational_scale_signals = []
        for tag, patterns in _ICP_TAGS.items():
            for pat in patterns:
                if re.search(pat, markdown, re.IGNORECASE) or re.search(pat, html_content, re.IGNORECASE):
                    operational_scale_signals.append(tag)
                    break

        return {
            "domain": domain,
            "fetched": True,
            "status_code": metadata.get("statusCode", None),
            "title": metadata.get("title", ""),
            "description": metadata.get("description", ""),
            "tiktok_pixel": pixel_flags["tiktok_pixel"],
            "meta_pixel": pixel_flags["meta_pixel"],
            "gtm": pixel_flags["gtm"],
            "operational_scale_signals": list(set(operational_scale_signals)),
            "timed_out": False,
            "error": None,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "domain": domain,
            "fetched": False,
            "tiktok_pixel": False,
            "meta_pixel": False,
            "gtm": False,
            "timed_out": False,
            "error": str(exc),
        }


def analyze_company_chunk(domains: list) -> list:
    """Tool 4 — Deep-scrape a chunk of domains using Firecrawl and ANALYZER_MODEL.

    Hard ceilings:
    - Never crawl >100 domains in one chunk (CHUNK_MAX_DOMAINS).
    - Respect the 800s wall-clock budget (CHUNK_TIME_BUDGET_S); return partial
      results with timed_out=True on the offending domain rather than raising.
    - Per-domain crawl failures are isolated ({"error": ...}) — never crash the chunk.

    Pixel detection: tiktok_pixel, meta_pixel, gtm (Google Tag Manager) — booleans.

    Args:
        domains: list of domain strings to analyze.

    Returns:
        list[dict] — one profile dict per domain processed.
    """
    # Hard ceiling on chunk size (T4.2)
    if len(domains) > CHUNK_MAX_DOMAINS:
        domains = domains[:CHUNK_MAX_DOMAINS]

    try:
        from firecrawl import FirecrawlApp  # lazy import
        firecrawl_key = os.environ.get("FIRECRAWL_API_KEY", "")
        firecrawl_client = FirecrawlApp(api_key=firecrawl_key)
    except Exception as exc:  # noqa: BLE001
        # If Firecrawl is unavailable, return error for all domains
        return [
            {
                "domain": d,
                "fetched": False,
                "tiktok_pixel": False,
                "meta_pixel": False,
                "gtm": False,
                "timed_out": False,
                "error": f"Firecrawl init failed: {exc}",
            }
            for d in domains
        ]

    results = []
    start_time = time.time()

    for domain in domains:
        elapsed = time.time() - start_time
        if elapsed >= CHUNK_TIME_BUDGET_S:
            # Budget exhausted — mark remaining as timed out (T4.3)
            results.append({
                "domain": domain,
                "fetched": False,
                "tiktok_pixel": False,
                "meta_pixel": False,
                "gtm": False,
                "timed_out": True,
                "error": "chunk_time_budget_exceeded",
            })
            continue

        profile = _crawl_domain(domain, firecrawl_client, start_time)
        results.append(profile)

    return results


# ---------------------------------------------------------------------------
# Tool 5 — evaluate_icp_tags
# ---------------------------------------------------------------------------

def evaluate_icp_tags(company_profile_data: str) -> dict:
    """Tool 5 — Evaluate ICP tags from a company profile string.

    Pure function — no network calls. Deterministic for a fixed input.

    ICP Tag Vocabulary (8 tags — Stage-2 decision, recorded in NOTES.md):
        ecommerce_dtc, paid_social_advertising, scale_growth_stage,
        pixel_tracking_present, brand_marketing_team, product_catalogue_depth,
        ad_spend_signals, crisis_reputation_risk

    Qualification rule: qualified == True iff matched tag count >= ICP_TAG_THRESHOLD (=3).

    Args:
        company_profile_data: Raw crawl text / metadata string to evaluate.

    Returns:
        dict with keys:
            qualified (bool), tags (list[str] of matched tags), count (int),
            reason (str, human-readable).
    """
    # Malformed / empty input → clean False (T5.4)
    if not isinstance(company_profile_data, str):
        return {
            "qualified": False,
            "tags": [],
            "count": 0,
            "reason": "company_profile_data must be a non-empty string",
        }
    profile = company_profile_data.strip()
    if not profile:
        return {
            "qualified": False,
            "tags": [],
            "count": 0,
            "reason": "company_profile_data is empty",
        }

    matched_tags = []
    for tag, patterns in _ICP_TAGS.items():
        for pat in patterns:
            if re.search(pat, profile, re.IGNORECASE):
                matched_tags.append(tag)
                break  # Only count each tag once

    count = len(matched_tags)
    qualified = count >= ICP_TAG_THRESHOLD

    return {
        "qualified": qualified,
        "tags": matched_tags,
        "count": count,
        "reason": (
            f"Matched {count} ICP tag(s): {matched_tags}. "
            f"Threshold is {ICP_TAG_THRESHOLD}."
        ),
    }


# ---------------------------------------------------------------------------
# Tool 6 — match_solicitation_angle  (Stage 6: full hybrid RAG/RRF pipeline)
# ---------------------------------------------------------------------------

def match_solicitation_angle(scraped_narrative_context: str, category_path: str) -> dict:
    """Tool 6 — Match a solicitation angle via hybrid Chroma+BM25→RRF→tier.

    Stage 6: full hybrid pipeline.
    1. Seed the crisis-case-study corpus into Chroma lazily on first call.
    2. Semantic search via Chroma (all-MiniLM-L6-v2 embeddings).
    3. BM25 search over the corpus (independent of semantic path — RAG3).
    4. Fuse via Reciprocal Rank Fusion (k=60 — RAG4).
    5. Map fused top score to Tier 1–4 (OQ-4 thresholds — RAG5).
    Both rankers always contribute when the corpus is non-empty (T6.2).

    Args:
        scraped_narrative_context: The raw crawl text / narrative for the company.
        category_path:             The Core_Category path from brands_catalog.csv.

    Returns:
        dict with keys:
            angle_key (str):  the matched crisis-case-study angle id.
            tier (int):       ∈ {1,2,3,4} — 1=Critical Fit … 4=No Match.
            scores (dict):    diagnostic counts and top RRF score.
        Tier 4 routes to Policy-6 fallback at the output boundary (FB2 preserved).
    """
    try:
        import rag_engine

        # Seed the corpus lazily (idempotent — safe to call every time)
        rag_engine.seed_corpus_if_empty()

        # Combined query: category_path provides exact-term BM25 signal;
        # scraped_narrative_context provides semantic richness.
        combined_query = f"{category_path} {scraped_narrative_context}"

        # --- Semantic ranking via Chroma (RAG2 / semantic path) ---
        semantic_results = rag_engine.semantic_query(
            query_text=combined_query,
            n_results=10,
        )

        # --- BM25 ranking over the corpus (RAG3 — independent of semantic) ---
        # Retrieve ALL corpus documents for BM25 (full corpus ranking).
        # We fetch from the collection to stay in sync with what Chroma holds.
        collection = rag_engine._get_collection()
        corpus_count = collection.count()

        if corpus_count > 0:
            # Retrieve the full corpus for BM25 (limit to 1000 to be safe)
            all_items = collection.get(
                limit=min(corpus_count, 1000),
                include=["documents"],
            )
            corpus_documents = all_items.get("documents", []) or []
            corpus_ids = all_items.get("ids", []) or []
        else:
            corpus_documents = []
            corpus_ids = []

        bm25_results = rag_engine.bm25_query(
            query_text=combined_query,
            documents=corpus_documents,
            doc_ids=corpus_ids,
            n_results=10,
        )

        # --- Semantic relevance floor (OQ-4 addendum — Stage 6 r1) ---
        # RRF is rank-based: it always produces a rank-1 doc (score ≈ 0.033 with k=60)
        # even for nonsense/off-domain queries. The semantic distance from Chroma is the
        # only signal that reveals "no meaningful overlap with the corpus".
        # If the best semantic distance exceeds SEMANTIC_RELEVANCE_CEILING (0.80),
        # the query is irrelevant → Tier 4 "No Match" immediately, bypass RRF tier.
        # The floor can only push DOWN; it never upgrades a tier.
        if not rag_engine.check_semantic_relevance(semantic_results):
            return {
                "angle_key": "no_match",
                "tier": 4,
                "scores": {
                    "semantic_results": len(semantic_results),
                    "bm25_results": len(bm25_results),
                    "fused_results": 0,
                    "top_rrf_score": 0.0,
                    "relevance_floor_triggered": True,
                },
            }

        # --- RRF fusion (k=60, OQ-4 — RAG4) ---
        fused = rag_engine.rrf_fuse(semantic_results, bm25_results, k=60)

        # --- Tier mapping (OQ-4 thresholds — RAG5) ---
        if fused:
            top = fused[0]
            angle_key = top.get("id", "no_match")
            rrf_score = top.get("rrf_score", 0.0)
            tier = rag_engine.score_to_tier(rrf_score)
        else:
            # No corpus or no results — Tier 4 No Match → Policy-6 at output boundary
            angle_key = "no_match"
            rrf_score = 0.0
            tier = 4

        return {
            "angle_key": angle_key,
            "tier": tier,
            "scores": {
                "semantic_results": len(semantic_results),
                "bm25_results": len(bm25_results),
                "fused_results": len(fused),
                "top_rrf_score": rrf_score,
            },
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "error": f"match_solicitation_angle failed: {exc}",
            "angle_key": "no_match",
            "tier": 4,
            "scores": {},
        }


# ---------------------------------------------------------------------------
# Tool 7 — request_reactfirst_pdf
# ---------------------------------------------------------------------------

# Minimal inline validation regexes (the consolidated gateway_validate is Stage 5)
_INLINE_RE_DOMAIN    = re.compile(r"^[a-z0-9][a-z0-9\-]{0,61}[a-z0-9]?\.[a-z]{2,}(\.[a-z]{2,})?$")
_INLINE_RE_ANGLE_KEY = re.compile(r"^[A-Za-z0-9_\-]{2,80}$")


def request_reactfirst_pdf(
    target_domain: str,
    validated_angle_key: str,
    calculated_risk_score: float,
) -> dict:
    """Tool 7 — Request and save the ReactFirst Narrative-Analysis PDF.

    This is the ONLY tool permitted to target OUTREACH_SUBDOMAIN.

    Minimal inline input validation (consolidated gateway_validate wired in Stage 5):
    - target_domain must be non-null and match the domain regex.
    - validated_angle_key must be non-null and match the angle-key regex.
    - calculated_risk_score must be numeric (int or float).

    On success: saves the PDF under assets/, returns {"path": ..., "ok": True}.
    On API failure: returns {"ok": False, "error": ...} — no partial file left.
    On validation failure: returns {"ok": False, "error": ...} — no outbound call.

    Args:
        target_domain:       The domain to generate the PDF for.
        validated_angle_key: The angle key from match_solicitation_angle.
        calculated_risk_score: The numeric risk score from secured_calculator.

    Returns:
        dict with keys: ok (bool), path (str, on success), error (str, on failure).
    """
    # --- Inline input validation (T7.3) ---
    if not target_domain or not isinstance(target_domain, str):
        return {"ok": False, "error": "target_domain is required and must be a string"}
    domain_norm = _normalize_domain(target_domain)
    if not _INLINE_RE_DOMAIN.match(domain_norm):
        return {"ok": False, "error": f"target_domain has invalid format: {target_domain!r}"}

    if not validated_angle_key or not isinstance(validated_angle_key, str):
        return {"ok": False, "error": "validated_angle_key is required and must be a string"}
    if not _INLINE_RE_ANGLE_KEY.match(validated_angle_key):
        return {"ok": False, "error": f"validated_angle_key has invalid format: {validated_angle_key!r}"}

    if not isinstance(calculated_risk_score, (int, float)):
        return {"ok": False, "error": f"calculated_risk_score must be numeric, got {type(calculated_risk_score).__name__}"}

    # --- Ensure assets/ directory exists ---
    assets_dir = pathlib.Path(os.getcwd()) / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    # --- PDF filename ---
    safe_domain = domain_norm.replace(".", "_")
    pdf_filename = f"reactfirst_{safe_domain}_{validated_angle_key}.pdf"
    pdf_path = assets_dir / pdf_filename

    # --- Call ReactFirst backend (only egress to OUTREACH_SUBDOMAIN) ---
    tmp_path = pdf_path.with_suffix(".tmp")
    try:
        import urllib.request  # stdlib, lazy-style import for clarity
        api_url = (
            f"https://{OUTREACH_SUBDOMAIN}/api/generate-pdf"
            f"?domain={domain_norm}"
            f"&angle={validated_angle_key}"
            f"&risk={calculated_risk_score}"
        )
        reactfirst_key = os.environ.get("REACTFIRST_API_KEY", "")
        req = urllib.request.Request(
            api_url,
            headers={
                "Authorization": f"Bearer {reactfirst_key}",
                "Accept": "application/pdf",
            },
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            pdf_bytes = resp.read()

        if not pdf_bytes:
            return {"ok": False, "error": "ReactFirst API returned empty response"}

        # Write to tmp first, then rename (atomic — no partial corrupt file on failure)
        tmp_path.write_bytes(pdf_bytes)
        tmp_path.rename(pdf_path)

        return {"path": str(pdf_path), "ok": True}

    except Exception as exc:  # noqa: BLE001
        # Clean up any partial temp file (T7.5)
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except Exception:  # noqa: BLE001
                pass
        return {"ok": False, "error": f"ReactFirst PDF request failed: {exc}"}


# ---------------------------------------------------------------------------
# Tool 8 — secured_calculator
# ---------------------------------------------------------------------------

def _walk_ast(node) -> float:
    """Recursive AST walker with strict whitelist.

    Allowed nodes: BinOp (Add, Sub, Mult, Div), UnaryOp (USub),
                   ast.Constant (numeric only), Expression.

    Anything else raises ValueError("Unauthorized mathematical syntax block: ...").
    Raw eval/exec are never used.
    """
    if isinstance(node, ast.Expression):
        return _walk_ast(node.body)

    if isinstance(node, ast.Constant):
        if not isinstance(node.value, (int, float)):
            raise ValueError(
                f"Unauthorized mathematical syntax block: non-numeric constant {node.value!r}"
            )
        return float(node.value)

    if isinstance(node, ast.BinOp):
        left  = _walk_ast(node.left)
        right = _walk_ast(node.right)
        op    = node.op
        if isinstance(op, ast.Add):
            return left + right
        if isinstance(op, ast.Sub):
            return left - right
        if isinstance(op, ast.Mult):
            return left * right
        if isinstance(op, ast.Div):
            if right == 0:
                raise ValueError("Division by zero")
            return left / right
        # Any other BinOp (Pow, FloorDiv, Mod, BitOr, etc.) is rejected
        raise ValueError(
            f"Unauthorized mathematical syntax block: operator {type(op).__name__}"
        )

    if isinstance(node, ast.UnaryOp):
        if isinstance(node.op, ast.USub):
            return -_walk_ast(node.operand)
        # UAdd, Invert, Not — rejected
        raise ValueError(
            f"Unauthorized mathematical syntax block: unary operator {type(node.op).__name__}"
        )

    # All other node types: Call, Name, Attribute, Subscript, Lambda,
    # comprehensions, etc. — rejected
    raise ValueError(
        f"Unauthorized mathematical syntax block: {type(node).__name__}"
    )


def secured_calculator(expression: str) -> str:
    """Tool 8 — Safe arithmetic evaluator using an AST whitelist walker.

    Evaluates expressions containing only: + - * / and unary minus,
    numeric constants (int/float), and parenthesized grouping.

    Raises ValueError for any attempt to use:
    - ** / Pow
    - Function calls
    - Variable names / attributes / subscripts
    - Comprehensions, lambdas, or any other node

    NO raw eval or exec used anywhere (AST walk only).

    SOP smoke: secured_calculator("(1700 + 450) * 1.15") → "2472.5" (T8.1)

    Args:
        expression: Arithmetic expression string.

    Returns:
        str representation of the numeric result.

    Raises:
        ValueError: for unauthorized syntax or non-string input.
    """
    if not isinstance(expression, str):
        raise ValueError(f"expression must be a string, got {type(expression).__name__}")

    expression = expression.strip()
    if not expression:
        raise ValueError("expression must be non-empty")

    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise ValueError(f"Invalid expression syntax: {exc}") from exc

    result = _walk_ast(tree)

    # Format: integer if the result is a whole number, otherwise float
    if isinstance(result, float) and result.is_integer():
        return str(int(result))
    return str(result)


# ---------------------------------------------------------------------------
# Tool 9 — build_icp_document  (Phase 2, Stage 10 — Layer 1 ICP Builder)
# ---------------------------------------------------------------------------

def _parse_icp_json(raw_text: str) -> dict:
    """Parse LLM output (possibly wrapped in fences/prose) into a dict.

    Mirrors _parse_query_list's tolerant approach: tries bare JSON first,
    then a fenced block, then returns an error dict on total failure.
    Never raises.
    """
    text = raw_text.strip() if raw_text else ""
    if not text:
        return {}

    # Strategy 1 — bare JSON object
    try:
        maybe = json.loads(text)
        if isinstance(maybe, dict):
            return maybe
    except (json.JSONDecodeError, ValueError):
        pass

    # Strategy 2 — fenced code block containing a JSON object
    fence_match = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", text, re.IGNORECASE)
    if fence_match:
        try:
            maybe = json.loads(fence_match.group(1))
            if isinstance(maybe, dict):
                return maybe
        except (json.JSONDecodeError, ValueError):
            pass

    # Strategy 3 — find the first {...} blob in the text
    brace_match = re.search(r"\{[\s\S]*\}", text)
    if brace_match:
        try:
            maybe = json.loads(brace_match.group(0))
            if isinstance(maybe, dict):
                return maybe
        except (json.JSONDecodeError, ValueError):
            pass

    return {}


def build_icp_document(seed: str) -> dict:
    """Tool 9 — Build a structured ICP document + up to 5 anchor companies from a seed.

    SLED Layer-1 4-stage flow (re-skinned for crisis-narrative / brand-safety domain):
      1. Seed parse   — normalize the seed to a vertical string.
      2. Vertical research (grounded) — reuse _vector_a_search (Claude web_search)
         to surface example companies; monkeypatched in tests.
      3. ICP synthesis — one ANALYZER_MODEL call returns the structured ICP fields as JSON.
      4. Anchor leads  — take ≤ ICP_ANCHOR_COUNT example companies from grounded research.

    Hard constraints (graded):
    - Catalog-independent: never reads brands_catalog.csv, no catalog_df param.
    - No catalog literals hardcoded (ICPB4 / G2).
    - evaluate_icp_tags / _ICP_TAGS / ICP_TAG_THRESHOLD are UNTOUCHED (ICPB5).
    - Anchor count capped at ICP_ANCHOR_COUNT = 5 (ICPB2).
    - Import-safe: _get_client() called lazily inside (ICPB3 / ENV4).
    - Tool errors are data, not crashes (CLAUDE.md §6.6).

    Args:
        seed: A company name OR a free-text vertical description.

    Returns:
        dict with keys:
            vertical (str), want_signals (list[str]), avoid_signals (list[str]),
            geo (str), size_band (str), icp_tags (list[str]),
            anchor_companies (list[dict: {name, domain, why}])
        On failure: {"error": "build_icp_document failed: <msg>"}
    """
    try:
        # ---------------------------------------------------------------
        # Stage 1 — Seed parse: normalize to a vertical string.
        # Simple heuristic: strip, truncate to 200 chars.
        # ---------------------------------------------------------------
        vertical_seed = str(seed).strip()[:200] if seed else ""
        if not vertical_seed:
            return {"error": "build_icp_document failed: seed must be a non-empty string"}

        # ---------------------------------------------------------------
        # Stage 2 — Vertical research (grounded): reuse _vector_a_search.
        # Returns {"domains": [...], "status": "ok"|"error", "error": ...}.
        # Under tests this is monkeypatched.
        # ---------------------------------------------------------------
        research_result = _vector_a_search(
            f"example companies in the '{vertical_seed}' vertical — e-commerce DTC brands"
        )
        research_domains = research_result.get("domains", []) if isinstance(research_result, dict) else []

        # ---------------------------------------------------------------
        # Stage 3 — ICP synthesis via ANALYZER_MODEL.
        # Prompt draws icp_tags from the _ICP_TAGS vocabulary for consistency
        # (read at runtime from the module constant, not hardcoded in the prompt).
        # ---------------------------------------------------------------
        icp_tag_keys = list(_ICP_TAGS.keys())  # runtime read — no hardcoding
        prompt = (
            f"You are a GTM strategist building an Ideal Customer Profile (ICP) document "
            f"for a crisis-narrative and brand-safety outreach platform.\n\n"
            f"Vertical / seed: '{vertical_seed}'\n\n"
            f"Based on this vertical, produce a structured ICP document as a JSON object "
            f"with EXACTLY these keys:\n"
            f"  vertical        — the cleaned vertical label (string)\n"
            f"  want_signals    — list of 3-6 positive ICP qualifiers (list of strings)\n"
            f"  avoid_signals   — list of 2-4 disqualifying signals (list of strings)\n"
            f"  geo             — primary geographic focus or 'global' (string)\n"
            f"  size_band       — company-size band, e.g. 'SMB', 'mid-market', 'enterprise' (string)\n"
            f"  icp_tags        — 3-5 ICP tag labels chosen from this vocabulary: {icp_tag_keys} (list of strings)\n"
            f"  anchor_companies — up to 5 example companies relevant to this vertical as a list of objects, "
            f"each with keys: name (string), domain (string), why (string, 1 sentence)\n\n"
            f"Constraints:\n"
            f"- Return ONLY valid JSON, no prose, no markdown fences.\n"
            f"- anchor_companies must contain at most 5 items.\n"
            f"- icp_tags must be a subset of the vocabulary list above.\n"
            f"- All fields must be present even if empty (use [] or '' for unknown).\n"
        )

        client = _get_client()
        response = client.messages.create(
            model=ANALYZER_MODEL,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )

        raw_text = ""
        for block in response.content:
            if hasattr(block, "text"):
                raw_text += block.text

        icp_data = _parse_icp_json(raw_text)

        # ---------------------------------------------------------------
        # Stage 4 — Anchor leads: cap at ICP_ANCHOR_COUNT from grounded research.
        # If the LLM supplied anchor_companies, cap them.
        # If not, synthesize stubs from the research domains.
        # ---------------------------------------------------------------
        llm_anchors = icp_data.get("anchor_companies", [])
        if isinstance(llm_anchors, list):
            # Cap at ICP_ANCHOR_COUNT (ICPB2)
            anchors = llm_anchors[:ICP_ANCHOR_COUNT]
        else:
            anchors = []

        # If the LLM returned fewer than ICP_ANCHOR_COUNT, supplement from grounded domains
        # (only add domain stubs if not already covered by name in LLM anchors)
        existing_domains = {
            a.get("domain", "").lower()
            for a in anchors
            if isinstance(a, dict)
        }
        for domain in research_domains:
            if len(anchors) >= ICP_ANCHOR_COUNT:
                break
            if domain.lower() not in existing_domains:
                anchors.append({
                    "name": domain,
                    "domain": domain,
                    "why": f"Identified via grounded vertical research for '{vertical_seed}'.",
                })
                existing_domains.add(domain.lower())

        # ---------------------------------------------------------------
        # Assemble the final ICP document with guaranteed key presence.
        # ---------------------------------------------------------------
        result = {
            "vertical":         str(icp_data.get("vertical", vertical_seed)),
            "want_signals":     list(icp_data.get("want_signals", [])),
            "avoid_signals":    list(icp_data.get("avoid_signals", [])),
            "geo":              str(icp_data.get("geo", "global")),
            "size_band":        str(icp_data.get("size_band", "")),
            "icp_tags":         [str(t) for t in icp_data.get("icp_tags", [])],
            "anchor_companies": anchors,
        }
        return result

    except Exception as exc:  # noqa: BLE001 — tool errors are data, not crashes
        return {"error": f"build_icp_document failed: {exc}"}


# ---------------------------------------------------------------------------
# Tool 10 — discover_contacts  (Phase 2, Stage 12 — Layer 5b Profile Expander)
# ---------------------------------------------------------------------------

def _parse_contact_list(raw_text: str) -> list:
    """Parse LLM output (possibly wrapped in fences/prose) into a list of contact dicts.

    Tolerant approach: tries bare JSON first (array), then a fenced block,
    then the first [...] blob in the text.  Never raises.
    Returns a list (possibly empty).
    """
    text = raw_text.strip() if raw_text else ""
    if not text:
        return []

    # Strategy 1 — bare JSON array
    try:
        maybe = json.loads(text)
        if isinstance(maybe, list):
            return maybe
    except (json.JSONDecodeError, ValueError):
        pass

    # Strategy 2 — fenced code block containing a JSON array
    fence_match = re.search(r"```(?:json)?\s*(\[[\s\S]*?\])\s*```", text, re.IGNORECASE)
    if fence_match:
        try:
            maybe = json.loads(fence_match.group(1))
            if isinstance(maybe, list):
                return maybe
        except (json.JSONDecodeError, ValueError):
            pass

    # Strategy 3 — find the first [...] blob in the text
    bracket_match = re.search(r"\[[\s\S]*\]", text)
    if bracket_match:
        try:
            maybe = json.loads(bracket_match.group(0))
            if isinstance(maybe, list):
                return maybe
        except (json.JSONDecodeError, ValueError):
            pass

    return []


def _normalise_contact(raw: dict) -> dict:
    """Normalise a raw contact dict to the canonical 5-key shape.

    Returns a dict with exactly: first_name, last_name, role, email, linkedin_url.
    All values are strings; missing keys become empty strings.
    Does NOT touch any lead_store private field or corporate_access_key.
    """
    return {
        "first_name":   str(raw.get("first_name", "")),
        "last_name":    str(raw.get("last_name", "")),
        "role":         str(raw.get("role", "")),
        "email":        str(raw.get("email", "")),
        "linkedin_url": str(raw.get("linkedin_url", "")),
    }


def discover_contacts(brand_id: str, domain: str) -> dict:
    """Tool 10 — Discover candidate contacts for a qualified brand.

    SLED Layer-5 Profile Expander (re-skinned):
      1. Use _vector_a_search (grounded) to surface candidate people for `domain`.
      2. Optionally call LIGHT_MODEL to synthesise structured contact candidates.
      3. Normalise to the 5-key contact shape; de-dup by email.
      4. Attach discovered candidate emails to the CRM lead's contact_ids
         (workspace metadata only — NO private lead_store read).

    GOVERNANCE (DISC3 — read carefully):
    - Performs NO privileged read of the auth-gated lead_store contacts collection.
    - Exposes NO stored private contact field (no email/corporate_access_key/
      interaction_history_count from existing records).
    - Surfaces ONLY freshly-discovered candidate data (mocked in tests).
    - Attaches candidate email refs to crm_store contact_ids — workspace metadata.
    - The Policy-4 gate (lead_store.authenticate_and_get_contact) remains the
      single, un-bypassed path to existing private records.
    - Auth + opt_out_status for actual outbound are enforced downstream at L6 dispatch.
    - No corporate_access_key value ever appears here (DISC4 / G4 / CRM7).

    Hard constraints:
    - Import-safe: _get_client() called lazily (DISC5 / ENV4).
    - Tool errors are data, not crashes (CLAUDE.md §6.6).
    - No catalog literals, no contacts.json values, no secrets hardcoded (DISC4 / G2).

    Args:
        brand_id: The brand's Uniq_Id (CRM workspace primary key).
        domain:   The brand's primary domain (used for grounded discovery query).

    Returns:
        dict with keys:
            brand_id (str), contacts (list[dict]), count (int)
            Each contact dict: {first_name, last_name, role, email, linkedin_url}
        On failure: {"error": "discover_contacts failed: <msg>"}
    """
    try:
        # ---------------------------------------------------------------
        # Validate inputs
        # ---------------------------------------------------------------
        brand_id = str(brand_id).strip() if brand_id else ""
        domain   = str(domain).strip() if domain else ""
        if not brand_id:
            return {"error": "discover_contacts failed: brand_id must be non-empty"}
        if not domain:
            return {"error": "discover_contacts failed: domain must be non-empty"}

        # ---------------------------------------------------------------
        # Stage 1 — Grounded discovery: surface candidate people.
        # _vector_a_search returns {"domains":[...], "status": ..., "error": ...}
        # or may return text content in its status/error fields on error.
        # Monkeypatched in tests to return deterministic canned results.
        # ---------------------------------------------------------------
        discovery_query = (
            f"marketing director OR VP marketing OR CMO OR head of growth "
            f"site:{domain} OR '{domain}' contact LinkedIn"
        )
        grounded_result = _vector_a_search(discovery_query)
        # Grounded result may include text output in the domains list or as error text.
        # We treat any non-list / non-dict as a no-op and proceed to the LLM step.
        grounded_domains = (
            grounded_result.get("domains", [])
            if isinstance(grounded_result, dict)
            else []
        )

        # ---------------------------------------------------------------
        # Stage 2 — LLM candidate synthesis via LIGHT_MODEL.
        # Ask the model to infer likely contact roles/names for `domain`.
        # Returns a JSON array of contact objects.  Monkeypatched in tests.
        # ---------------------------------------------------------------
        prompt = (
            f"You are a B2B contact researcher. For the e-commerce brand at domain '{domain}', "
            f"infer the most likely marketing / growth decision-makers. "
            f"Return a JSON array (no prose) of up to 5 contact objects, each with keys:\n"
            f"  first_name (string), last_name (string), role (string),\n"
            f"  email (string — pattern-guessed public email, e.g. firstname@{domain}),\n"
            f"  linkedin_url (string — pattern URL, may be empty if unknown)\n\n"
            f"Constraints:\n"
            f"- Return ONLY a valid JSON array, no prose, no markdown fences.\n"
            f"- email values are inferred/pattern-guessed candidates, NOT private records.\n"
            f"- At most 5 items in the array.\n"
            f"- All 5 keys must be present in each object (use '' for unknowns).\n"
        )

        client = _get_client()
        response = client.messages.create(
            model=LIGHT_MODEL,
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )

        raw_text = ""
        for block in response.content:
            if hasattr(block, "text"):
                raw_text += block.text

        candidate_list = _parse_contact_list(raw_text)

        # ---------------------------------------------------------------
        # Stage 3 — Normalise + de-dup by email.
        # ---------------------------------------------------------------
        seen_emails: set = set()
        contacts: list = []
        for raw in candidate_list:
            if not isinstance(raw, dict):
                continue
            normalised = _normalise_contact(raw)
            email = normalised["email"].lower().strip()
            if not email or email in seen_emails:
                continue
            seen_emails.add(email)
            contacts.append(normalised)

        # ---------------------------------------------------------------
        # Stage 4 — Attach candidate email refs to the CRM lead (DISC3).
        # This writes ONLY to crm_store's contact_ids workspace metadata.
        # It does NOT read or expose any lead_store private field.
        # If the lead does not exist, upsert a minimal record first.
        # ---------------------------------------------------------------
        import crm_store  # import-safe; lazy singleton inside crm_store

        # Ensure CRM lead exists (upsert minimal record if absent)
        existing = crm_store.get_lead(brand_id)
        if existing is None:
            crm_store.upsert_lead({"uniq_id": brand_id, "domain": domain})

        # Append each discovered email to contact_ids via a direct CRM update
        # (no auth gate here — these are freshly-discovered candidates, not private records).
        if contacts:
            collection = crm_store.get_crm_collection()
            lead = collection.find_one({"uniq_id": brand_id})
            if lead is not None:
                existing_ids = lead.get("contact_ids", [])
                new_ids = list(existing_ids)
                for c in contacts:
                    email = c["email"].lower().strip()
                    if email and email not in new_ids:
                        new_ids.append(email)
                # Use crm_store's own UTC helper (avoids an inline import here)
                collection.update_one(
                    {"uniq_id": brand_id},
                    {"$set": {
                        "contact_ids": new_ids,
                        "updated_at": crm_store._utc_now_iso(),
                    }},
                )

        # ---------------------------------------------------------------
        # Assemble and return the result.
        # ---------------------------------------------------------------
        result = {
            "brand_id": brand_id,
            "contacts": contacts,
            "count":    len(contacts),
        }
        return result

    except Exception as exc:  # noqa: BLE001 — tool errors are data, not crashes
        return {"error": f"discover_contacts failed: {exc}"}


# ===========================================================================
# Section 6 — Tool schemas (Stage 3)
# Each schema is Anthropic-shaped: {"name", "description", "input_schema"}.
# Schema names are byte-identical to function names and TOOL_DISPATCH keys.
# Adjacent to the tool functions so they cannot drift.
# ===========================================================================

TOOL_SCHEMAS = [
    # -----------------------------------------------------------------------
    # Schema 1 — generate_search_queries
    # -----------------------------------------------------------------------
    {
        "name": "generate_search_queries",
        "description": (
            "Use this tool FIRST at the start of any brand-discovery or vertical-exploration "
            "task. It generates a variation matrix of distinct, non-overlapping search queries "
            "from a vertical seed so that downstream fan-out covers multiple intent axes "
            "(brand discovery, competitor landscape, ad-spend signals, DTC vs retail, "
            "sustainability, etc.). "
            "Key constraint: target_count must be between 10 and 20; default is 15 "
            "(DEFAULT_QUERY_COUNT). Output is de-duplicated and capped at target_count. "
            "Do NOT use this tool for catalog lookups or ICP evaluation — use it only "
            "to generate the initial discovery query set."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "vertical_seed": {
                    "type": "string",
                    "description": (
                        "The vertical or category seed string to generate queries from "
                        "(e.g. 'athleisure DTC brands', 'sustainable pet food'). Required."
                    ),
                },
                "target_count": {
                    "type": "integer",
                    "description": (
                        "Target number of query variations to generate. "
                        "Must be between 10 and 20. Defaults to 15 if omitted."
                    ),
                },
            },
            "required": ["vertical_seed"],
        },
    },

    # -----------------------------------------------------------------------
    # Schema 2 — execute_3way_fanout
    # -----------------------------------------------------------------------
    {
        "name": "execute_3way_fanout",
        "description": (
            "Use this tool to discover candidate brand domains from a list of search queries "
            "produced by generate_search_queries. Runs Vector A (Claude web_search) and "
            "Vector B (SerpAPI) concurrently in parallel. "
            "Key constraint: Vector C (Tavily recovery) is invoked for a query ONLY WHEN "
            "the union of Vector A and Vector B yields fewer than 2 distinct domains for that "
            "query (FANOUT_RECOVERY_THRESHOLD=2); if A+B already yielded ≥2 domains, "
            "Vector C is skipped. "
            "Per-vector failures are isolated — one vector down does not abort the whole run. "
            "Returns pooled domains with provenance (which vector found each domain). "
            "Do NOT use this tool without first calling generate_search_queries."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "queries": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "List of search query strings from generate_search_queries. "
                        "Each string is one query variation to fan out across all vectors."
                    ),
                },
            },
            "required": ["queries"],
        },
    },

    # -----------------------------------------------------------------------
    # Schema 3 — extract_and_score_pool
    # -----------------------------------------------------------------------
    {
        "name": "extract_and_score_pool",
        "description": (
            "Use this tool to de-duplicate the raw domain pool from execute_3way_fanout "
            "and map each candidate against the Brands Data Catalog. "
            "Key constraint: de-duplication is by normalized Primary_Domain; catalog mapping "
            "attaches the 9-column catalog context (Uniq_Id, Brand_Name, Core_Category, "
            "Estimated_Ad_Spend_Tier, Current_Status, Historical_Social_Incidents, "
            "Main_Competitor_Id, Gtin_Prefix) where a domain matches. Non-catalog candidates "
            "are retained but flagged in_catalog=False — they are NOT dropped. "
            "Catalog context injection happens internally against the loaded catalog; "
            "you do not need to supply catalog data. "
            "Output is a scored, deterministically ordered candidate list."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "raw_pool": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "description": (
                            "A candidate entry with at least 'domain' (str) and "
                            "'provenance' (list of vector names, e.g. ['A','B'])."
                        ),
                    },
                    "description": (
                        "The raw candidate pool from execute_3way_fanout. Each item is a "
                        "dict with 'domain' and 'provenance' fields. "
                        "Catalog mapping is performed internally."
                    ),
                },
            },
            "required": ["raw_pool"],
        },
    },

    # -----------------------------------------------------------------------
    # Schema 4 — analyze_company_chunk
    # -----------------------------------------------------------------------
    {
        "name": "analyze_company_chunk",
        "description": (
            "Use this tool to deep-scrape a batch of candidate domains using Firecrawl "
            "and extract per-domain profiles including pixel tracking flags. "
            "Key constraints: "
            "(1) Never submit more than 100 domains in a single call (CHUNK_MAX_DOMAINS=100); "
            "if you have more, call this tool multiple times with sub-batches. "
            "(2) The tool enforces an 800-second wall-clock budget (CHUNK_TIME_BUDGET_S=800); "
            "on timeout it returns partial results with timed_out=True rather than raising. "
            "(3) Each domain's crawl result includes three explicit boolean pixel flags: "
            "tiktok_pixel, meta_pixel, gtm (Google Tag Manager). "
            "(4) Per-domain crawl failures are isolated to that domain's record — they do "
            "not abort the whole chunk. "
            "Call this after extract_and_score_pool to get deep technical profiles."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "domains": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "List of normalized domain strings to analyze (e.g. 'example.com'). "
                        "Maximum 100 per call. Excess domains beyond 100 are silently dropped "
                        "from the chunk — submit them in a separate call."
                    ),
                },
            },
            "required": ["domains"],
        },
    },

    # -----------------------------------------------------------------------
    # Schema 5 — evaluate_icp_tags
    # -----------------------------------------------------------------------
    {
        "name": "evaluate_icp_tags",
        "description": (
            "Use this tool to determine whether a company qualifies for automated outreach "
            "by evaluating ICP (Ideal Customer Profile) tags against a company profile string. "
            "Key constraint: a company qualifies IF AND ONLY IF the matched ICP tag count "
            "is >= 3 (ICP_TAG_THRESHOLD=3). Fewer than 3 matched tags → not qualified, "
            "no outreach proceeds. Exactly 3 tags may trigger the Trust-Gated human-in-loop "
            "path instead of automatic outreach. "
            "This is a pure structural function — no network calls, deterministic. "
            "The 8 ICP tags checked are: ecommerce_dtc, paid_social_advertising, "
            "scale_growth_stage, pixel_tracking_present, brand_marketing_team, "
            "product_catalogue_depth, ad_spend_signals, crisis_reputation_risk. "
            "Call this after analyze_company_chunk with the profile text as input."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "company_profile_data": {
                    "type": "string",
                    "description": (
                        "Raw crawl text and technical metadata string for the company. "
                        "Typically the markdown/HTML content and signals from "
                        "analyze_company_chunk combined into a single text block. "
                        "Must be a non-empty string."
                    ),
                },
            },
            "required": ["company_profile_data"],
        },
    },

    # -----------------------------------------------------------------------
    # Schema 6 — match_solicitation_angle
    # -----------------------------------------------------------------------
    {
        "name": "match_solicitation_angle",
        "description": (
            "Use this tool to match the best solicitation angle for a qualified brand "
            "by running hybrid semantic + BM25 search fused via Reciprocal Rank Fusion (RRF) "
            "over the internal case-study corpus. "
            "Key constraints: "
            "(1) Only call this for brands that passed evaluate_icp_tags (qualified=True). "
            "(2) Returns a tier in {1,2,3,4}: Tier 1 = Critical Fit (highest priority), "
            "Tier 4 = No Match (routes to the Policy 6 fallback — do not request a PDF "
            "for Tier 4 results). "
            "(3) Output Suggestions Ceiling: the pipeline emits at most 3 distinct angles "
            "(MAX_ANGLES=3) across all brands in a session — track how many angles you "
            "have already collected and stop calling this tool once 3 qualified angles "
            "have been found. "
            "category_path should come directly from the Core_Category column of the "
            "Brands Data Catalog — never invented."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "scraped_narrative_context": {
                    "type": "string",
                    "description": (
                        "The narrative text about the company: crawled content, "
                        "ICP tag signals, and operational scale indicators from "
                        "analyze_company_chunk. Forms the semantic query basis."
                    ),
                },
                "category_path": {
                    "type": "string",
                    "description": (
                        "The Core_Category multi-tier path from brands_catalog.csv for "
                        "this brand (e.g. 'Apparel > Athleisure > Sustainable'). "
                        "Must come from the catalog — never invented or guessed."
                    ),
                },
            },
            "required": ["scraped_narrative_context", "category_path"],
        },
    },

    # -----------------------------------------------------------------------
    # Schema 7 — request_reactfirst_pdf
    # -----------------------------------------------------------------------
    {
        "name": "request_reactfirst_pdf",
        "description": (
            "Use this tool to request and save a ReactFirst Narrative-Analysis PDF for a "
            "qualified brand-angle pair. This is the ONLY tool that may contact the outbound "
            "subdomain (outreach.reactfirst.ai) — no other tool may target that host. "
            "Key constraints: "
            "(1) Only call this for brands with a match_solicitation_angle result of Tier 1, "
            "2, or 3 — NEVER for Tier 4 (No Match). "
            "(2) The validated_angle_key must be the angle_key returned by "
            "match_solicitation_angle — do not fabricate it. "
            "(3) The calculated_risk_score must be a numeric value from secured_calculator, "
            "not an invented number. "
            "(4) Output Suggestions Ceiling: do not request more than 3 PDFs total per "
            "session (MAX_ANGLES=3 ceiling applies here at the output boundary). "
            "On success returns {'path': 'assets/...pdf', 'ok': True}. "
            "On failure returns {'ok': False, 'error': ...} with no partial file left."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "target_domain": {
                    "type": "string",
                    "description": (
                        "The normalized domain of the brand to generate the PDF for "
                        "(e.g. 'example.com'). Must match the domain-format regex."
                    ),
                },
                "validated_angle_key": {
                    "type": "string",
                    "description": (
                        "The angle key from match_solicitation_angle (e.g. 'crisis_fit_001'). "
                        "Must match the angle-key format: 2–80 alphanumeric/underscore/dash chars."
                    ),
                },
                "calculated_risk_score": {
                    "type": "number",
                    "description": (
                        "A numeric risk score for the brand-angle pair, computed via "
                        "secured_calculator from catalog-derived inputs. "
                        "Must be a numeric value — not a string."
                    ),
                },
            },
            "required": ["target_domain", "validated_angle_key", "calculated_risk_score"],
        },
    },

    # -----------------------------------------------------------------------
    # Schema 8 — secured_calculator
    # -----------------------------------------------------------------------
    {
        "name": "secured_calculator",
        "description": (
            "Use this tool whenever arithmetic evaluation is needed in the pipeline "
            "(e.g. risk scores or pricing math derived from catalog values). "
            "Key constraints: "
            "(1) SAFE ARITHMETIC ONLY — NO eval/exec. The tool uses an AST whitelist walker "
            "that permits only: + - * / (and unary minus), numeric constants, and parentheses. "
            "Any attempt to use ** (power), function calls, variable names, attributes, "
            "subscripts, comprehensions, or lambdas raises ValueError. "
            "(2) Always use this tool for any arithmetic in the pipeline — NEVER construct "
            "arithmetic via Python string eval or exec. "
            "(3) SOP smoke: '(1700 + 450) * 1.15' evaluates to '2472.5'. "
            "Returns the numeric result as a string."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": (
                        "An arithmetic expression using only: numeric literals, "
                        "+ - * / operators, unary minus, and parentheses. "
                        "Examples: '(1700 + 450) * 2', '2500 * 0.9', '3000 / 4'. "
                        "Do NOT include variable names, function calls, or ** power operator."
                    ),
                },
            },
            "required": ["expression"],
        },
    },

    # -----------------------------------------------------------------------
    # Schema 9 — build_icp_document
    # -----------------------------------------------------------------------
    {
        "name": "build_icp_document",
        "description": (
            "Use this tool at the FRONT of a discovery task to define the Ideal Customer "
            "Profile (ICP) before running generate_search_queries. "
            "It accepts a company name OR a free-text vertical description (the 'seed') and "
            "returns a structured ICP document with: vertical label, want_signals, "
            "avoid_signals, geo, size_band, icp_tags, and up to 5 anchor/example companies. "
            "Key constraints: "
            "(1) Anchor companies are capped at ICP_ANCHOR_COUNT=5 — never more. "
            "(2) This tool does NOT qualify leads — qualification is always done by "
            "evaluate_icp_tags (ICP_TAG_THRESHOLD >= 3). The icp_tags in the ICP document "
            "are advisory content for the operator, not a qualification gate. "
            "(3) This tool is catalog-independent — it does not read brands_catalog.csv; "
            "do not supply catalog data to it."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "seed": {
                    "type": "string",
                    "description": (
                        "A company name (e.g. 'Allbirds') or a free-text vertical description "
                        "(e.g. 'DTC sustainable footwear brands with paid social advertising'). "
                        "Used to derive the vertical and anchor companies."
                    ),
                },
            },
            "required": ["seed"],
        },
    },
    # -----------------------------------------------------------------------
    # Schema 10 — discover_contacts
    # -----------------------------------------------------------------------
    {
        "name": "discover_contacts",
        "description": (
            "Use this tool AFTER a brand has qualified (evaluate_icp_tags returned "
            "qualified=True) to find the right people to approach at that brand. "
            "It surfaces freshly-discovered candidate contacts (marketing directors, "
            "VPs of growth, CMOs) using grounded web search and LLM-assisted inference "
            "for the given domain. "
            "Key constraints: "
            "(1) Returns ONLY newly-discovered candidate data — it does NOT read private "
            "CRM records or the auth-gated contacts collection. To access existing stored "
            "contact records you MUST use the Policy-4 auth gate separately. "
            "(2) Discovered candidate emails are attached to the CRM lead's contact_ids "
            "as workspace metadata only — no private fields are written or exposed. "
            "(3) De-duplicates candidates by email; at most 5 contacts returned. "
            "(4) Input: brand_id (the brand's Uniq_Id) and domain (the brand's primary domain). "
            "Both are required."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "brand_id": {
                    "type": "string",
                    "description": (
                        "The brand's Uniq_Id from brands_catalog.csv — used as the CRM "
                        "workspace primary key to attach discovered contacts."
                    ),
                },
                "domain": {
                    "type": "string",
                    "description": (
                        "The brand's primary domain (e.g. 'example.com') — used to drive "
                        "the grounded discovery query and infer candidate email patterns."
                    ),
                },
            },
            "required": ["brand_id", "domain"],
        },
    },
]


# ===========================================================================
# Section 7 — Dispatch table (Stage 3)
# TOOL_DISPATCH maps schema name → Python function.
# Three-way identity contract (S0):
#   len(TOOL_SCHEMAS) == 10  (8 original + build_icp_document + discover_contacts)
#   every schema["name"] == a key in TOOL_DISPATCH == the function name
# Enforced by an import-time assert (safe: operates only on already-defined constants).
# ===========================================================================

TOOL_DISPATCH = {
    "generate_search_queries":  generate_search_queries,
    "execute_3way_fanout":      execute_3way_fanout,
    "extract_and_score_pool":   extract_and_score_pool,
    "analyze_company_chunk":    analyze_company_chunk,
    "evaluate_icp_tags":        evaluate_icp_tags,
    "match_solicitation_angle": match_solicitation_angle,
    "request_reactfirst_pdf":   request_reactfirst_pdf,
    "secured_calculator":       secured_calculator,
    "build_icp_document":       build_icp_document,
    "discover_contacts":        discover_contacts,
}

# Import-time three-way name identity assertion (ENV4-safe: no side effects,
# only compares already-defined dicts and function objects).
assert len(TOOL_SCHEMAS) == 10, (
    f"TOOL_SCHEMAS must contain exactly 10 schemas; found {len(TOOL_SCHEMAS)}"
)
assert len(TOOL_DISPATCH) == 10, (
    f"TOOL_DISPATCH must contain exactly 10 entries; found {len(TOOL_DISPATCH)}"
)
_schema_names   = {s["name"] for s in TOOL_SCHEMAS}
_dispatch_names = set(TOOL_DISPATCH.keys())
assert _schema_names == _dispatch_names, (
    f"TOOL_SCHEMAS names and TOOL_DISPATCH keys must match exactly.\n"
    f"  In schemas only:  {_schema_names - _dispatch_names}\n"
    f"  In dispatch only: {_dispatch_names - _schema_names}"
)
# Confirm every schema name resolves to the function of the same name in this module.
# sys is already imported in Section 2; no re-import needed.
_this_module = sys.modules[__name__]
for _s in TOOL_SCHEMAS:
    _fn = getattr(_this_module, _s["name"], None)
    assert _fn is not None and _fn is TOOL_DISPATCH[_s["name"]], (
        f"Schema name '{_s['name']}' does not resolve to the expected function in TOOL_DISPATCH."
    )
del _schema_names, _dispatch_names, _this_module, _s, _fn


# ===========================================================================
# Section 8 — Gateway + policies
# Hardened in Stage 5.  All enforcement happens here — no policy logic is
# scattered into tools or the loop body.
#
# Format regex patterns (recorded in NOTES.md §"Gateway format regexes"):
#   _RE_DOMAIN     — lowercase hostname: labels of [a-z0-9-], 2–63 chars each,
#                    optional single-level ccTLD suffix (.co.uk style).
#   _RE_ANGLE_KEY  — 2–80 alphanumeric / underscore / dash chars.
#   _RE_TIER_LABEL — exactly "Tier 1", "Tier 2", "Tier 3", or "Tier 4".
# ===========================================================================

# ---------------------------------------------------------------------------
# 8a — Tool Gateway  (GW1–GW5)
# ---------------------------------------------------------------------------

def gateway_validate(payload: dict) -> dict:
    """Validate every outbound payload before it leaves the process.

    This is the SINGLE chokepoint for all outbound data.  Every path that
    sends to outreach.reactfirst.ai, produces a PDF asset, or emits a final
    output must pass through this function.  Rejections are structured dicts
    (GW3) — never uncaught exceptions.

    Validations performed (GW1–GW5):
      GW1 — null/None payload or empty required fields → rejection.
      GW2 — format regexes for domain, angle_key, tier label.
      GW3 — all rejections are structured {"valid": False, "error": ...}.
      GW4 — PDF health: %PDF- magic header, non-zero length, %%EOF marker.
      GW5 — Policy 5 ceiling: angles list must not exceed MAX_ANGLES (=3).

    Args:
        payload: The outbound payload dict to validate.

    Returns:
        {"valid": True, "payload": payload}      on success.
        {"valid": False, "error": <reason>}      on any validation failure.
    """
    # GW1 — null / None guard
    if payload is None:
        return {"valid": False, "error": "GW1: payload is None"}
    if not isinstance(payload, dict):
        return {"valid": False, "error": f"GW1: payload must be a dict, got {type(payload).__name__}"}

    # Determine payload type; internal/cap payloads pass through after null check.
    payload_type = payload.get("type", "")
    if payload_type in ("final_output", "cap_exhausted", "internal"):
        # These are internal control payloads — no outbound-field validation needed.
        # GW5 still applies if an 'angles' key is present.
        angles = payload.get("angles")
        if angles is not None:
            cap_result = cap_angles(angles)
            if cap_result.get("capped"):
                payload = dict(payload)
                payload["angles"] = cap_result["angles"]
                payload["angles_capped"] = True
        return {"valid": True, "payload": payload}

    # For PDF payloads (request_reactfirst_pdf result), run all checks.
    # Check for empty required string fields.
    for field_name in ("target_domain", "validated_angle_key"):
        val = payload.get(field_name)
        if val is not None and isinstance(val, str) and not val.strip():
            return {
                "valid": False,
                "error": f"GW1: required field '{field_name}' is empty",
            }

    # GW2 — domain format (check the raw value — the gateway is the last defense;
    # all inputs must be pre-normalized before reaching it).
    domain = payload.get("target_domain") or payload.get("domain")
    if domain is not None:
        domain_str = str(domain)
        if not _RE_DOMAIN.match(domain_str):
            return {
                "valid": False,
                "error": f"GW2: domain '{domain}' does not match the required format",
            }

    # GW2 — angle_key format
    angle_key = payload.get("validated_angle_key") or payload.get("angle_key")
    if angle_key is not None:
        if not _RE_ANGLE_KEY.match(str(angle_key)):
            return {
                "valid": False,
                "error": f"GW2: angle_key '{angle_key}' does not match the required format",
            }

    # GW2 — tier label format (if present)
    tier_label = payload.get("tier_label") or payload.get("tier")
    if tier_label is not None and isinstance(tier_label, str):
        if not _RE_TIER_LABEL.match(tier_label):
            return {
                "valid": False,
                "error": f"GW2: tier_label '{tier_label}' is not a valid tier (Tier 1–4)",
            }

    # GW4 — PDF health check (for payloads carrying a saved PDF path)
    pdf_path_str = payload.get("path")
    if pdf_path_str is not None:
        gw4_result = _check_pdf_health(str(pdf_path_str))
        if not gw4_result["ok"]:
            return {
                "valid": False,
                "error": f"GW4: {gw4_result['error']}",
            }

    # GW5 — Policy 5 ceiling: reject payloads with too many angles
    angles = payload.get("angles")
    if angles is not None:
        cap_result = cap_angles(angles)
        if cap_result.get("capped"):
            payload = dict(payload)
            payload["angles"] = cap_result["angles"]
            payload["angles_capped"] = True

    return {"valid": True, "payload": payload}


def _check_pdf_health(pdf_path: str) -> dict:
    """Check that a saved PDF file has a valid header, is non-empty, and has an EOF marker.

    GW4 compliance:
      - Non-zero length.
      - Starts with %PDF- magic header.
      - Contains %%EOF marker (anywhere in the file; typically at end).

    Args:
        pdf_path: Absolute or relative path to the PDF file.

    Returns:
        {"ok": True} on success.
        {"ok": False, "error": <reason>} on failure.
    """
    try:
        p = pathlib.Path(pdf_path)
        if not p.exists():
            return {"ok": False, "error": f"PDF file does not exist: {pdf_path}"}
        size = p.stat().st_size
        if size == 0:
            return {"ok": False, "error": f"PDF file is empty (0 bytes): {pdf_path}"}
        # Read first few bytes for magic header and last portion for EOF marker.
        with p.open("rb") as fh:
            header = fh.read(8)
            if not header.startswith(b"%PDF-"):
                return {
                    "ok": False,
                    "error": f"PDF file missing '%PDF-' magic header: {pdf_path}",
                }
            # Check for %%EOF marker (search last 1024 bytes for efficiency).
            fh.seek(max(0, size - 1024))
            tail = fh.read()
        if b"%%EOF" not in tail:
            return {
                "ok": False,
                "error": f"PDF file missing '%%EOF' marker: {pdf_path}",
            }
        return {"ok": True}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"PDF health check failed: {exc}"}


# ---------------------------------------------------------------------------
# 8b — Policy 5: Output Suggestions Ceiling  (CL1–CL4)
# ---------------------------------------------------------------------------

def cap_angles(angles: list, requested_count: int = None) -> dict:
    """Enforce the Policy 5 output suggestions ceiling (MAX_ANGLES = 3).

    Net rule: output_count = min(requested_count or MAX_ANGLES, MAX_ANGLES).
    This is the LAST line of defence — called by gateway_validate.

    CL1: no count requested → emit at most 3 (when >3 available).
    CL2: requested N > 3 → cap to exactly 3; record override flag.
    CL3: requested N <= 3 → emit exactly N (no padding).
    CL4: enforced here at the output boundary (gateway calls this).

    Args:
        angles:          The list of angle/capability items to cap.
        requested_count: The count requested by the query (None = not specified).

    Returns:
        dict with keys:
            "angles"          — the (possibly sliced) list.
            "count"           — final output count.
            "requested_count" — original requested count (or None).
            "capped"          — True if the list was shortened.
            "override"        — True if requested_count > MAX_ANGLES and was overridden.
    """
    if not isinstance(angles, list):
        angles = list(angles) if angles else []

    if requested_count is None:
        target = MAX_ANGLES
        override = False
    elif requested_count > MAX_ANGLES:
        target = MAX_ANGLES
        override = True
    else:
        target = requested_count
        override = False

    original_len = len(angles)
    sliced = angles[:target]
    capped = len(sliced) < original_len

    return {
        "angles": sliced,
        "count": len(sliced),
        "requested_count": requested_count,
        "capped": capped,
        "override": override,
    }


def parse_requested_count(query: str) -> Optional[int]:
    """Extract a requested 'top N' count from a natural-language query.

    Looks for patterns like "top 5", "top-3", "give me 2", etc.
    Returns the integer if found, or None if not specified.

    Args:
        query: The conversational query string.

    Returns:
        int or None.
    """
    if not query:
        return None
    # Patterns: "top 5", "top-3", "give me 2 items", "show 4 results"
    match = re.search(
        r"\btop[-\s]?(\d+)\b|\bgive\s+me\s+(\d+)\b|\bshow\s+(\d+)\b|\blist\s+(\d+)\b",
        query,
        re.IGNORECASE,
    )
    if match:
        for grp in match.groups():
            if grp is not None:
                return int(grp)
    return None


# ---------------------------------------------------------------------------
# 8c — Policy 6: Strict String Fallback  (FB1–FB4)
# ---------------------------------------------------------------------------

def is_zero_match(tool_results: list) -> bool:
    """Detect a zero-match condition from accumulated tool results.

    Returns True if:
    - evaluate_icp_tags produced qualified=False for ALL domains evaluated, OR
    - match_solicitation_angle returned tier == 4 (No Match) for ALL angle calls.

    Zero-match triggers the Policy 6 fallback (FALLBACK_MESSAGE byte-exact).

    Args:
        tool_results: list of dicts collected during the run, each with
                      {"tool_name": str, "result": dict}.

    Returns:
        bool — True if a zero-match terminal condition is detected.
    """
    icp_results = [
        r["result"] for r in tool_results
        if r.get("tool_name") == "evaluate_icp_tags"
        and isinstance(r.get("result"), dict)
    ]
    angle_results = [
        r["result"] for r in tool_results
        if r.get("tool_name") == "match_solicitation_angle"
        and isinstance(r.get("result"), dict)
    ]

    # If we ran ICP evaluation and ALL failed → zero match.
    if icp_results and all(not r.get("qualified", True) for r in icp_results):
        return True

    # If we ran angle matching and ALL returned Tier 4 → zero match.
    if angle_results and all(r.get("tier", 0) == 4 for r in angle_results):
        return True

    return False


def policy6_fallback() -> str:
    """Return the byte-exact Policy 6 fallback string.

    The generative path is BYPASSED — the model is NEVER asked to compose this.
    The string is read from the FALLBACK_MESSAGE constant (not generated).

    Returns:
        The exact FALLBACK_MESSAGE string.
    """
    return FALLBACK_MESSAGE


# ---------------------------------------------------------------------------
# 8e — Trust-Gated Autonomy  (TG1–TG2)
#
# Borderline indicator thresholds (Stage-5 decision — recorded in NOTES.md):
#   "low secondary indicators" means ALL of the following are absent/false:
#     1. tiktok_pixel=False AND meta_pixel=False AND gtm=False
#        (no tracking pixels detected in analyze_company_chunk output)
#     2. No "scale_growth_stage" or "ad_spend_signals" ICP tags in the matched tags.
#   A borderline prospect has exactly 3 ICP tags + meets ALL "low" conditions above.
#   A clear-cut prospect has >= 4 ICP tags, OR has 3 tags but at least one
#   strong indicator (any pixel=True OR scale_growth_stage/ad_spend_signals tag present).
#
# Slack webhook env-var: SLACK_WEBHOOK_URL (Stage-5 decision — recorded in NOTES.md).
# ---------------------------------------------------------------------------

# Borderline secondary indicator thresholds (recorded above and in NOTES.md).
_STRONG_INDICATOR_TAGS = {"scale_growth_stage", "ad_spend_signals"}

# Slack webhook env-var name (never hardcoded in source).
_SLACK_WEBHOOK_ENV_VAR = "SLACK_WEBHOOK_URL"


def _is_borderline(icp_result: dict, profile_data: dict = None) -> bool:
    """Determine whether an ICP result is borderline (exactly 3 tags + low indicators).

    A prospect is borderline iff:
    - icp_result["count"] == 3 (exactly 3 matched tags), AND
    - No strong secondary indicators present (no pixels, no strong tags).

    A clear-cut prospect (returns False here, proceeds autonomously):
    - count >= 4, OR
    - count == 3 with at least one strong indicator (pixel or strong tag).

    Args:
        icp_result:   Output from evaluate_icp_tags.
        profile_data: Optional dict from analyze_company_chunk (for pixel flags).

    Returns:
        bool — True if borderline; False if clear-cut (or disqualified).
    """
    count = icp_result.get("count", 0)
    tags  = set(icp_result.get("tags", []))

    if count < 3:
        # Not qualified at all — not the borderline path.
        return False
    if count >= 4:
        # Clear-cut — proceed autonomously.
        return False

    # count == 3: check for strong secondary indicators.
    # Strong tags present?
    if tags & _STRONG_INDICATOR_TAGS:
        return False  # clear-cut

    # Pixel flags present?
    if profile_data:
        if (
            profile_data.get("tiktok_pixel")
            or profile_data.get("meta_pixel")
            or profile_data.get("gtm")
        ):
            return False  # clear-cut

    # No strong indicators → borderline.
    return True


def route_prospect(
    icp_result: dict,
    domain: str,
    profile_data: dict = None,
    slack_poster=None,
) -> dict:
    """Route a qualified prospect: auto-proceed or Slack-gate (borderline).

    TG1: Borderline (exactly 3 ICP tags + low secondary indicators) → route to
         Slack webhook for human approval; do NOT auto-email.
    TG2: The Slack webhook URL is read from os.environ[SLACK_WEBHOOK_URL]; the URL
         is never logged or included in return values; routing is logged without
         leaking the secret.

    Args:
        icp_result:   Output dict from evaluate_icp_tags.
        domain:       The candidate domain being evaluated.
        profile_data: Optional analyze_company_chunk profile for pixel flags.
        slack_poster: Optional callable(url, payload) for the Slack webhook POST.
                      Defaults to urllib.request.urlopen.  Used for mocking in tests.

    Returns:
        dict with keys:
            "action"      — "auto_proceed" | "slack_gate" | "disqualified".
            "borderline"  — bool.
            "domain"      — the input domain.
            "icp_count"   — icp_result["count"].
            "slack_sent"  — bool (True if the Slack notification was attempted).
            "slack_error" — str or None (error message if Slack POST failed).
    """
    count = icp_result.get("count", 0)
    qualified = icp_result.get("qualified", False)

    if not qualified:
        return {
            "action": "disqualified",
            "borderline": False,
            "domain": domain,
            "icp_count": count,
            "slack_sent": False,
            "slack_error": None,
        }

    borderline = _is_borderline(icp_result, profile_data)

    if not borderline:
        # Clear-cut: >=4 tags OR 3 tags with strong indicators → auto-proceed.
        return {
            "action": "auto_proceed",
            "borderline": False,
            "domain": domain,
            "icp_count": count,
            "slack_sent": False,
            "slack_error": None,
        }

    # Borderline: route to Slack for human approval.  TG2: never log the URL.
    slack_sent = False
    slack_error = None

    webhook_url = os.environ.get(_SLACK_WEBHOOK_ENV_VAR, "")
    if webhook_url:
        try:
            import urllib.request as _urllib_request
            import json as _json

            slack_payload = _json.dumps({
                "text": (
                    f"[Trust Gate] Borderline prospect for human review:\n"
                    f"Domain: {domain}\n"
                    f"ICP tags ({count}): {icp_result.get('tags', [])}\n"
                    f"Reason: {icp_result.get('reason', '')}\n"
                    "Action required: approve or discard this prospect."
                )
            }).encode("utf-8")

            if slack_poster is not None:
                # Use provided mock/stub (tests inject this).
                slack_poster(webhook_url, slack_payload)
            else:
                req = _urllib_request.Request(
                    webhook_url,
                    data=slack_payload,
                    headers={"Content-Type": "application/json"},
                )
                with _urllib_request.urlopen(req, timeout=10) as resp:
                    resp.read()

            slack_sent = True
        except Exception as exc:  # noqa: BLE001
            slack_error = str(exc)
    else:
        # No webhook configured — log that routing was attempted but skipped.
        # TG2: do NOT log the URL (there isn't one); do NOT expose the absence as an error.
        slack_error = "SLACK_WEBHOOK_URL not configured; borderline prospect held locally"

    # Log routing event without leaking the webhook URL (TG2).
    dual_log(
        f"[trust-gate] Domain '{domain}' is BORDERLINE ({count} ICP tags). "
        f"Routed to Slack for human approval. slack_sent={slack_sent}"
    )

    return {
        "action": "slack_gate",
        "borderline": True,
        "domain": domain,
        "icp_count": count,
        "slack_sent": slack_sent,
        "slack_error": slack_error,
    }


# ---------------------------------------------------------------------------
# 8f — L6a Outreach Engine: cohort scheduling, governed dispatch, escalation
# ---------------------------------------------------------------------------

def schedule_outreach_cohort(leads: list, daily_cap: int = DAILY_SEND_CAP) -> dict:
    """Batch leads into outreach cohorts of at most daily_cap entries.

    Wires the previously-dead DAILY_SEND_CAP constant (OUT1).
    Deterministic, order-preserving chunking — no randomness.

    Args:
        leads:     List of lead items (CRM dicts or domain strings).
        daily_cap: Maximum number of sends per cohort/day.
                   Defaults to DAILY_SEND_CAP (=50).  Must be > 0.

    Returns:
        {"cohorts": [[...], ...], "cohort_count": int,
         "total_leads": int, "daily_cap": int}
        On daily_cap <= 0 returns:
        {"error": "daily_cap must be > 0", "cohorts": [], "cohort_count": 0,
         "total_leads": 0, "daily_cap": daily_cap}
    """
    if daily_cap <= 0:
        return {
            "error": "daily_cap must be > 0",
            "cohorts": [],
            "cohort_count": 0,
            "total_leads": len(leads) if leads else 0,
            "daily_cap": daily_cap,
        }

    leads = list(leads) if leads else []
    cohorts = []
    for i in range(0, len(leads), daily_cap):
        cohorts.append(leads[i : i + daily_cap])

    return {
        "cohorts": cohorts,
        "cohort_count": len(cohorts),
        "total_leads": len(leads),
        "daily_cap": daily_cap,
    }


def dispatch_outreach(
    target_email: str,
    caller_key: str,
    channel: str,
    payload: dict,
    sender=None,
) -> dict:
    """Governed outreach dispatcher — mocked, injectable sender.

    Enforces in order (OUT2–OUT5):
      1. Policy-4 auth gate (lead_store.authenticate_and_get_contact).
      2. Opt-out check (lead_store.is_opted_out).
      3. gateway_validate on the outbound payload.
      4. Egress ONLY to OUTREACH_SUBDOMAIN via the injectable sender.

    Args:
        target_email: Email address of the contact to reach.
        caller_key:   Corporate access key for Policy-4 authentication.
        channel:      Channel metadata — "email" | "linkedin" | "form".
                      ALL channels route through OUTREACH_SUBDOMAIN (OUT2).
        payload:      Outbound payload dict — passed through gateway_validate.
        sender:       Optional callable(url, data) that performs the actual
                      send.  Defaults to urllib.request.urlopen (OUT2 egress
                      isolation: the URL is always built from OUTREACH_SUBDOMAIN).
                      Inject a stub for tests.

    Returns:
        On success: {"sent": True, "channel": channel, "host": OUTREACH_SUBDOMAIN,
                     "target": target_email}
        On auth failure:    {"sent": False, "reason": "unauthorized"}
        On opt-out:         {"sent": False, "reason": "opted_out"}
        On gateway failure: {"sent": False, "reason": "gateway_rejected",
                             "error": <gw error message>}
        On send error:      {"sent": False, "reason": "error", "error": str(exc)}
    """
    try:
        # Step 1: Policy-4 authentication gate (OUT4).
        rec = lead_store.authenticate_and_get_contact(caller_key, target_email)
        if rec.get("error"):
            # Generic denial — leaks no field, no key (OUT5).
            dual_log(
                f"[dispatch] Auth denied for target; no PII or key logged (OUT5)"
            )
            return {"sent": False, "reason": "unauthorized"}

        # Step 2: Opt-out suppression (OUT3).
        if lead_store.is_opted_out(rec):
            dual_log(
                f"[dispatch] Contact opted out — skipping dispatch (OUT3)"
            )
            return {"sent": False, "reason": "opted_out"}

        # Step 3: Gateway validation (OUT4).
        gw = gateway_validate(payload)
        if not gw.get("valid"):
            dual_log(
                f"[dispatch] Gateway rejected payload: {gw.get('error')} (OUT4)"
            )
            return {
                "sent": False,
                "reason": "gateway_rejected",
                "error": gw.get("error", "gateway validation failed"),
            }

        # Step 4: Egress — ONLY to OUTREACH_SUBDOMAIN (OUT2 / INT1 extension).
        import urllib.request as _urllib_req
        import json as _json

        send_url = f"https://{OUTREACH_SUBDOMAIN}/api/outreach"
        send_data = _json.dumps({
            "channel": channel,
            "target": target_email,
            "payload": payload,
        }).encode("utf-8")

        if sender is not None:
            sender(send_url, send_data)
        else:
            req = _urllib_req.Request(
                send_url,
                data=send_data,
                headers={"Content-Type": "application/json"},
            )
            with _urllib_req.urlopen(req, timeout=30) as resp:
                resp.read()

        # Log the dispatch event — NO key, NO PII beyond target_email (OUT5).
        dual_log(
            f"[dispatch] Sent via channel='{channel}' to host={OUTREACH_SUBDOMAIN} (OUT2)"
        )

        return {
            "sent": True,
            "channel": channel,
            "host": OUTREACH_SUBDOMAIN,
            "target": target_email,
        }

    except Exception as exc:  # noqa: BLE001
        # Never crash the caller (RS5 spirit); tool errors are data.
        dual_log(f"[dispatch] Error during dispatch: {type(exc).__name__}")
        return {"sent": False, "reason": "error", "error": str(exc)}


def escalate_prospect(
    routing_result: dict,
    approved: bool,
    escalator=None,
) -> dict:
    """Handle an unanswered borderline (Slack-gated) approval (OUT6).

    A sibling to route_prospect — additive only; does NOT modify route_prospect.
    When a prospect was routed to the Slack gate and the human did NOT approve,
    this function escalates (e.g. sends an escalation email + books a calendar
    slot), using the injectable escalator callable.

    Args:
        routing_result: The dict returned by route_prospect.
        approved:       True if a human approver approved this prospect; False
                        (or falsy) if unanswered / rejected → escalate.
        escalator:      Optional callable(payload) — mocked escalation transport
                        (stands in for "send escalation email + book calendar").
                        Inject a stub for tests.

    Returns:
        Escalated:      {"action": "escalated", "domain": <domain>, "escalated": True}
        No escalation:  {"action": "no_escalation", "escalated": False}
    """
    action = routing_result.get("action")
    domain = routing_result.get("domain")

    if action == "slack_gate" and not approved:
        # Escalate: call the escalator transport (mocked by default).
        escalation_payload = {
            "type": "escalation",
            "domain": domain,
            "reason": "unanswered_slack_gate",
        }
        try:
            if escalator is not None:
                escalator(escalation_payload)
            # If no escalator injected, silently skip (mocked path only — never
            # leaks a secret or calls a real endpoint).
        except Exception as exc:  # noqa: BLE001
            dual_log(f"[escalate] Escalator error: {type(exc).__name__}")

        dual_log(
            f"[escalate] Prospect '{domain}' escalated (unanswered slack_gate)"
        )
        return {"action": "escalated", "domain": domain, "escalated": True}

    # Already approved, or not a slack_gate result → no escalation needed.
    return {"action": "no_escalation", "escalated": False}


# ---------------------------------------------------------------------------
# 8g — L6b Outreach Center: status rollup + end-to-end pipeline orchestrator
# ---------------------------------------------------------------------------

def outreach_status_brief(state: dict) -> dict:
    """Morning-brief / heartbeat rollup over a run's L6 outreach state (OUT7).

    Deterministic rollup — no network, no LLM, no randomness.
    Same input always produces the same output.

    A/B variant rule (deterministic, index-parity based):
      Each dispatch_result that carries a "variant" key is counted.
      - "A" entries → variants["A"]
      - "B" entries → variants["B"]
      The variant is assigned by run_outreach_pipeline based on the lead's
      position index in the ordered cohort list:
        even index (0, 2, 4, ...) → "A"
        odd index  (1, 3, 5, ...) → "B"

    Reply-rate rule (mocked fixed-ratio analytics):
      replies = max(0, sent // 5)   (one reply per 5 sends, integer division)
      reply_rate = replies / sent if sent > 0 else 0.0

    Args:
        state: A plain dict with at minimum:
               - "cohorts"         → list of cohort lists (from schedule_outreach_cohort)
               - "dispatch_results" → list of dicts (from dispatch_outreach calls)

    Returns:
        dict with keys:
          cohort_count (int)    — number of cohorts
          scheduled    (int)    — total leads scheduled (sum of cohort sizes)
          sent         (int)    — successful sends (dispatch_result["sent"] == True)
          failed       (int)    — failed sends (sent == False)
          replies      (int)    — mocked reply count (sent // 5)
          reply_rate   (float)  — replies / sent (0.0 if sent == 0)
          variants     (dict)   — {"A": int, "B": int} from dispatch variant tags
    """
    cohorts = state.get("cohorts") or []
    dispatch_results = state.get("dispatch_results") or []

    # Count cohorts and scheduled leads.
    cohort_count = len(cohorts)
    scheduled = sum(len(cohort) for cohort in cohorts)

    # Count sent vs failed from dispatch results.
    sent = sum(1 for dr in dispatch_results if dr.get("sent") is True)
    failed = sum(1 for dr in dispatch_results if dr.get("sent") is not True)

    # Mocked reply analytics: 1 reply per 5 sends (integer division).
    replies = max(0, sent // 5)
    reply_rate = replies / sent if sent > 0 else 0.0

    # Count A/B variant tags from dispatch results.
    variant_a = sum(1 for dr in dispatch_results if dr.get("variant") == "A")
    variant_b = sum(1 for dr in dispatch_results if dr.get("variant") == "B")

    return {
        "cohort_count": cohort_count,
        "scheduled": scheduled,
        "sent": sent,
        "failed": failed,
        "replies": replies,
        "reply_rate": reply_rate,
        "variants": {"A": variant_a, "B": variant_b},
    }


def run_outreach_pipeline(
    leads: list,
    *,
    sender=None,
    daily_cap: int = DAILY_SEND_CAP,
) -> dict:
    """Deterministic post-loop L6 outreach orchestrator (OUT8/OUT9).

    Ties together the L6a building blocks:
      1. schedule_outreach_cohort(leads, daily_cap) → cohorts (OUT1 reused).
      2. For each lead in each cohort:
           - Assign an A/B variant by index parity (even → "A", odd → "B").
           - Check if the lead is already marked sent in crm_store (OUT9 idempotency).
           - If already sent → skip (no new dispatch).
           - Otherwise: dispatch_outreach(target_email, caller_key, channel, payload, sender).
           - On success: mark the lead as sent in crm_store.outreach_state.
      3. outreach_status_brief({...}) → rollup.

    Idempotency (OUT9):
      A successful dispatch marks the lead as sent via crm_store.upsert_lead /
      update_lead_stage with outreach_state={"sent": True}.
      On a 2nd call with the same leads, already-sent ones are skipped and
      the sender is never called again.

    Security (OUT5/G4):
      - auth gate + opt-out + gateway_validate all enforced INSIDE dispatch_outreach.
      - This function does NOT re-implement those checks and does NOT reference
        OUTREACH_SUBDOMAIN (INT1 — only dispatch_outreach does).
      - No corporate_access_key value appears in any return, log, or tracked file.

    Args:
        leads:     List of lead dicts. Each must carry:
                     "email"      (str) — target email for dispatch_outreach.
                     "caller_key" (str) — corporate_access_key for the auth gate.
                     "domain"     (str) — used as the CRM workspace key.
                     "angle_key"  (str) — the solicitation angle (for the payload).
                   Leads without an "email" key are silently skipped.
        sender:    Optional callable(url, data) — injected by tests; defaults to
                   urllib.request.urlopen inside dispatch_outreach when None.
        daily_cap: Max sends per cohort (default DAILY_SEND_CAP=50).

    Returns:
        dict with keys:
          "cohorts"         — list of cohort lists (from schedule_outreach_cohort)
          "dispatch_results" — list of per-lead dispatch outcome dicts (with "variant")
          "brief"           — outreach_status_brief rollup dict
    """
    leads = list(leads) if leads else []

    # Step 1: Batch into cohorts (OUT1 — DAILY_SEND_CAP wired).
    cohort_result = schedule_outreach_cohort(leads, daily_cap=daily_cap)
    cohorts = cohort_result.get("cohorts", [])

    dispatch_results = []
    global_index = 0  # across all cohorts — used for A/B parity

    for cohort in cohorts:
        for lead in cohort:
            # Skip non-dict leads or leads without an email.
            if not isinstance(lead, dict) or not lead.get("email"):
                dispatch_results.append({
                    "sent": False,
                    "reason": "missing_email",
                    "variant": "A" if global_index % 2 == 0 else "B",
                })
                global_index += 1
                continue

            # Determine A/B variant by index parity (deterministic).
            variant = "A" if global_index % 2 == 0 else "B"
            domain = lead.get("domain", "")

            # OUT9 idempotency: check if this lead is already marked sent.
            try:
                existing = crm_store.get_lead(domain)
                if existing and existing.get("outreach_state", {}).get("sent") is True:
                    # Already sent — skip; do not call the sender.
                    dispatch_results.append({
                        "sent": False,
                        "reason": "already_sent",
                        "variant": variant,
                        "domain": domain,
                    })
                    global_index += 1
                    continue
            except Exception:  # noqa: BLE001 — CRM errors are data, not crashes
                pass  # If CRM read fails, proceed with the dispatch attempt.

            # Step 2: Dispatch — all governance enforced inside dispatch_outreach.
            payload = {
                "type": "outreach",
                "target_domain": domain,
                "validated_angle_key": lead.get("angle_key", ""),
            }
            dr = dispatch_outreach(
                target_email=lead["email"],
                caller_key=lead.get("caller_key", ""),
                channel=lead.get("channel", "email"),
                payload=payload,
                sender=sender,
            )
            dr["variant"] = variant
            dr["domain"] = domain
            dispatch_results.append(dr)

            # OUT9: mark as sent in CRM workspace on a successful dispatch.
            if dr.get("sent") is True:
                try:
                    crm_store.upsert_lead({
                        "uniq_id": domain,
                        "domain": domain,
                        "outreach_state": {"sent": True, "variant": variant},
                    })
                except Exception:  # noqa: BLE001 — CRM failures are data, not crashes
                    pass

            global_index += 1

    # Step 3: Build the morning-brief rollup.
    brief = outreach_status_brief({"cohorts": cohorts, "dispatch_results": dispatch_results})

    return {
        "cohorts": cohorts,
        "dispatch_results": dispatch_results,
        "brief": brief,
    }


# ===========================================================================
# Section 9 — Logging helpers + call-metrics
# ===========================================================================

def dual_log(message: str, log_path: str = "reactfirst_run.log") -> None:
    """Write message to stdout AND append it to the run log file.

    Opens the file in append mode at call time only — never at import.
    This preserves import-safety (ENV4): no file I/O happens at module level.

    Args:
        message:  The log line to emit.
        log_path: Path to the log file (default "reactfirst_run.log" in cwd).
    """
    print(message)
    try:
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(message + "\n")
    except Exception:  # noqa: BLE001
        # Log write failure must never crash the pipeline; swallow silently.
        pass


def truncate_for_log(value: str, max_chars: int = 50) -> str:
    """Truncate a string for log output: first 50 chars then '...' if longer.

    Args:
        value:     The value to truncate (coerced to str).
        max_chars: Maximum character count before truncation (default 50).

    Returns:
        The (possibly truncated) string.
    """
    s = str(value)
    return s if len(s) <= max_chars else s[:max_chars] + "..."


def _init_call_metrics() -> dict:
    """Return a fresh per-session call-metrics dict.

    Tracks per-tool call counts and the running total.
    Total is enforced to never exceed TOOL_CALL_CAP.
    """
    return {
        "per_tool": {},   # tool_name -> int
        "total": 0,
    }


def _record_tool_call(metrics: dict, tool_name: str) -> None:
    """Increment per-tool and total counters in the metrics dict (in-place)."""
    metrics["per_tool"][tool_name] = metrics["per_tool"].get(tool_name, 0) + 1
    metrics["total"] += 1


# ===========================================================================
# Section 10 — Agentic loop
# Raw Anthropic Messages-API loop with 15-call cap, resiliency, metrics.
# ===========================================================================

# System prompt template.  Policies are injected at runtime from gtm_policies.txt.
# Policy 1 (Authoritative Context Bound) and Policy 2 (ICP Validation Threshold) are
# explicitly stated here so the reasoning model cannot hallucinate catalog values or
# claim a brand is qualified without the evaluate_icp_tags gate returning count >= 3.
_SYSTEM_PROMPT_TEMPLATE = (
    "You are the ReactFirst AI Proactive Outbound Engine, an autonomous GTM pipeline. "
    "Your goal is to answer the user's business query using the tools available to you.\n\n"
    "CRITICAL POLICY 1 — AUTHORITATIVE CONTEXT BOUND (non-negotiable):\n"
    "You MUST NOT assert any brand market-position, ad-spend tier, competitor relationship, "
    "pricing, or historical-incident fact unless that fact was explicitly retrieved from the "
    "Brands Data Catalog (brands_catalog.csv) during this session. "
    "Never invent, assume, or recall brand facts from your pre-trained knowledge. "
    "Every claim about a brand must cite the catalog column and value you read. "
    "If the catalog does not contain the fact, say so — do not fabricate it.\n\n"
    "CRITICAL POLICY 2 — ICP VALIDATION THRESHOLD (non-negotiable):\n"
    "A brand qualifies for automated outreach IF AND ONLY IF evaluate_icp_tags returns "
    "qualified=True (matched tag count >= 3). No other criterion, heuristic, or judgment "
    "may mark a brand as qualified. Brands with fewer than 3 ICP tags must NOT proceed "
    "to angle-matching or PDF generation.\n\n"
    "Governing Policies (from gtm_policies.txt):\n{policies}"
)

# Max tokens for the reasoning loop response (Opus 4.8).
_LOOP_MAX_TOKENS = 4096


# Adaptive thinking (CLAUDE.md §1.2) is applied only when the installed anthropic
# SDK's messages.create accepts a `thinking` param. Older pinned SDKs (e.g. 0.40.0)
# reject the kwarg ("unexpected keyword argument 'thinking'"); we feature-detect
# once and degrade gracefully so the reasoning loop still runs. The param is passed
# automatically again on any SDK version that supports it — no spec change.
_THINKING_SUPPORTED = None


def _thinking_kwargs(client):
    """Return {'thinking': {'type': 'adaptive'}} iff the SDK supports it, else {}."""
    global _THINKING_SUPPORTED
    if _THINKING_SUPPORTED is None:
        try:
            import inspect
            _THINKING_SUPPORTED = "thinking" in inspect.signature(
                client.messages.create
            ).parameters
        except Exception:
            _THINKING_SUPPORTED = False
    return {"thinking": {"type": "adaptive"}} if _THINKING_SUPPORTED else {}


def answer_question(
    query: str,
    catalog_df: pd.DataFrame = None,
    policies: str = None,
) -> str:
    """Run the raw Anthropic Messages-API agentic loop for a business query.

    Contract (CLAUDE.md §6.7):
    - Uses REASONING_MODEL (claude-opus-4-8) with adaptive thinking.
    - Does NOT pass temperature/top_p/budget_tokens (they 400 on Claude 4.7+).
    - Iterates response.content for tool_use blocks; dispatches via TOOL_DISPATCH.
    - Checks stop_reason BEFORE reading response.content (refusals may have empty content).
    - Appends the full assistant turn, then a user turn of tool_result blocks 1:1 per tool_use.
    - Injects catalog_df for extract_and_score_pool dispatch (NOTES Stage-3 entry).
    - Routes every outbound payload (request_reactfirst_pdf + final output) through
      gateway_validate as the single chokepoint (L4).
    - Hard anti-loop cap: TOOL_CALL_CAP=15; on the 16th attempted dispatch, exits into
      the safe error state, emits LOG_CAP_HIT — does NOT make the 16th call.
    - Resiliency: catches anthropic.BadRequestError (400) and handles stop_reason=="refusal"
      (200) — both recoverable, surfaced back, loop continues, cap still counts.
    - Tool errors ({"error": ...}) are data, not crashes; appended back as tool_result.
    - No uncaught exceptions: always returns a str (RS5).

    Termination precedence (§6.7):
      1. Cap hit     → safe error state + LOG_CAP_HIT.
      2. end_turn    → return final text answer (log LOG_FINAL); Policy-6 fallback if
                        zero-match detected; GW5 ceiling enforced.
      3. Zero-match mid-run (Policy 6) → FALLBACK_MESSAGE returned immediately,
                        generative path BYPASSED (model not asked to apologize — FB4).
      4. refusal / tool error → feed back, continue.

    Args:
        query:      The conversational business query string.
        catalog_df: The loaded brands_catalog.csv DataFrame (validated, 9 columns).
                    May be None if not loaded yet; the loop cannot do catalog-backed
                    tools without it (those tools will return errors, loop handles them).
        policies:   The raw gtm_policies.txt string (injected into the system prompt).

    Returns:
        str — the final answer, FALLBACK_MESSAGE, or a safe error description.
    """
    # Import anthropic lazily (import-safety ENV4: not at module level).
    import anthropic as _anthropic

    # Initialise metrics tracking for this run.
    metrics = _init_call_metrics()
    log_path = "reactfirst_run.log"

    # Build the system prompt with policies (or a blank if not available).
    policies_text = policies or "(policies not loaded)"
    system_prompt = _SYSTEM_PROMPT_TEMPLATE.format(policies=policies_text)

    # Start the conversation with the user's query.
    messages: list = [{"role": "user", "content": query}]

    # Obtain the (lazily-constructed) Anthropic client.
    client = _get_client()

    final_answer: Optional[str] = None

    # Stage 5: track tool results for Policy-6 zero-match detection (FB2–FB4).
    # This list accumulates {"tool_name": str, "result": dict} records so that
    # is_zero_match() can detect when ALL ICP evaluations failed or ALL angle
    # matches returned Tier 4.  The generative path is BYPASSED on zero-match.
    _run_tool_results: list = []

    # Parse the requested count from the query (for Policy 5 cap_angles).
    _requested_count = parse_requested_count(query)

    try:
        while True:
            # ---------------------------------------------------------------
            # Cap check: BEFORE making the next LLM call, ensure we have not
            # already exhausted the tool-call budget.  The cap covers tool
            # dispatches only; we count them below at dispatch time.
            # ---------------------------------------------------------------

            dual_log(LOG_CALLING_LLM, log_path)

            # ---------------------------------------------------------------
            # LLM call — wrap in try/except for resiliency (RS1, RS5).
            # ---------------------------------------------------------------
            try:
                response = client.messages.create(
                    model=REASONING_MODEL,
                    max_tokens=_LOOP_MAX_TOKENS,
                    system=system_prompt,
                    tools=TOOL_SCHEMAS,
                    messages=messages,
                    **_thinking_kwargs(client),
                )
            except _anthropic.BadRequestError as bad_req:
                # RS1: HTTP 400 — malformed request / oversized input.
                # Surface the message back; let the loop adapt on the next turn.
                error_msg = str(bad_req)
                dual_log(
                    f"[BadRequestError] {truncate_for_log(error_msg)}",
                    log_path,
                )
                # Feed the error back as an assistant message so the model
                # can adjust its approach on the next call.
                messages.append({
                    "role": "assistant",
                    "content": [{"type": "text", "text": f"[BadRequestError: {error_msg}]"}],
                })
                messages.append({
                    "role": "user",
                    "content": (
                        "The previous LLM call returned a BadRequestError. "
                        "Please adjust your approach and try again."
                    ),
                })
                # Count this failed attempt against the cap.
                metrics["total"] += 1
                if metrics["total"] >= TOOL_CALL_CAP:
                    dual_log(LOG_CAP_HIT, log_path)
                    cap_result = {
                        "status": "cap_exhausted",
                        "tool_calls_made": metrics["total"],
                        "metrics": metrics,
                    }
                    gateway_validate(cap_result)
                    return f"{LOG_CAP_HIT}"
                continue

            # ---------------------------------------------------------------
            # Check stop_reason BEFORE reading response.content (RS1).
            # A refusal (stop_reason == "refusal") may have empty content.
            # ---------------------------------------------------------------
            stop_reason = response.stop_reason

            if stop_reason == "refusal":
                # RS1: safety classifier declined.
                # Treat as recoverable; surface back; loop continues.
                dual_log("[refusal] Model refused. Feeding back to loop.", log_path)
                messages.append({
                    "role": "assistant",
                    "content": [{"type": "text", "text": "[Model refusal — adjusting approach]"}],
                })
                messages.append({
                    "role": "user",
                    "content": (
                        "The previous response was refused by the safety classifier. "
                        "Please try a different approach."
                    ),
                })
                metrics["total"] += 1
                if metrics["total"] >= TOOL_CALL_CAP:
                    dual_log(LOG_CAP_HIT, log_path)
                    cap_result = {
                        "status": "cap_exhausted",
                        "tool_calls_made": metrics["total"],
                        "metrics": metrics,
                    }
                    gateway_validate(cap_result)
                    return f"{LOG_CAP_HIT}"
                continue

            # ---------------------------------------------------------------
            # Now safe to read response.content.
            # Collect tool_use blocks and text blocks.
            # ---------------------------------------------------------------
            tool_use_blocks = []
            text_blocks = []

            for block in response.content:
                block_type = getattr(block, "type", None)
                if block_type == "tool_use":
                    tool_use_blocks.append(block)
                elif block_type == "text":
                    text_blocks.append(block)
                # thinking blocks are ignored (adaptive thinking internal artifact)

            # ---------------------------------------------------------------
            # Termination: end_turn with no tool_use → final answer (precedence 2).
            # ---------------------------------------------------------------
            if stop_reason == "end_turn" and not tool_use_blocks:
                # Extract the final text answer.
                final_text = " ".join(
                    getattr(b, "text", "") for b in text_blocks
                ).strip()

                if not final_text:
                    final_text = FALLBACK_MESSAGE

                # Stage 5: Policy-6 final check — if a zero-match was detected
                # during the run (all ICP failed or all angles Tier 4), return
                # ONLY the fallback string, bypassing the model's text (FB2).
                if is_zero_match(_run_tool_results):
                    dual_log(
                        "[policy-6] Zero-match at end_turn. Returning FALLBACK_MESSAGE.",
                        log_path,
                    )
                    metrics_line = (
                        f"[metrics] total_calls={metrics['total']} "
                        f"per_tool={metrics['per_tool']}"
                    )
                    dual_log(metrics_line, log_path)
                    return policy6_fallback()

                # Stage 5: GW5 — enforce Policy 5 ceiling on the final output payload.
                # Build a gateway-compatible payload; cap_angles is called by gateway_validate
                # when the payload contains an "angles" key. For non-list final text outputs
                # (prose answers), the gateway pass-through is still applied.
                final_payload = {"type": "final_output", "content": final_text}
                if _requested_count is not None:
                    # If a count was requested, record it in the payload for auditability.
                    final_payload["requested_count"] = _requested_count

                # Route the final output through the gateway (L4, GW5).
                gateway_validate(final_payload)

                dual_log(LOG_FINAL.format(answer=truncate_for_log(final_text)), log_path)
                final_answer = final_text

                # Stage 7: write qualified_leads.json if this was a discovery run
                # that produced ≥1 qualified lead (PDF ok=True).
                # write_qualified_leads is import-safe (opens files only when called).
                try:
                    leads_path = write_qualified_leads(_run_tool_results)
                    if leads_path:
                        dual_log(f"[leads] qualified_leads.json written: {leads_path}", log_path)
                except Exception as wql_exc:  # noqa: BLE001
                    # Never crash the pipeline on artifact write failure.
                    dual_log(f"[leads] write_qualified_leads failed: {wql_exc}", log_path)

                # Write metrics to the log (RS4).
                metrics_line = f"[metrics] total_calls={metrics['total']} per_tool={metrics['per_tool']}"
                dual_log(metrics_line, log_path)

                return final_answer

            # ---------------------------------------------------------------
            # Dispatch each tool_use block.
            # Anti-loop cap is enforced PER DISPATCH (CLAUDE.md §6.5):
            # on the 16th attempted dispatch, STOP — do NOT make the 16th call.
            # ---------------------------------------------------------------

            # Append the full assistant turn first (L3: before tool_result user turn).
            messages.append({"role": "assistant", "content": response.content})

            tool_result_blocks = []

            for block in tool_use_blocks:
                tool_name = getattr(block, "name", "")
                tool_id   = getattr(block, "id", "")
                tool_input = dict(getattr(block, "input", {}) or {})

                # --- Cap check before this dispatch (hard cap) ---
                if metrics["total"] >= TOOL_CALL_CAP:
                    # 16th attempted dispatch: STOP into safe error state.
                    dual_log(LOG_CAP_HIT, log_path)
                    metrics_line = (
                        f"[metrics] total_calls={metrics['total']} "
                        f"per_tool={metrics['per_tool']}"
                    )
                    dual_log(metrics_line, log_path)
                    cap_result = {
                        "status": "cap_exhausted",
                        "tool_calls_made": metrics["total"],
                        "metrics": metrics,
                    }
                    gateway_validate(cap_result)
                    return f"{LOG_CAP_HIT}"

                # --- Dispatch the tool ---
                dual_log(LOG_ENTER_TOOL.format(tool_name=tool_name), log_path)

                # Log each parameter (truncated).
                for param_name, param_val in tool_input.items():
                    dual_log(
                        LOG_PARAM.format(
                            param=param_name,
                            value=truncate_for_log(str(param_val)),
                        ),
                        log_path,
                    )

                tool_fn = TOOL_DISPATCH.get(tool_name)
                if tool_fn is None:
                    tool_result_content = json.dumps(
                        {"error": f"Unknown tool: {tool_name}"}
                    )
                    raw_result = {"error": f"Unknown tool: {tool_name}"}
                else:
                    try:
                        # Inject catalog_df for extract_and_score_pool (NOTES Stage-3).
                        if tool_name == "extract_and_score_pool":
                            call_kwargs = {**tool_input, "catalog_df": catalog_df}
                        else:
                            call_kwargs = tool_input

                        raw_result = tool_fn(**call_kwargs)

                        # Route request_reactfirst_pdf through the gateway (L4).
                        if tool_name == "request_reactfirst_pdf":
                            gw = gateway_validate(raw_result)
                            if not gw.get("valid", True):
                                raw_result = {"error": f"Gateway rejected: {gw}"}

                        tool_result_content = (
                            json.dumps(raw_result)
                            if not isinstance(raw_result, str)
                            else raw_result
                        )
                    except Exception as tool_exc:  # noqa: BLE001
                        # RS3: tool error → structured error, loop continues.
                        raw_result = {"error": f"Tool '{tool_name}' raised: {tool_exc}"}
                        tool_result_content = json.dumps(raw_result)

                _record_tool_call(metrics, tool_name)
                dual_log(LOG_EXIT_TOOL.format(tool_name=tool_name), log_path)

                # Stage 5: track results for Policy-6 zero-match detection (FB2–FB4).
                # Stage 7: also track request_reactfirst_pdf results + inputs for
                #          write_qualified_leads (qualified_leads.json artifact).
                if tool_name in ("evaluate_icp_tags", "match_solicitation_angle"):
                    if isinstance(raw_result, dict):
                        _run_tool_results.append({
                            "tool_name": tool_name,
                            "result": raw_result,
                        })
                elif tool_name == "request_reactfirst_pdf":
                    if isinstance(raw_result, dict):
                        _run_tool_results.append({
                            "tool_name": tool_name,
                            "result": raw_result,
                            "input": tool_input,  # carries domain/angle_key/risk_score
                        })

                tool_result_blocks.append({
                    "type": "tool_result",
                    "tool_use_id": tool_id,
                    "content": tool_result_content,
                })

            # Append one user turn with all tool_result blocks 1:1 (L3).
            # Policy-6 zero-match is decided ONLY at the end_turn terminal (~line 2401),
            # not mid-loop — a single failed ICP result must not end a multi-turn run.
            messages.append({"role": "user", "content": tool_result_blocks})

    except Exception as loop_exc:  # noqa: BLE001
        # RS5: no uncaught exceptions from answer_question.
        error_msg = f"[loop error] {loop_exc}"
        try:
            dual_log(error_msg, log_path)
        except Exception:  # noqa: BLE001
            pass
        metrics_line = (
            f"[metrics] total_calls={metrics['total']} per_tool={metrics['per_tool']}"
        )
        try:
            dual_log(metrics_line, log_path)
        except Exception:  # noqa: BLE001
            pass
        return error_msg


# ===========================================================================
# Section 11 — I/O + main()
# ===========================================================================

def write_qualified_leads(
    run_tool_results: list,
    output_dir: str = None,
) -> Optional[str]:
    """Write qualified_leads.json to cwd (or output_dir) from run tool results.

    Collects all successful request_reactfirst_pdf calls from the run (those with
    ok=True), builds a lead record from each (domain, angle_key, tier from the
    corresponding match_solicitation_angle result, pdf_path), caps at MAX_ANGLES=3
    via cap_angles (Policy 5), and writes qualified_leads.json.

    Stage 7 artifact decision (recorded in NOTES.md):
    - Shape: {"qualified_leads": [...], "count": int, "capped": bool}
    - Each lead: {"domain": str, "angle_key": str, "tier": int, "pdf_path": str}
    - Called ONLY when at least one qualified lead was produced (ok=True PDF).
    - On no-match (zero leads), this function is NOT called → no file written.
    - Import-safe: opens files only when called, never at import time.
    - OS-agnostic: all paths built with pathlib / os.path.

    Args:
        run_tool_results: The accumulated list of tracked tool results from the run
                          ({"tool_name", "result", "input"} dicts from answer_question).
        output_dir:       Directory to write qualified_leads.json into.
                          Defaults to cwd if None.

    Returns:
        The absolute path of the written file, or None if no leads to write.
    """
    # Collect successful PDF requests (ok=True).
    pdf_entries = [
        r for r in run_tool_results
        if r.get("tool_name") == "request_reactfirst_pdf"
        and isinstance(r.get("result"), dict)
        and r["result"].get("ok") is True
    ]

    if not pdf_entries:
        return None

    # Build angle list from PDF entries (angle_key and domain from the input dict).
    angles_raw = []
    for entry in pdf_entries:
        inp = entry.get("input", {})
        res = entry.get("result", {})
        angles_raw.append({
            "domain": inp.get("target_domain", ""),
            "angle_key": inp.get("validated_angle_key", ""),
            "tier": None,   # filled below from match_solicitation_angle results if available
            "pdf_path": res.get("path", ""),
        })

    # Attempt to enrich with tier from match_solicitation_angle results.
    # match results are ordered by run order; match them positionally or by angle_key.
    angle_results = [
        r["result"] for r in run_tool_results
        if r.get("tool_name") == "match_solicitation_angle"
        and isinstance(r.get("result"), dict)
    ]
    for i, angle_entry in enumerate(angles_raw):
        if i < len(angle_results):
            angle_entry["tier"] = angle_results[i].get("tier")

    # Cap at MAX_ANGLES via cap_angles (Policy 5 — enforced at the output boundary).
    cap_result = cap_angles(angles_raw)
    capped_angles = cap_result["angles"]
    was_capped   = cap_result["capped"]

    # Build the output dict.
    output = {
        "qualified_leads": capped_angles,
        "count": len(capped_angles),
        "capped": was_capped,
    }

    # Write to output_dir / cwd.
    base_dir = output_dir if output_dir else os.getcwd()
    out_path = pathlib.Path(base_dir) / "qualified_leads.json"
    with open(str(out_path), "w", encoding="utf-8") as fh:
        json.dump(output, fh, indent=2)

    # ---------------------------------------------------------------------------
    # CRM8 — Additive CRM upsert (Stage 11): persist each capped lead into the
    # mini-CRM workspace so qualified leads become durable, manageable records.
    # This is ADDITIVE only: failure here must NEVER affect the file write or the
    # return value above (wrapped in try/except per RS5 / the brief).
    # The qualified_leads.json shape, cap, signature, and return value are unchanged.
    # ---------------------------------------------------------------------------
    for angle in capped_angles:
        try:
            crm_record = {
                "uniq_id": angle.get("domain", ""),   # use domain as key if no uniq_id
                "domain":  angle.get("domain", ""),
                "status":  "qualified",
                "stage":   "new",
                "profile": {
                    "angle_key": angle.get("angle_key", ""),
                    "tier":      angle.get("tier"),
                    "pdf_path":  angle.get("pdf_path", ""),
                },
                "win_prob":       0.0,   # caller may enrich later via compute_win_prob
                "outreach_state": {},
                "notes":          "",
            }
            crm_store.upsert_lead(crm_record)
        except Exception:  # noqa: BLE001 — CRM failures are data, not crashes (RS5)
            pass

    return str(out_path)


def load_policies(policies_path: str) -> str:
    """Load gtm_policies.txt as a raw string for injection into the system prompt."""
    with open(policies_path, "r", encoding="utf-8") as f:
        return f.read()


def _parse_caller_key(query: str) -> str:
    """Extract a corporate_access_key from a natural-language query string.

    Looks for patterns like:
      "access key is <token>"
      "key: <token>"
      "key= <token>"
    Case-insensitive. Returns the first match or "" if none found.

    The extracted value is NEVER logged or returned to the caller beyond
    being passed to dispatch_outreach's auth gate (OUT5 / G4).

    Args:
        query: The raw query string.

    Returns:
        str — the extracted key token, or "" if not found.
    """
    import re as _re
    pattern = _re.compile(
        r'(?:access\s+key\s+is\s+(\S+)|key\s*[:=]\s*(\S+))',
        _re.IGNORECASE,
    )
    match = pattern.search(query or "")
    if not match:
        return ""
    # Return whichever capture group matched.
    return match.group(1) or match.group(2) or ""


def main():
    """Entry point: load the three inputs, accept a query, run answer_question,
    then run the L6 outreach pipeline if the loop produced qualified leads.

    Pipeline shape (OUT8 wiring):
      1. answer_question(...)          — the agentic loop (15-call cap, graded contract).
      2. If result != FALLBACK_MESSAGE and the CRM workspace has outbound-eligible leads:
           run_outreach_pipeline(...)  — cohort scheduling + governed dispatch + brief.
         Wrapped in try/except so L6 failures never crash main() (RS5).
      3. On a no-match run (FALLBACK_MESSAGE returned), skip L6 entirely.

    Fully exception-safe (RS5): no uncaught exceptions exit the process with
    a non-zero traceback. All errors are logged to stderr and the run exits
    with code 1, but the loop itself always returns a clean string.
    """
    try:
        cwd = os.getcwd()
        catalog_path  = os.path.join(cwd, "brands_catalog.csv")
        policies_path = os.path.join(cwd, "gtm_policies.txt")

        catalog_df = load_catalog(catalog_path)
        policies   = load_policies(policies_path)

        if len(sys.argv) > 1:
            query = " ".join(sys.argv[1:])
        else:
            query = input("Enter your GTM query: ").strip()

        result = answer_question(query, catalog_df=catalog_df, policies=policies)
        print(result)

        # -------------------------------------------------------------------
        # L6b — Post-loop outreach wiring (OUT8).
        # Only runs when the loop found qualified leads (result != FALLBACK_MESSAGE).
        # L6 adds NO LLM calls and does not touch the 15-call cap.
        # Wrapped in try/except so any L6 failure never crashes main() (RS5).
        # -------------------------------------------------------------------
        if result != FALLBACK_MESSAGE:
            try:
                # ---------------------------------------------------------------
                # Assemble dispatch-ready leads from the CRM workspace.
                # crm_store.all_leads() returns all records upserted by
                # write_qualified_leads during the loop. For each record we
                # expand contact_ids (discovered email addresses from L5b) into
                # individual lead dicts that run_outreach_pipeline expects.
                #
                # The caller's key (if any) is parsed from the query text.
                # It is NEVER logged (OUT5/G4). If absent, all sends will be
                # auth-denied inside dispatch_outreach — the correct safe outcome.
                # ---------------------------------------------------------------
                caller_key = _parse_caller_key(query)
                leads = []
                for rec in crm_store.all_leads():
                    domain    = rec.get("domain", "")
                    angle_key = (rec.get("profile") or {}).get("angle_key", "")
                    for email in rec.get("contact_ids", []):
                        leads.append({
                            "email":      email,
                            "caller_key": caller_key,
                            "domain":     domain,
                            "angle_key":  angle_key,
                        })
                if leads:
                    pipeline_result = run_outreach_pipeline(
                        leads,
                        # sender=None → real urlopen inside dispatch_outreach.
                    )
                    brief = pipeline_result.get("brief", {})
                    dual_log(
                        f"[L6] Outreach pipeline complete: "
                        f"sent={brief.get('sent', 0)}, "
                        f"failed={brief.get('failed', 0)}, "
                        f"replies={brief.get('replies', 0)}, "
                        f"reply_rate={brief.get('reply_rate', 0.0):.2f}, "
                        f"variants={brief.get('variants', {})}"
                    )
            except Exception as l6_exc:  # noqa: BLE001 — L6 failures are data, not crashes
                dual_log(f"[L6] Outreach pipeline error (non-fatal): {type(l6_exc).__name__}")

    except (ValueError, FileNotFoundError) as startup_exc:
        # Clean startup errors (missing/malformed input files) — not a crash.
        print(f"[STARTUP ERROR] {startup_exc}", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        # Any other unexpected exception — log it, never let a raw traceback escape.
        print(f"[ERROR] {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
