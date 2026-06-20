"""
api_adapters.py — ReactFirst AI Proactive Outbound Engine
Phase 3 Integration Layer: pure snake_case→camelCase adapters.

Import-safety contract (INTG1 / ENV4):
    `import api_adapters` has ZERO side effects.
    No backend imports at module top-level (no crm_store, lead_store, main).
    No I/O, no network, no file reads.

These are PURE functions — fully unit-testable with no infrastructure.

Thresholds (LOCKED — do NOT change without PM approval):
    GovBand  from historical_social_incidents: >=3 → "Heavy Gov", 1|2 → "Light Gov", 0 → "No Gov"
    FitGrade from icp_count:                   >=4 → "Strong",    2|3  → "Medium",    <=1 → "Weak"
    LeadKind from current_status:              "Active_Client" → "Existing", else → "New"

Anti-leakage (G2, G4):
    No catalog literals hardcoded. No corporate_access_key anywhere.
    contact_ids is STRIPPED from every crm_lead_to_ui output (INTG5).

Author: Asaf (ReactFirst AI)
"""

from datetime import datetime, timedelta, timezone

# ---------------------------------------------------------------------------
# Threshold constants (LOCKED — named, not magic inline)
# ---------------------------------------------------------------------------

_GOVBAND_HEAVY_THRESHOLD = 3   # historical_social_incidents >= 3 → "Heavy Gov"
_FITGRADE_STRONG_THRESHOLD = 4  # icp_count >= 4 → "Strong"
_FITGRADE_MEDIUM_MIN = 2        # icp_count 2 or 3 → "Medium"

# LeadKind: "Active_Client" → "Existing", all others → "New"
_EXISTING_STATUS = "Active_Client"


# ---------------------------------------------------------------------------
# gov_band — GovBand classifier (INTG5)
# ---------------------------------------------------------------------------

def gov_band(incidents: int) -> str:
    """Classify historical_social_incidents into a GovBand label.

    Thresholds (LOCKED):
        >= 3 → "Heavy Gov"
        1 or 2 → "Light Gov"
        0 → "No Gov"

    Args:
        incidents: Non-negative integer count of historical social incidents.

    Returns:
        One of "Heavy Gov", "Light Gov", "No Gov".
    """
    if incidents >= _GOVBAND_HEAVY_THRESHOLD:
        return "Heavy Gov"
    if incidents >= 1:
        return "Light Gov"
    return "No Gov"


# ---------------------------------------------------------------------------
# fit_grade — FitGrade classifier (INTG5)
# ---------------------------------------------------------------------------

def fit_grade(icp_count: int) -> str:
    """Classify icp_count into a FitGrade label.

    Thresholds (LOCKED):
        >= 4 → "Strong"
        2 or 3 → "Medium"
        <= 1 → "Weak"

    Args:
        icp_count: Non-negative integer count of matched ICP tags.

    Returns:
        One of "Strong", "Medium", "Weak".
    """
    if icp_count >= _FITGRADE_STRONG_THRESHOLD:
        return "Strong"
    if icp_count >= _FITGRADE_MEDIUM_MIN:
        return "Medium"
    return "Weak"


# ---------------------------------------------------------------------------
# lead_kind — LeadKind classifier (INTG5)
# ---------------------------------------------------------------------------

def lead_kind(current_status: str) -> str:
    """Classify current_status into a LeadKind label.

    Rule (LOCKED):
        "Active_Client" → "Existing"
        anything else   → "New"

    Args:
        current_status: The current_status string from the CRM record.

    Returns:
        "Existing" or "New".
    """
    if current_status == _EXISTING_STATUS:
        return "Existing"
    return "New"


# ---------------------------------------------------------------------------
# crm_lead_to_ui — CRM record → Lead (camelCase) (INTG5)
# ---------------------------------------------------------------------------

