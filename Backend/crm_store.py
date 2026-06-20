"""
crm_store.py — ReactFirst AI Proactive Outbound Engine
MongoDB-backed mini-CRM lead workspace (SLED Layer 5).

Import-safe: import of this module has ZERO side effects.
All heavy work (client construction) happens lazily inside get_crm_collection()
on first call.

Unlike lead_store.py, this collection starts EMPTY and is populated by
upserts from write_qualified_leads and the agentic loop — it is a
workspace, not a contacts registry.

Policy 4 compliance: any path that reads or exposes private contact fields
MUST go through lead_store.authenticate_and_get_contact (the single
chokepoint). No corporate_access_key value ever appears in a returned
payload, log message, or error string (CRM7 / G4).
"""

import json
import os
from datetime import datetime, timezone

import db
import lead_store  # import-safe — lead_store.py has zero module-level side effects

# ---------------------------------------------------------------------------
# Module-level singleton (None until first use — CRM1)
# ---------------------------------------------------------------------------
_leads_collection = None


# ---------------------------------------------------------------------------
# Lazy singleton — mirrors lead_store.get_lead_data_collection() pattern
# ---------------------------------------------------------------------------

def get_crm_collection():
    """Return the 'leads' collection from db.get_database() (DB4 / CRM1 / ENV4).

    Built on FIRST call, not at import.
    Unlike lead_store, this collection starts EMPTY — it is a workspace
    populated by upserts rather than a pre-loaded contacts registry.
    The collection is obtained from the shared db.py client so that a real
    MongoDB is used when MONGO_URI is set and mongomock is used otherwise.

    Database:   gtm_db  (or DB_NAME env var)
    Collection: leads
    """
    global _leads_collection
    if _leads_collection is None:
        _leads_collection = db.get_database()["leads"]
        # Real-Mongo-only: create a unique index on uniq_id as a safety net.
        # Gated so that the mongomock path (MONGO_URI unset) is byte-identical
        # to the pre-D3 behaviour — no offline side effects (ENV4 / DB6).
        if db.using_real_mongo():
            try:
                _leads_collection.create_index("uniq_id", unique=True)
            except Exception:
                pass  # index creation is a real-Mongo safety net; never crash the getter
    return _leads_collection


# ---------------------------------------------------------------------------
# Internal helper — current UTC timestamp
# ---------------------------------------------------------------------------

def _utc_now_iso() -> str:
    """Return the current UTC time as an ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Internal helper — strip mongo _id from a record dict
# ---------------------------------------------------------------------------

def _strip_id(record: dict) -> dict:
    """Return a copy of record with mongo's _id field removed."""
    return {k: v for k, v in record.items() if k != "_id"}


# ---------------------------------------------------------------------------
# Internal helper — safe defaults for missing optional CRM record keys
# ---------------------------------------------------------------------------

_CRM_DEFAULTS = {
    "status": "qualified",
    "stage": "new",
    "profile": {},
    "contact_ids": [],
    "win_prob": 0.0,
    "outreach_state": {},
    "notes": "",
}


def _apply_defaults(record: dict) -> dict:
    """Return a copy of record with safe defaults filled in for missing optional keys."""
    out = dict(record)
    for key, default_value in _CRM_DEFAULTS.items():
        if key not in out:
            # Deep-copy mutable defaults to avoid aliasing
            if isinstance(default_value, dict):
                out[key] = {}
            elif isinstance(default_value, list):
                out[key] = []
            else:
                out[key] = default_value
    return out


# ---------------------------------------------------------------------------
# CRM record shape (CRM2) — keyed on brand Uniq_Id
# ---------------------------------------------------------------------------
# {
#   "uniq_id": str,            # PRIMARY KEY (== brands_catalog Uniq_Id)
#   "domain": str,
#   "status": str,             # "qualified" | "contacted" | "disqualified"
#   "stage": str,              # "new" | "researching" | "outreach" | "won"
#   "profile": dict,           # arbitrary enrichment blob
#   "contact_ids": list,       # references to lead_store contacts (emails)
#   "win_prob": float,         # 0.0..1.0 from compute_win_prob
#   "outreach_state": dict,    # reserved for L6 (default {})
#   "notes": str,
#   "updated_at": str,         # ISO 8601 UTC timestamp
# }


# ---------------------------------------------------------------------------
# upsert_lead — idempotent upsert keyed on uniq_id (CRM3)
# ---------------------------------------------------------------------------

def upsert_lead(record: dict) -> dict:
    """Idempotent upsert keyed on uniq_id.

    Same uniq_id UPDATES in place, never duplicates (CRM3).
    Sets/refreshes updated_at. Fills missing optional keys with safe defaults.
    Returns the stored record WITHOUT mongo's _id (JSON-serializable).

    Args:
        record: A dict containing at minimum "uniq_id" and "domain".

    Returns:
        The stored record dict (no _id key).

    Raises:
        ValueError: if "uniq_id" is missing or empty in record.
    """
    uniq_id = record.get("uniq_id", "")
    if not uniq_id:
        raise ValueError("upsert_lead: record must contain a non-empty 'uniq_id'")

    doc = _apply_defaults(record)
    doc["updated_at"] = _utc_now_iso()

    collection = get_crm_collection()
    collection.replace_one({"uniq_id": uniq_id}, doc, upsert=True)

    stored = collection.find_one({"uniq_id": uniq_id})
    return _strip_id(stored)


