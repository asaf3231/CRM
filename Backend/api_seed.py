"""
api_seed.py — ReactFirst AI Proactive Outbound Engine
Phase 3 Integration Layer: deterministic offline seed data for the API.

Import-safety contract (INTG1 / ENV4):
    `import api_seed` has ZERO side effects.
    crm_store is imported INSIDE seed_demo() (lazy), never at module top-level.
    No file reads, no network calls, no backend work at import time.

Anti-leakage (G2):
    All brand names and domains are INVENTED — no values from brands_catalog.csv.

No secrets (G4):
    No corporate_access_key anywhere in this file.

Author: Asaf (ReactFirst AI)
"""

# ---------------------------------------------------------------------------
# SEED_ICP — the deterministic ICP document (offline, no live LLM call)
# Matches the build_icp_document output shape exactly (INTG6).
# ---------------------------------------------------------------------------

SEED_ICP: dict = {
    "vertical": "Athleisure",
    "want_signals": [
        "high ad spend",
        "active social presence",
        "DTC brand",
        "strong influencer marketing",
        "ecommerce-first",
    ],
    "avoid_signals": [
        "brick-and-mortar only",
        "B2B focus",
        "no social presence",
    ],
    "geo": "North America",
    "size_band": "Mid-Market",
    "icp_tags": [
        # Canonical _ICP_TAGS keys (== main._ICP_TAGS / the crawler's
        # operational_scale_signals) so the pipeline_runner icp_fit overlay actually
        # overlaps the live crawl signals instead of always scoring 0 (C8).
        "ecommerce_dtc",
        "paid_social_advertising",
        "ad_spend_signals",
        "pixel_tracking_present",
        "brand_marketing_team",
        "crisis_reputation_risk",
    ],
    "anchor_companies": [
        {"name": "FlowFit Apparel", "domain": "flowfitapparel.com", "why": "DTC athleisure leader with heavy TikTok spend and recent PR incident"},
        {"name": "PeakMove Co", "domain": "peakmoveco.com", "why": "Mid-market brand with aggressive Meta advertising and influencer campaigns"},
        {"name": "SwiftForm Gear", "domain": "swiftformgear.com", "why": "Fast-growing DTC brand with strong social presence and ecommerce focus"},
        {"name": "CoreLift Sports", "domain": "corelift.com", "why": "Active social accounts with brand safety exposure across multiple channels"},
        {"name": "ZenFlex Studio", "domain": "zenflexstudio.com", "why": "High-spend athleisure brand with confirmed TikTok and Meta pixel infrastructure"},
    ],
}

# ---------------------------------------------------------------------------
# SEED_STATS — LeadDiscoveryStats source numbers (self-consistent funnel)
# These are run-level funnel totals, separate from the 16 seeded pool rows.
# Internal consistency:
#   goal=60, discovered=42
#   filteredByIcp=14 → retained=28  (42-14=28)
#   belowFloor=4 → aboveFloor=24   (28-4=24)
#   newCount=20, existingCount=8    (20+8=28 = retained)
#   strong=10, review=11, weak=7   (10+11+7=28 = retained)
# ---------------------------------------------------------------------------

SEED_STATS: dict = {
    "goal": 60,
    "discovered": 42,
    "filteredByIcp": 14,
    "retained": 28,
    "belowFloor": 4,
    "aboveFloor": 24,
    "newCount": 20,
    "existingCount": 8,
    "alreadyInCrm": 5,
    "strong": 10,
    "review": 11,
    "weak": 7,
    "strictness": "Balanced strictness",
}

# ---------------------------------------------------------------------------
# _SEED_RECORDS — the 16 deterministic lead records
# Each carries the base CRM keys + the catalog-derived fields the adapter needs.
# spread across GovBand / FitGrade / LeadKind buckets for variety.
#
# GovBand buckets (historical_social_incidents):
#   Heavy Gov (>=3):  records 1,2,4,7,10,13
#   Light Gov (1-2):  records 3,5,8,11,14
#   No Gov (0):       records 6,9,12,15,16
#
# FitGrade buckets (icp_count):
#   Strong (>=4):  records 1,3,5,7,9,13
#   Medium (2-3):  records 2,4,6,8,10,14
#   Weak (<=1):    records 11,12,15,16
#
# LeadKind (current_status):
#   Existing (Active_Client): records 1,3,7,9,13
#   New (others):             records 2,4,5,6,8,10,11,12,14,15,16
# ---------------------------------------------------------------------------

