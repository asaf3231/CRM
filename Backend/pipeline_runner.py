"""
pipeline_runner.py — deterministic, ICP-driven live discovery (connection-plan C4 / deferred I5).

Chains the REAL graded tools into one reproducible discovery run, driven by the persisted ICP
(`api_seed.get_icp_document`).  It deliberately does NOT use the 15-call LLM loop (`answer_question`) —
that qualifies inconsistently (it feeds the ICP check thin strings; see NOTES 2026-06-20).  This runner
calls the same tools directly, so it's reliable and instrumentable:

    get_icp_document → generate_search_queries → execute_3way_fanout → extract_and_score_pool
                     → analyze_company_chunk → (ICP gate) → ICP overlay → crm_store.upsert_lead

Governance:
  - Qualification mirrors the graded gate: a brand qualifies iff its live crawl surfaces
    >= main.ICP_TAG_THRESHOLD ICP signals (the crawler's operational_scale_signals are matched with the
    SAME `_ICP_TAGS` vocabulary `evaluate_icp_tags` uses).  `evaluate_icp_tags`/`_ICP_TAGS`/the threshold
    are UNTOUCHED (ICPB5).
  - Only catalog matches persist (Policy 1); net-new brands are returned but NOT saved.
  - No corporate_access_key is ever read or written here (no Policy-4 contact access).

Progress is written to a `pipeline_jobs` Mongo doc so an async HTTP endpoint can poll it.

Import-safety (ENV4): main / crm_store / api_seed / db are imported LAZILY inside functions; no client or
collection is built at module import.
"""

import datetime
import os
import uuid

# Ordered stages — the FE swarm screen maps `stage` to an animation step.
STAGES = ["queued", "icp", "queries", "fanout", "score", "analyze", "qualify", "persist", "done"]

# Lazy singleton for the pipeline_jobs collection (mirrors crm_store.get_crm_collection()).
_jobs_collection = None


def get_jobs_collection():
    """Return the `pipeline_jobs` collection from db.get_database() (lazy; mongomock offline)."""
    global _jobs_collection
    if _jobs_collection is None:
        import db  # lazy — no client at import (ENV4)
        _jobs_collection = db.get_database()["pipeline_jobs"]
    return _jobs_collection


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _update_job(job_id: str, **fields) -> None:
    fields["updated_at"] = _now_iso()
    get_jobs_collection().update_one({"job_id": job_id}, {"$set": fields}, upsert=True)


def create_job(seed_override: str | None = None) -> str:
    """Create a fresh pipeline_jobs doc in the 'running' state; return its job_id."""
    job_id = uuid.uuid4().hex
    get_jobs_collection().replace_one(
        {"job_id": job_id},
        {
            "job_id": job_id,
            "status": "running",
            "stage": "queued",
            "seed": (seed_override or "").strip(),
            "discovered": [],
            "qualified": [],
            "saved": [],
            "error": None,
            "created_at": _now_iso(),
            "updated_at": _now_iso(),
        },
        upsert=True,
    )
    return job_id


def get_job(job_id: str) -> dict | None:
    """Return the job doc (without Mongo _id), or None if absent."""
    doc = get_jobs_collection().find_one({"job_id": job_id})
    if doc is None:
        return None
    doc.pop("_id", None)
    return doc


def _compose_seed(icp: dict) -> str:
    """Compose a discovery seed from the ICP's vertical + want_signals."""
    vertical = str(icp.get("vertical", "") or "").strip()
    wants = [str(w).strip() for w in (icp.get("want_signals") or []) if isinstance(w, str) and w.strip()]
    parts = [p for p in [vertical, ", ".join(wants)] if p]
    return " — ".join(parts) if parts else "ecommerce DTC brands"


def _matches_avoid(text: str, avoid_signals: list) -> bool:
    """Conservative avoid-signal match: the full phrase as a substring, or >=2 salient words present.

    Kept conservative on purpose — an over-eager avoid filter would wrongly drop qualified leads, and
    Firecrawl title/description text is often thin.
    """
    t = (text or "").lower()
    for a in avoid_signals or []:
        phrase = str(a).lower().strip()
        if not phrase:
            continue
        if phrase in t:
            return True
        words = [w for w in phrase.replace("-", " ").split() if len(w) >= 4]
        if len(words) >= 2 and all(w in t for w in words):
            return True
    return False


def _resolve_catalog_path() -> str:
    cwd_path = os.path.join(os.getcwd(), "brands_catalog.csv")
    if os.path.exists(cwd_path):
        return cwd_path
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "brands_catalog.csv")