# ---------------------------------------------------------------------------
# get_lead — fetch by uniq_id (CRM3)
# ---------------------------------------------------------------------------

def get_lead(uniq_id: str) -> dict | None:
    """Fetch a CRM lead record by its uniq_id.

    Returns the record dict (no _id) on success, or None if absent.

    Args:
        uniq_id: The brand's Uniq_Id (primary key).

    Returns:
        dict or None.
    """
    collection = get_crm_collection()
    record = collection.find_one({"uniq_id": uniq_id})
    if record is None:
        return None
    return _strip_id(record)


# ---------------------------------------------------------------------------
# update_lead_stage — update stage + updated_at (CRM3)
# ---------------------------------------------------------------------------

def update_lead_stage(uniq_id: str, stage: str) -> dict:
    """Update the pipeline stage for a lead record.

    Returns the updated record on success.
    Returns {"error": "not_found"} if no lead exists with that uniq_id —
    generic error, leaks nothing about the record's content.

    Args:
        uniq_id: The brand's Uniq_Id (primary key).
        stage:   New pipeline stage string.

    Returns:
        dict — updated record, or {"error": "not_found"}.
    """
    collection = get_crm_collection()
    result = collection.update_one(
        {"uniq_id": uniq_id},
        {"$set": {"stage": stage, "updated_at": _utc_now_iso()}},
    )
    if result.matched_count == 0:
        return {"error": "not_found"}
    stored = collection.find_one({"uniq_id": uniq_id})
    return _strip_id(stored)


# ---------------------------------------------------------------------------
# attach_contact — AUTH-GATED (CRM4 / Policy 4)
# ---------------------------------------------------------------------------

def attach_contact(caller_key: str, uniq_id: str, target_email: str) -> dict:
    """Attach a contact (by email) to a CRM lead — AUTH-GATED.

    Calls lead_store.authenticate_and_get_contact(caller_key, target_email)
    as the SINGLE chokepoint for private contact data (Policy 4 / CRM4).

    On denial: returns the denial dict UNCHANGED; does NOT modify the lead;
    leaks NO field, NO key, NO existence signal.

    On success: checks opt_out_status (CRM5). If opted out, returns
    {"ok": False, "reason": "opted_out"} and does NOT attach.
    If not opted out, appends target_email to contact_ids and returns
    {"ok": True, "uniq_id": ..., "contact_ids": [...]}.

    The corporate_access_key value NEVER appears in the return payload,
    any log, or the lead record (CRM7 / G4).

    Args:
        caller_key:   Caller-supplied auth key.
        uniq_id:      The brand's Uniq_Id (the lead to update).
        target_email: Email identifying the contact in lead_store.

    Returns:
        dict — success payload, denial dict, or error dict.
    """
    # Auth gate — the single chokepoint (Policy 4 / CRM4)
    auth_result = lead_store.authenticate_and_get_contact(caller_key, target_email)

    # Generic denial propagated unchanged — no field leaked
    if "error" in auth_result:
        return auth_result

    # Check opt_out (CRM5)
    if lead_store.is_opted_out(auth_result):
        return {"ok": False, "reason": "opted_out"}

    # Ensure the lead exists
    collection = get_crm_collection()
    lead = collection.find_one({"uniq_id": uniq_id})
    if lead is None:
        return {"error": "lead_not_found"}

    # Append email to contact_ids if not already present
    existing_ids = lead.get("contact_ids", [])
    if target_email not in existing_ids:
        existing_ids = existing_ids + [target_email]
        collection.update_one(
            {"uniq_id": uniq_id},
            {"$set": {"contact_ids": existing_ids, "updated_at": _utc_now_iso()}},
        )

    updated = collection.find_one({"uniq_id": uniq_id})
    return {
        "ok": True,
        "uniq_id": uniq_id,
        "contact_ids": _strip_id(updated).get("contact_ids", []),
    }


# ---------------------------------------------------------------------------
# outbound_eligible_contacts — opt-out filtering (CRM5)
# ---------------------------------------------------------------------------