_SEED_RECORDS: list = [
    # --- Record 1: Heavy Gov, Strong, Existing ---
    {
        "uniq_id": "seed-lead-001",
        "domain": "apexwear.com",
        "company": "Apex Wear",
        "status": "qualified",
        "stage": "in_crm",
        "win_prob": 0.82,
        "profile": {"icp_tags": ["high_ad_spend", "social_presence", "dtc_brand", "influencer_marketing", "brand_safety_risk"]},
        "icp_count": 5,
        "historical_social_incidents": 4,
        "current_status": "Active_Client",
        "contact_ids": ["exec@apexwear.com"],
    },
    # --- Record 2: Heavy Gov, Medium, New ---
    {
        "uniq_id": "seed-lead-002",
        "domain": "boldstride.com",
        "company": "Bold Stride",
        "status": "qualified",
        "stage": "enrolled",
        "win_prob": 0.54,
        "profile": {"icp_tags": ["social_presence", "dtc_brand", "brand_safety_risk"]},
        "icp_count": 3,
        "historical_social_incidents": 5,
        "current_status": "Open_Opportunity",
        "contact_ids": [],
    },
    # --- Record 3: Light Gov, Strong, Existing ---
    {
        "uniq_id": "seed-lead-003",
        "domain": "coreflex.com",
        "company": "CoreFlex",
        "status": "qualified",
        "stage": "outreach",
        "win_prob": 0.78,
        "profile": {"icp_tags": ["high_ad_spend", "social_presence", "dtc_brand", "ecommerce", "influencer_marketing"]},
        "icp_count": 5,
        "historical_social_incidents": 2,
        "current_status": "Active_Client",
        "contact_ids": ["vp@coreflex.com", "sales@coreflex.com"],
    },
    # --- Record 4: Heavy Gov, Medium, New ---
    {
        "uniq_id": "seed-lead-004",
        "domain": "dynamo-sport.com",
        "company": "Dynamo Sport",
        "status": "qualified",
        "stage": "qualified",
        "win_prob": 0.49,
        "profile": {"icp_tags": ["high_ad_spend", "brand_safety_risk", "ecommerce"]},
        "icp_count": 3,
        "historical_social_incidents": 6,
        "current_status": "Unreached_Prospect",
        "contact_ids": [],
    },
    # --- Record 5: Light Gov, Strong, New ---
    {
        "uniq_id": "seed-lead-005",
        "domain": "eliteform.com",
        "company": "Elite Form",
        "status": "qualified",
        "stage": "in_crm",
        "win_prob": 0.70,
        "profile": {"icp_tags": ["high_ad_spend", "social_presence", "dtc_brand", "ecommerce"]},
        "icp_count": 4,
        "historical_social_incidents": 1,
        "current_status": "Open_Opportunity",
        "contact_ids": [],
    },
    # --- Record 6: No Gov, Medium, New ---
    {
        "uniq_id": "seed-lead-006",
        "domain": "freshpace.com",
        "company": "Fresh Pace",
        "status": "qualified",
        "stage": "enriched",
        "win_prob": 0.41,
        "profile": {"icp_tags": ["dtc_brand", "ecommerce", "influencer_marketing"]},
        "icp_count": 3,
        "historical_social_incidents": 0,
        "current_status": "Open_Opportunity",
        "contact_ids": [],
    },
    # --- Record 7: Heavy Gov, Strong, Existing ---
    {
        "uniq_id": "seed-lead-007",
        "domain": "gripzone.com",
        "company": "GripZone",
        "status": "qualified",
        "stage": "replied",
        "win_prob": 0.91,
        "profile": {"icp_tags": ["high_ad_spend", "social_presence", "dtc_brand", "influencer_marketing", "brand_safety_risk", "ecommerce"]},
        "icp_count": 6,
        "historical_social_incidents": 3,
        "current_status": "Active_Client",
        "contact_ids": ["cmo@gripzone.com"],
    },
    # --- Record 8: Light Gov, Medium, New ---
    {
        "uniq_id": "seed-lead-008",
        "domain": "highstep.com",
        "company": "High Step",
        "status": "qualified",
        "stage": "qualified",
        "win_prob": 0.45,
        "profile": {"icp_tags": ["social_presence", "brand_safety_risk"]},
        "icp_count": 2,
        "historical_social_incidents": 2,
        "current_status": "Unreached_Prospect",
        "contact_ids": [],
    },
    # --- Record 9: No Gov, Strong, Existing ---
    {
        "uniq_id": "seed-lead-009",
        "domain": "infinitestride.com",
        "company": "Infinite Stride",
        "status": "qualified",
        "stage": "in_crm",
        "win_prob": 0.66,
        "profile": {"icp_tags": ["high_ad_spend", "dtc_brand", "ecommerce", "influencer_marketing"]},
        "icp_count": 4,
        "historical_social_incidents": 0,
        "current_status": "Active_Client",
        "contact_ids": [],
    },
    # --- Record 10: Heavy Gov, Medium, New ---
    {
        "uniq_id": "seed-lead-010",
        "domain": "kineticwear.com",
        "company": "Kinetic Wear",
        "status": "qualified",
        "stage": "enrolled",
        "win_prob": 0.58,
        "profile": {"icp_tags": ["social_presence", "dtc_brand", "brand_safety_risk"]},
        "icp_count": 3,
        "historical_social_incidents": 4,
        "current_status": "Open_Opportunity",
        "contact_ids": [],
    },
    # --- Record 11: Light Gov, Weak, New ---
    {
        "uniq_id": "seed-lead-011",
        "domain": "livefit.com",
        "company": "LiveFit",
        "status": "qualified",
        "stage": "discovered",
        "win_prob": 0.22,
        "profile": {"icp_tags": ["dtc_brand"]},
        "icp_count": 1,
        "historical_social_incidents": 1,
        "current_status": "Unreached_Prospect",
        "contact_ids": [],
    },
    # --- Record 12: No Gov, Weak, New ---
    {
        "uniq_id": "seed-lead-012",
        "domain": "momentumgear.com",
        "company": "Momentum Gear",
        "status": "qualified",
        "stage": "discovered",
        "win_prob": 0.15,
        "profile": {"icp_tags": ["ecommerce"]},
        "icp_count": 1,
        "historical_social_incidents": 0,
        "current_status": "Unreached_Prospect",
        "contact_ids": [],
    },
    # --- Record 13: Heavy Gov, Strong, Existing ---
    {
        "uniq_id": "seed-lead-013",
        "domain": "nextstep-sport.com",
        "company": "NextStep Sport",
        "status": "qualified",
        "stage": "in_crm",
        "win_prob": 0.85,
        "profile": {"icp_tags": ["high_ad_spend", "social_presence", "dtc_brand", "brand_safety_risk", "ecommerce"]},
        "icp_count": 5,
        "historical_social_incidents": 7,
        "current_status": "Active_Client",
        "contact_ids": ["legal@nextstep-sport.com"],
    },
    # --- Record 14: Light Gov, Medium, New ---
    {
        "uniq_id": "seed-lead-014",
        "domain": "openrun.com",
        "company": "OpenRun",
        "status": "qualified",
        "stage": "qualified",
        "win_prob": 0.38,
        "profile": {"icp_tags": ["social_presence", "dtc_brand", "influencer_marketing"]},
        "icp_count": 3,
        "historical_social_incidents": 2,
        "current_status": "Open_Opportunity",
        "contact_ids": [],
    },
    # --- Record 15: No Gov, Weak, New ---
    {
        "uniq_id": "seed-lead-015",
        "domain": "prestige-active.com",
        "company": "Prestige Active",
        "status": "qualified",
        "stage": "discovered",
        "win_prob": 0.18,
        "profile": {"icp_tags": ["ecommerce"]},
        "icp_count": 1,
        "historical_social_incidents": 0,
        "current_status": "Unreached_Prospect",
        "contact_ids": [],
    },
    # --- Record 16: No Gov, Weak, New ---
    {
        "uniq_id": "seed-lead-016",
        "domain": "quickform.com",
        "company": "QuickForm",
        "status": "qualified",
        "stage": "discovered",
        "win_prob": 0.12,
        "profile": {"icp_tags": []},
        "icp_count": 0,
        "historical_social_incidents": 0,
        "current_status": "Unreached_Prospect",
        "contact_ids": [],
    },
]