def run_discovery(job_id: str, seed_override: str | None = None, max_domains: int = 25) -> dict:
    """Run the deterministic discovery chain, updating the pipeline_jobs doc at each stage.

    Never raises — any failure is recorded on the job (status='error').  Returns the final job dict.
    Catalog matches that clear the ICP gate are upserted to crm_store; net-new brands are reported only.
    """
    import main         # lazy
    import crm_store    # lazy
    import api_seed     # lazy

    try:
        # 1) ICP — persisted doc (SEED_ICP fallback so this lane is never blocked).
        _update_job(job_id, stage="icp")
        try:
            icp = api_seed.get_icp_document() or {}
        except Exception:  # noqa: BLE001
            icp = {}
        if not icp:
            icp = getattr(api_seed, "SEED_ICP", {}) or {}
        avoid_signals = icp.get("avoid_signals", []) or []
        icp_tags = {str(t) for t in (icp.get("icp_tags") or [])}
        seed = (seed_override or "").strip() or _compose_seed(icp)

        # 2) Search queries from the ICP-derived seed.
        _update_job(job_id, stage="queries", seed=seed)
        queries = main.generate_search_queries(seed)

        # 3) 3-way fan-out (web search).
        _update_job(job_id, stage="fanout")
        fanout = main.execute_3way_fanout(queries)
        domains_map = fanout.get("domains", {}) if isinstance(fanout, dict) else {}
        raw_pool = [
            {"domain": d, "provenance": (m or {}).get("provenance", [])}
            for d, m in domains_map.items()
        ]

        # 4) De-dup + catalog map.
        _update_job(job_id, stage="score")
        catalog_df = main.load_catalog(_resolve_catalog_path())
        scored = main.extract_and_score_pool(raw_pool, catalog_df)
        scored = [s for s in scored if not s.get("blacklisted")]  # Blacklisted excluded from outreach
        discovered = [{"domain": s["domain"], "in_catalog": bool(s.get("in_catalog"))} for s in scored]
        _update_job(job_id, discovered=discovered)

        # 5) Deep crawl (Firecrawl) — capped.
        _update_job(job_id, stage="analyze")
        domains = [s["domain"] for s in scored][:max_domains]
        profiles = {p.get("domain"): p for p in main.analyze_company_chunk(domains)}
        by_domain = {s["domain"]: s for s in scored}

        # 6) ICP gate + overlay + persist.
        _update_job(job_id, stage="qualify")
        threshold = main.ICP_TAG_THRESHOLD
        qualified, saved = [], []
        for domain in domains:
            prof = profiles.get(domain, {}) or {}
            signals = prof.get("operational_scale_signals", []) or []
            icp_count = len(signals)
            text = f"{prof.get('title', '')} {prof.get('description', '')}"
            if _matches_avoid(text, avoid_signals):
                continue
            if icp_count < threshold:  # graded gate, mirrored on the live crawl signals
                continue
            pixel_count = sum(1 for k in ("tiktok_pixel", "meta_pixel", "gtm") if prof.get(k))
            icp_fit = len(set(signals) & icp_tags)  # ICP overlay (ranking signal, not a pass/fail)
            ctx = by_domain.get(domain, {}).get("catalog_context")

            qualified.append({
                "domain": domain,
                "company": (ctx or {}).get("Brand_Name", domain),
                "icpCount": icp_count,
                "icpFit": icp_fit,
                "inCatalog": bool(ctx),
                "tags": signals,
            })

            if ctx:  # catalog match → persist (Policy 1)
                tier = str(ctx["Estimated_Ad_Spend_Tier"]).strip()
                incidents = int(ctx["Historical_Social_Incidents"])
                win_prob = crm_store.compute_win_prob(tier, incidents, icp_count, pixel_count)
                record = {
                    "uniq_id": str(ctx["Uniq_Id"]).strip(),
                    "domain": domain,
                    "company": str(ctx["Brand_Name"]).strip(),
                    "status": "qualified",
                    "stage": "in_crm",
                    "win_prob": win_prob,
                    "profile": {
                        "icp_tags": signals,
                        "title": prof.get("title", ""),
                        "icp_fit": icp_fit,
                        "pixels": {k: bool(prof.get(k)) for k in ("tiktok_pixel", "meta_pixel", "gtm")},
                        "category_path": str(ctx["Core_Category"]).strip(),
                    },
                    "icp_count": icp_count,
                    "historical_social_incidents": incidents,
                    "current_status": str(ctx["Current_Status"]).strip(),
                    "contact_ids": [],
                }
                crm_store.upsert_lead(record)
                saved.append({
                    "uniqId": record["uniq_id"],
                    "company": record["company"],
                    "domain": domain,
                    "score": round(win_prob * 100),
                    "icpFit": icp_fit,
                })

        _update_job(job_id, stage="persist", qualified=qualified, saved=saved)
        _update_job(job_id, status="done", stage="done")
    except Exception as exc:  # noqa: BLE001 — failures are data, never crash the worker
        _update_job(job_id, status="error", error=str(exc))

    return get_job(job_id)
