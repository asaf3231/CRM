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
        "high_ad_spend",
        "social_presence",
        "dtc_brand",
        "influencer_marketing",
        "ecommerce",
        "brand_safety_risk",
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