# ---------------------------------------------------------------------------
# seed_demo() — upsert all 16 records into crm_store (idempotent)
# crm_store is imported LAZILY inside this function (import-safety / INTG1).
# Calling seed_demo() twice yields the same 16 records, never 32 (upsert).
# ---------------------------------------------------------------------------

def seed_demo() -> None:
    """Seed the 16 deterministic lead records into crm_store — seed-if-empty only.

    Called ONLY from the ASGI lifespan in api_server.py (never at import time).
    crm_store is imported lazily here so `import api_seed` stays side-effect-free.

    Seeding logic (CONN0 / CONN1):
      1. If the env var SEED_DEMO is set to one of {"0", "false", "no", "off"}
         (case-insensitive), return immediately — operator opt-out.
      2. If the leads workspace is non-empty (count_documents({}) > 0), return
         immediately — seed-if-empty guard; never clobber persisted data.
      3. Only when the workspace is empty (and not opted out) are the 16
         _SEED_RECORDS upserted.  On a fresh offline mongomock workspace
         (always empty at boot) the FE dev data is seeded as before (CONN1).

    No corporate_access_key is set or referenced anywhere here (G4).
    """
    import os

    seed_flag = os.environ.get("SEED_DEMO", "1").strip().lower()
    if seed_flag in {"0", "false", "no", "off"}:
        return  # operator opted out

    import crm_store  # lazy — never at module top-level

    collection = crm_store.get_crm_collection()
    if collection.count_documents({}) > 0:
        return  # workspace already has data — never overwrite

    for record in _SEED_RECORDS:
        crm_store.upsert_lead(record)