def crm_lead_to_ui(record: dict) -> dict:
    """Convert a CRM lead record to the UI Lead shape (camelCase).

    Output keys (EXACT — must match frontend types/index.ts Lead interface):
        id, company, domain, score, fit, gov, kind, stage, tags, winProb

    STRIPS:
        - contact_ids (must NOT appear in output — INTG5)
        - corporate_access_key (must NEVER appear at any depth — INTG5 / G4)
        - updated_at and any other internal CRM fields

    Uses safe .get() with sensible defaults for optional fields so a record
    missing an optional key does not crash.

    Args:
        record: A CRM lead record dict (from crm_store.all_leads() or upsert_lead()).

    Returns:
        dict with exactly the Lead camelCase keys.
    """
    win_prob = record.get("win_prob", 0.0)
    icp_count = record.get("icp_count", 0)
    incidents = record.get("historical_social_incidents", 0)
    current_status = record.get("current_status", "")
    profile = record.get("profile", {})
    tags = profile.get("icp_tags", []) if isinstance(profile, dict) else []

    return {
        "id": record.get("uniq_id", ""),
        "company": record.get("company", ""),
        "domain": record.get("domain", ""),
        "score": round(win_prob * 100),
        "fit": fit_grade(icp_count),
        "gov": gov_band(incidents),
        "kind": lead_kind(current_status),
        "stage": record.get("stage", "discovered"),
        "tags": tags,
        "winProb": win_prob,
        # contact_ids intentionally OMITTED (INTG5)
        # corporate_access_key intentionally OMITTED (INTG5 / G4)
        # updated_at intentionally OMITTED
    }


# ---------------------------------------------------------------------------
# crm_lead_to_detail — CRM record → LeadDetail (camelCase) (lead-detail drawer)
# ---------------------------------------------------------------------------

# win_prob → angle Tier bands (deterministic; mirrors the 1..4 scale the FE
# TierBadge renders). This is a DERIVED view of the record's own win_prob, NOT a
# live match_solicitation_angle RAG result (which needs a crawl). Highest band wins.
_ANGLE_TIER_BANDS = ((0.75, 1), (0.50, 2), (0.25, 3))


def _derive_angle(win_prob: float, gov: str, tags: list, incidents: int, icp_count: int) -> dict:
    """Derive a deterministic LeadAngle from the record's REAL signals.

    Honest derivation — no invented external facts:
      - tier is banded from the record's own win_prob,
      - title is categorised from its GovBand (same spirit as gov_band/fit_grade),
      - rationale quotes the actual ICP-tag / incident / win-prob numbers.
    The true RAG-matched angle requires a live crawl + match_solicitation_angle run.

    Returns a LeadAngle dict: {title, tier (1..4), rationale}.
    """
    tier = 4
    for floor, t in _ANGLE_TIER_BANDS:
        if win_prob >= floor:
            tier = t
            break

    if gov == "Heavy Gov":
        title = "Crisis-narrative brand-safety angle"
    elif gov == "Light Gov":
        title = "Reputation-watch angle"
    else:
        title = "Growth-performance angle"

    tag_str = ", ".join(tags) if tags else "no ICP tags"
    rationale = (
        f"Derived from CRM signals — {icp_count} ICP tag(s) matched ({tag_str}); "
        f"{incidents} historical social incident(s) ({gov}); "
        f"win probability {round(win_prob * 100)}%. "
        f"The RAG-matched angle is computed on a live crawl (match_solicitation_angle)."
    )
    return {"title": title, "tier": tier, "rationale": rationale}


def crm_lead_to_detail(record: dict) -> dict:
    """Convert a CRM lead record to the UI LeadDetail shape (camelCase).

    LeadDetail extends Lead (see crm_lead_to_ui) with three more keys:
        contacts, angle, brief

    Contacts (Policy-4): private contact fields are reachable ONLY through the
    lead_store auth gate with a valid corporate_access_key.  The API holds no
    key, so `contacts` is returned EMPTY here — honest, and the Policy-4
    chokepoint stays un-bypassed (contact_ids are never exposed either, since
    this builds on crm_lead_to_ui which strips them).

    angle / brief are deterministically derived from the record's own fields
    (see _derive_angle) — no fabricated external facts.

    Returns:
        dict with the Lead keys + {contacts, angle, brief}.
    """
    base = crm_lead_to_ui(record)

    win_prob = record.get("win_prob", 0.0)
    icp_count = record.get("icp_count", 0)
    incidents = record.get("historical_social_incidents", 0)

    base["contacts"] = []  # Policy-4 gate not satisfied by the API → no private contacts revealed
    base["angle"] = _derive_angle(win_prob, base["gov"], base["tags"], incidents, icp_count)
    base["brief"] = (
        f"{base['company']} ({base['domain']}) is a {base['kind']} lead at the "
        f"'{base['stage']}' stage. {base['fit']} ICP fit "
        f"({icp_count} tag(s): {', '.join(base['tags']) if base['tags'] else 'none'}). "
        f"{base['gov']} — {incidents} historical social incident(s). "
        f"Win probability {round(win_prob * 100)}%."
    )
    return base