def outbound_eligible_contacts(
    caller_key: str,
    uniq_id: str,
    emails: list,
) -> list:
    """Return only auth-passing, non-opted-out contacts for a given lead.

    For each email in the list, attempts authenticate_and_get_contact.
    Only contacts that:
      (a) pass the auth gate, AND
      (b) have opt_out_status != True
    are included in the returned list.

    Opted-out contacts are silently excluded (CRM5).
    The corporate_access_key value never appears in any returned item (CRM7).

    Args:
        caller_key: Caller-supplied auth key.
        uniq_id:    The brand's Uniq_Id (for context; not used for filtering).
        emails:     List of contact emails to check.

    Returns:
        list of sanitised contact dicts that are eligible for outbound.
    """
    eligible = []
    for email in emails:
        result = lead_store.authenticate_and_get_contact(caller_key, email)
        if "error" in result:
            continue  # auth denied — skip
        if lead_store.is_opted_out(result):
            continue  # opted out — skip
        eligible.append(result)
    return eligible


# ---------------------------------------------------------------------------
# compute_win_prob — deterministic, catalog-sourced (CRM6 / Policy 1)
# ---------------------------------------------------------------------------
#
# Weights (recorded in NOTES.md — Stage 11 handback):
#
#   tier_base:
#     "Tier 1" → 0.40   ($5M+ ad spend — strongest fit signal)
#     "Tier 2" → 0.25   ($1M–$5M ad spend)
#     "Tier 3" → 0.10   (<$1M ad spend — weakest tier)
#     (anything else) → 0.10  (fallback)
#
#   icp_bonus:   +0.10 × min(icp_count, 5)
#     (caps at 0.50 contribution at icp_count=5)
#
#   incident_bonus:  +0.04 × min(incidents, 5)
#     (more PR incidents → more urgent need for brand-safety product)
#     (caps at 0.20 contribution at incidents=5)
#
#   pixel_bonus:  +0.05 × min(pixel_count, 3)
#     (pixel infrastructure → confirmed tracking maturity)
#     (caps at 0.15 contribution at pixel_count=3)
#
#   Final:  max(0.0, min(1.0, sum))   — clamped to [0.0, 1.0]
#
# Maximum theoretical:  0.40 + 0.50 + 0.20 + 0.15 = 1.25 → clamped to 1.0
# Minimum theoretical:  0.10 + 0.00 + 0.00 + 0.00 = 0.10 → floored at 0.0

_TIER_BASE = {
    "Tier 1": 0.40,
    "Tier 2": 0.25,
    "Tier 3": 0.10,
}

_ICP_WEIGHT      = 0.10
_INCIDENT_WEIGHT = 0.04
_PIXEL_WEIGHT    = 0.05

_ICP_CAP      = 5
_INCIDENT_CAP = 5
_PIXEL_CAP    = 3


def compute_win_prob(
    tier_label: str,
    incidents: int,
    icp_count: int,
    pixel_count: int,
) -> float:
    """Compute a deterministic win probability score in [0.0, 1.0].

    Inputs are ALL sourced from catalog/record signals (Policy 1 — no LLM,
    no parametric invention):
      tier_label  — from brands_catalog.csv Estimated_Ad_Spend_Tier
      incidents   — from brands_catalog.csv Historical_Social_Incidents
      icp_count   — from evaluate_icp_tags return value (count field)
      pixel_count — from analyze_company_chunk (sum of tiktok_pixel + meta_pixel + gtm)

    Weights:
      tier_base:       Tier 1 → 0.40, Tier 2 → 0.25, Tier 3 → 0.10 (default 0.10)
      icp_bonus:       +0.10 × min(icp_count, 5)
      incident_bonus:  +0.04 × min(incidents, 5)   (PR incidents → urgency)
      pixel_bonus:     +0.05 × min(pixel_count, 3)  (tracking maturity)

    Final score is clamped to [0.0, 1.0].

    Args:
        tier_label:  "Tier 1", "Tier 2", or "Tier 3".
        incidents:   Integer count of historical social incidents (≥ 0).
        icp_count:   Integer count of matched ICP tags (0..8).
        pixel_count: Integer count of detected pixels/tags (0..3).

    Returns:
        float in [0.0, 1.0].
    """
    base    = _TIER_BASE.get(tier_label, 0.10)
    icp_bonus      = _ICP_WEIGHT      * min(max(icp_count, 0), _ICP_CAP)
    incident_bonus = _INCIDENT_WEIGHT * min(max(incidents, 0), _INCIDENT_CAP)
    pixel_bonus    = _PIXEL_WEIGHT    * min(max(pixel_count, 0), _PIXEL_CAP)

    raw = base + icp_bonus + incident_bonus + pixel_bonus
    return max(0.0, min(1.0, raw))


# ---------------------------------------------------------------------------
# all_leads — list all workspace records (additive, non-graded)
# ---------------------------------------------------------------------------

def all_leads() -> list:
    """Return all lead records from the CRM workspace.

    Iterates get_crm_collection().find({}) and strips mongo _id from each.
    Returns an empty list if the workspace is empty.

    This is an additive helper used by main() to assemble the leads list
    for run_outreach_pipeline without requiring a caller_key or emails list
    upfront — the auth gate still fires inside dispatch_outreach.

    Returns:
        list of dicts (each without the mongo _id key).
    """
    collection = get_crm_collection()
    return [_strip_id(rec) for rec in collection.find({})]