# ---------------------------------------------------------------------------
# ICP durable substrate (connection-plan C6 / CONN9–CONN10)
# Persist the ICP document in an `icp_documents` collection so /api/icp serves
# the durable workspace instead of the in-memory SEED_ICP constant — making the
# ICP the third DB-backed read endpoint (after leads + computed stats).
#
# Governance: the ICP doc has NO private contact fields, so no Policy-4 auth
# gate is involved, and no corporate_access_key is ever written or read here.
#
# Seed-if-empty is INTENTIONALLY INDEPENDENT of SEED_DEMO. The ICP doc is
# baseline configuration, not disposable demo data — Railway sets SEED_DEMO=0 to
# retire the demo leads, but the ICP must still seed there or /api/icp would
# return empty. It seeds only when the collection is empty and never clobbers an
# existing (possibly edited) doc.
#
# Import-safety (ENV4): the collection is obtained lazily inside each function
# via db.get_database(); nothing connects at import time. `_icp_collection` is
# the lazy singleton (reset in tests/conftest.py).
# ---------------------------------------------------------------------------

_ICP_DOC_ID = "active"   # stable key for the single active ICP doc
_icp_collection = None   # lazy singleton — built on first use, not at import


def get_icp_collection():
    """Return the `icp_documents` collection from db.get_database().

    Lazy singleton mirroring crm_store.get_crm_collection(): built on first
    call, never at import. A real-Mongo-only unique index on `icp_id` keeps the
    seed idempotent; create_index is guarded so the mongomock path stays
    side-effect-identical to having no index (ENV4 / DB6 pattern).
    """
    global _icp_collection
    if _icp_collection is None:
        import db  # lazy — preserves import-safety (ENV4)

        _icp_collection = db.get_database()["icp_documents"]
        if db.using_real_mongo():
            try:
                _icp_collection.create_index("icp_id", unique=True)
            except Exception:
                pass  # index is a real-Mongo safety net; never crash the getter
    return _icp_collection