# ---------------------------------------------------------------------------
# icp_doc_to_ui — SEED_ICP dict → IcpDocument (camelCase) (INTG6)
# ---------------------------------------------------------------------------

def icp_doc_to_ui(seed: dict) -> dict:
    """Convert a SEED_ICP dict to the UI IcpDocument shape (camelCase).

    Output keys (EXACT — must match frontend types/index.ts IcpDocument interface):
        id, title, description, source, keywords, industryVerticals,
        geographicFocus, qualificationCriteria, anchorCompanies

    qualificationCriteria:
        each want_signal → {"criterion": s, "importance": "High"}
        each avoid_signal → {"criterion": "Avoid: "+s, "importance": "Low"}

    anchorCompanies: pass-through list of {name, domain, why}.

    Args:
        seed: The SEED_ICP dict (from api_seed.SEED_ICP).

    Returns:
        dict with exactly the IcpDocument camelCase keys.
    """
    vertical = seed.get("vertical", "")
    geo = seed.get("geo", "")
    size_band = seed.get("size_band", "")
    want_signals = seed.get("want_signals", [])
    avoid_signals = seed.get("avoid_signals", [])
    anchor_companies = seed.get("anchor_companies", [])

    qualification_criteria = (
        [{"criterion": s, "importance": "High"} for s in want_signals]
        + [{"criterion": "Avoid: " + s, "importance": "Low"} for s in avoid_signals]
    )

    return {
        "id": "icp-v1",
        "title": vertical,
        "description": f"DTC brands in the {vertical} space, {geo}, {size_band} segment",
        "source": "Companies",
        "keywords": want_signals,
        "industryVerticals": [vertical],
        "geographicFocus": [geo],
        "sizeBand": size_band,
        "icpTags": seed.get("icp_tags", []),
        "qualificationCriteria": qualification_criteria,
        "anchorCompanies": anchor_companies,
    }


# ---------------------------------------------------------------------------
# ui_to_icp_doc — reverse of icp_doc_to_ui: UI IcpDocument → storage ICP fields
# (CONN13 — ICP authoring write path)
# ---------------------------------------------------------------------------

def ui_to_icp_doc(ui: dict) -> dict:
    """Map a (possibly partial) UI IcpDocument (camelCase) → storage-shaped ICP fields.

    The inverse of icp_doc_to_ui. **Partial-safe:** emits a storage key ONLY for a UI key
    that is present, so a partial edit merges cleanly via api_seed.upsert_icp_document.

        title              → vertical
        keywords           → want_signals
        geographicFocus[0] → geo
        sizeBand           → size_band
        icpTags            → icp_tags
        anchorCompanies    → anchor_companies
        qualificationCriteria "Avoid: X" items → avoid_signals (prefix stripped)

    The non-"Avoid:" qualificationCriteria items are a forward-only display echo of
    want_signals (which round-trips via `keywords`), so they are ignored on the reverse.
    `description`/`industryVerticals`/`source`/`id` are forward-derived and ignored here.

    Args:
        ui: a UI IcpDocument dict (may contain only the edited keys).

    Returns:
        dict of storage-shaped ICP fields (a subset of the SEED_ICP keys).
    """
    out: dict = {}
    if "title" in ui:
        out["vertical"] = ui["title"]
    if "keywords" in ui:
        out["want_signals"] = list(ui["keywords"] or [])
    if "geographicFocus" in ui:
        geos = ui["geographicFocus"] or []
        out["geo"] = geos[0] if geos else ""
    if "sizeBand" in ui:
        out["size_band"] = ui["sizeBand"]
    if "icpTags" in ui:
        out["icp_tags"] = list(ui["icpTags"] or [])
    if "anchorCompanies" in ui:
        out["anchor_companies"] = ui["anchorCompanies"] or []
    if "qualificationCriteria" in ui:
        avoid = []
        for c in ui["qualificationCriteria"] or []:
            crit = c.get("criterion", "") if isinstance(c, dict) else ""
            if isinstance(crit, str) and crit.startswith("Avoid: "):
                avoid.append(crit[len("Avoid: "):])
        out["avoid_signals"] = avoid
    return out


# ---------------------------------------------------------------------------
# stats_to_ui — seed stats dict → LeadDiscoveryStats (camelCase) (INTG6)
# ---------------------------------------------------------------------------

def stats_to_ui(stats: dict) -> dict:
    """Map seed stats keys to the FE LeadDiscoveryStats field names (camelCase).

    All keys are passed through; the dict must contain the following keys:
        goal, discovered, filteredByIcp, retained, belowFloor, aboveFloor,
        newCount, existingCount, alreadyInCrm, strong, review, weak, strictness

    Args:
        stats: The SEED_STATS dict (from api_seed.SEED_STATS).

    Returns:
        dict with the LeadDiscoveryStats camelCase keys (all present).
    """
    return {
        "goal": stats.get("goal", 0),
        "discovered": stats.get("discovered", 0),
        "filteredByIcp": stats.get("filteredByIcp", 0),
        "retained": stats.get("retained", 0),
        "belowFloor": stats.get("belowFloor", 0),
        "aboveFloor": stats.get("aboveFloor", 0),
        "newCount": stats.get("newCount", 0),
        "existingCount": stats.get("existingCount", 0),
        "alreadyInCrm": stats.get("alreadyInCrm", 0),
        "strong": stats.get("strong", 0),
        "review": stats.get("review", 0),
        "weak": stats.get("weak", 0),
        "strictness": stats.get("strictness", ""),
    }


# ---------------------------------------------------------------------------
# compute_stats_from_leads — derive LeadDiscoveryStats from real persisted leads
# (CONN3) — replaces the static SEED_STATS so the funnel reflects the DB.
# ---------------------------------------------------------------------------

_WIN_PROB_FLOOR = 0.5  # win_prob floor for the "above floor" funnel band


def compute_stats_from_leads(leads: list) -> dict:
    """Compute the LeadDiscoveryStats funnel from the persisted lead records.

    Every number is derived from the durable workspace (no static seed). All
    persisted leads are, by construction, retained/qualified (they cleared the
    ICP gate at ingest), so discovered == retained == len(leads); the narrowing
    band is win_prob >= _WIN_PROB_FLOOR.

    FitGrade buckets: Strong → strong, Medium → review, Weak → weak.
    LeadKind: Active_Client → existing, else → new.

    Args:
        leads: list of CRM lead records (from crm_store.all_leads()).

    Returns:
        dict in the camelCase LeadDiscoveryStats shape (same keys as stats_to_ui).
    """
    retained = len(leads)
    above = sum(1 for l in leads if l.get("win_prob", 0) >= _WIN_PROB_FLOOR)
    strong = sum(1 for l in leads if fit_grade(l.get("icp_count", 0)) == "Strong")
    review = sum(1 for l in leads if fit_grade(l.get("icp_count", 0)) == "Medium")
    weak = sum(1 for l in leads if fit_grade(l.get("icp_count", 0)) == "Weak")
    existing = sum(1 for l in leads if lead_kind(l.get("current_status", "")) == "Existing")
    in_crm = sum(1 for l in leads if l.get("stage") == "in_crm")

    return {
        "goal": retained,
        "discovered": retained,
        "filteredByIcp": 0,
        "retained": retained,
        "belowFloor": retained - above,
        "aboveFloor": above,
        "newCount": retained - existing,
        "existingCount": existing,
        "alreadyInCrm": in_crm,
        "strong": strong,
        "review": review,
        "weak": weak,
        "strictness": "Live (>=3 ICP signals)",
    }


# ===========================================================================
# Stage I3 — Outreach adapters (INTG7 / INTG8)
# Map the deterministic run_outreach_pipeline-shaped return → the FE Outreach
# Center types (OutreachStats, Cohort[], EnrollmentEvent[]). Pure functions.
# ===========================================================================

# Deterministic anchor for synthesized cohort timestamps (the pipeline carries
# no real timestamp; offline demo uses a fixed anchor + per-cohort day offset).
_COHORT_ANCHOR = datetime(2026, 3, 31, 16, 58, tzinfo=timezone.utc)
_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
           "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

# Variant key → FE label (deterministic A/B → control/email_heavy)
_VARIANT_LABELS = (("A", "control"), ("B", "email_heavy"))