def seed_icp_if_empty() -> None:
    """Seed SEED_ICP into `icp_documents` when the collection is empty.

    Called from the ASGI lifespan (never at import). Seed-if-empty and
    idempotent: if a doc already exists it is left untouched (never clobbered).
    Deliberately NOT gated on SEED_DEMO — see the section header.
    """
    collection = get_icp_collection()
    if collection.count_documents({}) > 0:
        return  # already seeded — never overwrite an edited ICP
    doc = dict(SEED_ICP)          # shallow copy so the module constant is untouched
    doc["icp_id"] = _ICP_DOC_ID
    collection.insert_one(doc)


def get_icp_document() -> dict:
    """Return the persisted ICP document (SEED_ICP-shaped), or SEED_ICP as fallback.

    Reads the single active doc from `icp_documents`, strips Mongo's `_id` and the
    internal `icp_id`, and returns the SEED_ICP-shaped dict that icp_doc_to_ui
    expects. If the collection is empty (e.g. a request before lifespan seeding),
    falls back to a copy of the in-memory SEED_ICP so /api/icp never 500s or
    returns empty.
    """
    try:
        doc = get_icp_collection().find_one({})
    except Exception:
        doc = None
    if not doc:
        return dict(SEED_ICP)  # resilient fallback — never empty/500
    return {k: v for k, v in doc.items() if k not in ("_id", "icp_id")}


def upsert_icp_document(fields: dict) -> dict:
    """Merge storage-shaped `fields` onto the active ICP doc and persist (CONN13).

    Merge-preserve: any storage field NOT present in `fields` keeps its existing stored
    value, so a partial edit from the UI never drops anchors/tags it didn't send. Stamps
    the stable `icp_id` and upserts the single active doc. The ICP has NO private contact
    fields, so no Policy-4 gate is involved and no corporate_access_key is ever written.

    Args:
        fields: storage-shaped ICP fields to merge (a subset of the SEED_ICP keys).

    Returns:
        The saved ICP doc (SEED_ICP-shaped, without `_id`/`icp_id`).
    """
    current = get_icp_document()              # existing active doc, or SEED_ICP fallback
    merged = {**current, **(fields or {})}
    doc = dict(merged)
    doc["icp_id"] = _ICP_DOC_ID
    get_icp_collection().replace_one({"icp_id": _ICP_DOC_ID}, doc, upsert=True)
    return {k: v for k, v in doc.items() if k not in ("_id", "icp_id")}


# Deterministic ICP suggestion pool (C9 / CONN18) — domain-relevant want-signal phrases an
# operator might add to sharpen the ICP. KEY-FREE (no LLM): the endpoint returns the pool
# entries NOT already present in the active ICP. Order is stable (pool order).
_ICP_SUGGESTION_POOL = [
    "high ad spend",
    "active social presence",
    "DTC brand",
    "strong influencer marketing",
    "ecommerce-first",
    "TikTok pixel installed",
    "Meta pixel installed",
    "Google Tag Manager",
    "performance marketing team",
    "venture-backed growth stage",
    "deep product catalog",
    "recent PR or brand-safety incident",
    "Shopify storefront",
    "retargeting campaigns",
    "rapid revenue growth",
]


def icp_suggestions(limit: int = 8) -> list:
    """Deterministic ICP keyword suggestions (C9 / CONN18) — ADDITIVE want-signal phrases that
    are NOT already in the active ICP (replaces the old behaviour that just echoed want_signals).

    No LLM / no keys: drawn from the curated `_ICP_SUGGESTION_POOL` and de-duped (case-insensitive)
    against the active ICP's `want_signals` + humanized `icp_tags`. Reads the persisted doc via
    get_icp_document(), so it reflects edits. Stable order, capped at `limit`.

    Returns:
        list[str] — up to `limit` suggested additions not yet in the ICP.
    """
    icp = get_icp_document()
    present = {str(v).strip().lower() for v in (icp.get("want_signals") or [])}
    present |= {str(v).replace("_", " ").strip().lower() for v in (icp.get("icp_tags") or [])}

    out = []
    for phrase in _ICP_SUGGESTION_POOL:
        if phrase.strip().lower() not in present:
            out.append(phrase)
        if len(out) >= limit:
            break
    return out