def _fmt_cohort_dt(dt: datetime) -> str:
    """Format a datetime as e.g. 'Mar 31, 2026 4:58 PM' (OS-agnostic, no %-d)."""
    hour12 = dt.hour % 12 or 12
    ampm = "AM" if dt.hour < 12 else "PM"
    return f"{_MONTHS[dt.month - 1]} {dt.day}, {dt.year} {hour12}:{dt.minute:02d} {ampm}"


def brief_to_outreach_stats(pipeline_return: dict) -> dict:
    """Map a run_outreach_pipeline-shaped return → OutreachStats (camelCase).

    Output keys (EXACT — FE OutreachStats):
        totalCohorts, totalCompanies, inCampaign, inCampaignCohorts, replies, replyRate

    inCampaignCohorts = number of cohorts that have >= 1 successfully-sent lead
    (computed from dispatch_results, not the rolled-up brief, which lacks per-cohort data).
    """
    brief = pipeline_return.get("brief", {})
    cohorts = pipeline_return.get("cohorts", [])
    dispatch_results = pipeline_return.get("dispatch_results", [])

    sent_domains = {dr.get("domain") for dr in dispatch_results if dr.get("sent") is True}
    in_campaign_cohorts = sum(
        1 for cohort in cohorts
        if any((lead.get("domain") if isinstance(lead, dict) else lead) in sent_domains
               for lead in cohort)
    )

    return {
        "totalCohorts": brief.get("cohort_count", 0),
        "totalCompanies": brief.get("scheduled", 0),
        "inCampaign": brief.get("sent", 0),
        "inCampaignCohorts": in_campaign_cohorts,
        "replies": brief.get("replies", 0),
        "replyRate": brief.get("reply_rate", 0.0),
    }


def pipeline_to_cohorts(pipeline_return: dict) -> list:
    """Map a run_outreach_pipeline-shaped return → list[Cohort] (camelCase).

    Synthesizes the fields the pipeline does not carry (name, enrolledAt, variant
    stages) deterministically. Cohort i is enrolled at _COHORT_ANCHOR + i days.

    Each Cohort: {id, name, enrolledAt, leadsCount, variants:[CohortVariant]}
    Each CohortVariant: {label, stages:[CohortVariantStage], outcome:{dead, success}}
    """
    cohorts = pipeline_return.get("cohorts", [])
    dispatch_results = pipeline_return.get("dispatch_results", [])
    dr_by_domain = {dr.get("domain"): dr for dr in dispatch_results}

    out = []
    for idx, cohort in enumerate(cohorts):
        n = idx + 1
        dt = _COHORT_ANCHOR + timedelta(days=idx)

        groups: dict = {"A": [], "B": []}
        for lead in cohort:
            domain = lead.get("domain") if isinstance(lead, dict) else lead
            dr = dr_by_domain.get(domain, {})
            groups.setdefault(dr.get("variant", "A"), []).append(dr)

        variants = []
        for vkey, label in _VARIANT_LABELS:
            grp = groups.get(vkey, [])
            if not grp:
                continue
            sent = sum(1 for dr in grp if dr.get("sent") is True)
            failed = sum(1 for dr in grp if dr.get("sent") is not True)
            stages = [
                {"icon": "clock", "status": "done", "count": str(len(grp))},
                {"icon": "mail",
                 "status": "done" if sent else "queued",
                 "count": str(sent),
                 "gapBefore": "1d"},
            ]
            variants.append({
                "label": label,
                "stages": stages,
                "outcome": {"dead": failed, "success": sent},
            })

        out.append({
            "id": f"cohort-{n}",
            "name": f"Cohort {n}",
            "enrolledAt": _fmt_cohort_dt(dt),
            "leadsCount": len(cohort),
            "variants": variants,
        })
    return out


def cohorts_to_enrollments(cohorts_ui: list) -> list:
    """Derive EnrollmentEvent[] from already-mapped Cohort[] (camelCase).

    Each EnrollmentEvent: {id, date (ISO YYYY-MM-DD), label}. One per cohort,
    dated on the same deterministic enrollment day used in pipeline_to_cohorts.
    """
    out = []
    for idx, cohort in enumerate(cohorts_ui):
        n = idx + 1
        dt = _COHORT_ANCHOR + timedelta(days=idx)
        out.append({
            "id": f"enroll-{n}",
            "date": f"{dt.year:04d}-{dt.month:02d}-{dt.day:02d}",
            "label": f"{cohort.get('name', f'Cohort {n}')} enrolled",
        })
    return out
