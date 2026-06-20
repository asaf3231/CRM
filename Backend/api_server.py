"""
api_server.py — ReactFirst AI Proactive Outbound Engine
Phase 3 Integration Layer: FastAPI HTTP server exposing the backend to the React frontend.

Run command:
    uvicorn api_server:app --port 8000

Import-safety contract (INTG1 / ENV4):
    `import api_server` has ZERO side effects — no crm_store/lead_store/main imports at
    module top-level, no file reads, no network calls.  The FastAPI `app` object is
    constructed with no backend work.  Any backend import happens lazily inside a handler
    or the lifespan body, never at module scope.

CORS:
    allow_origins = ["http://localhost:5173"] only (localhost Vite dev server).
    Decision recorded in NOTES.md (2026-06-19 Phase 3 entry).

Author: Asaf (ReactFirst AI)
"""

import contextlib
import os
from typing import List

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Lifespan — startup / shutdown hook
# Seed fires on ASGI startup (lifespan), NEVER at import time (INTG1).
# ---------------------------------------------------------------------------

@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    """ASGI lifespan context manager.

    On startup: lazily imports api_seed and calls seed_demo() to populate
    the crm_store with the 16 deterministic example leads.
    The import happens HERE (inside lifespan body), never at module top-level,
    preserving the import-safety contract (INTG1 / ENV4).
    """
    import api_seed  # lazy — preserves import-safety
    api_seed.seed_demo()

    yield  # startup complete — serve requests
    # (no teardown needed)


# ---------------------------------------------------------------------------
# FastAPI app — constructed with no backend side effects
# ---------------------------------------------------------------------------

app = FastAPI(
    title="ReactFirst Outbound Engine API",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS — localhost dev by default; override in prod via the ALLOWED_ORIGINS env var
# (comma-separated), e.g. ALLOWED_ORIGINS="https://your-app.vercel.app" on Railway.
# Reading an env var is not an import side effect (ENV4-safe). Decision: NOTES.md Phase 3.
_allowed_origins = [
    o.strip()
    for o in os.environ.get("ALLOWED_ORIGINS", "http://localhost:5173").split(",")
    if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Pydantic request model for POST /api/leads/find-more
# ---------------------------------------------------------------------------

class FindMoreRequest(BaseModel):
    """Request body for POST /api/leads/find-more (INTG4)."""
    existing_domains: List[str] = []
    target: int = 10


# ---------------------------------------------------------------------------
# Routes — Stage I1 scaffold
# ---------------------------------------------------------------------------

@app.get("/api/health")
async def health() -> dict:
    """INTG3: liveness probe."""
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Routes — Stage I2: Leads endpoints
# ---------------------------------------------------------------------------

@app.get("/api/leads")
async def get_leads() -> list:
    """INTG4: GET /api/leads → list[Lead].

    Reads all leads from crm_store, filters out Blacklisted records (pre-adapter),
    maps each through crm_lead_to_ui (camelCase), returns sorted by uniq_id
    for deterministic ordering.

    crm_store and api_adapters are imported lazily (preserves import-safety / INTG1).
    """
    import crm_store        # lazy
    import api_adapters     # lazy

    records = crm_store.all_leads()
    # Filter out Blacklisted records pre-adapter (brief spec)
    filtered = [r for r in records if r.get("current_status") != "Blacklisted"]
    # Sort by uniq_id for deterministic order
    filtered.sort(key=lambda r: r.get("uniq_id", ""))
    return [api_adapters.crm_lead_to_ui(r) for r in filtered]


@app.get("/api/leads/stats")
async def get_leads_stats() -> dict:
    """INTG4: GET /api/leads/stats → LeadDiscoveryStats.

    Returns the seed stats dict mapped through stats_to_ui (camelCase).
    api_seed and api_adapters are imported lazily.
    """
    import api_seed         # lazy
    import api_adapters     # lazy

    return api_adapters.stats_to_ui(api_seed.SEED_STATS)


@app.post("/api/leads/find-more")
async def find_more_leads(body: FindMoreRequest) -> list:
    """INTG4: POST /api/leads/find-more → deduped list[Lead].

    From the seed pool, excludes any lead whose domain (lowercased) is in
    the existing_domains set (lowercased), returns up to `target` of the
    remaining leads mapped via crm_lead_to_ui.

    Offline/deterministic — returns unseen seed pool rows; no live discovery.
    crm_store and api_adapters imported lazily.
    """
    import crm_store        # lazy
    import api_adapters     # lazy

    existing_lower = {d.lower() for d in body.existing_domains}
    records = crm_store.all_leads()
    # Filter Blacklisted and already-seen domains
    candidates = [
        r for r in records
        if r.get("current_status") != "Blacklisted"
        and r.get("domain", "").lower() not in existing_lower
    ]
    # Sort deterministically, then return up to target
    candidates.sort(key=lambda r: r.get("uniq_id", ""))
    return [api_adapters.crm_lead_to_ui(r) for r in candidates[: body.target]]


@app.get("/api/leads/{lead_id}")
async def get_lead_detail(lead_id: str) -> dict:
    """GET /api/leads/{id} → LeadDetail (lead-detail drawer source).

    Fetches the CRM record by uniq_id and maps it through crm_lead_to_detail.
    404 if the lead does not exist.  Contacts stay EMPTY in the response — the
    API holds no corporate_access_key, so the Policy-4 gate is not satisfied and
    no private contact field is exposed (contact_ids are stripped too).

    Declared AFTER /api/leads and /api/leads/stats (and the POST find-more) so
    those static paths match first — Starlette matches routes in declaration
    order, so `{lead_id}` only catches the genuinely-dynamic case.

    crm_store and api_adapters are imported lazily (preserves import-safety / INTG1).
    """
    import crm_store        # lazy
    import api_adapters     # lazy

    record = crm_store.get_lead(lead_id)
    if record is None:
        raise HTTPException(status_code=404, detail="lead not found")
    return api_adapters.crm_lead_to_detail(record)


# ---------------------------------------------------------------------------
# Routes — Stage I2: ICP endpoints
# ---------------------------------------------------------------------------

@app.get("/api/icp")
async def get_icp() -> dict:
    """INTG6: GET /api/icp → IcpDocument.

    Returns the seed ICP document (offline — no live build_icp_document call).
    api_seed and api_adapters imported lazily.
    """
    import api_seed         # lazy
    import api_adapters     # lazy

    return api_adapters.icp_doc_to_ui(api_seed.SEED_ICP)


@app.get("/api/icp/suggestions")
async def get_icp_suggestions() -> list:
    """INTG6: GET /api/icp/suggestions → list[str].

    Returns the SEED_ICP want_signals list.
    api_seed imported lazily.
    """
    import api_seed  # lazy

    return api_seed.SEED_ICP["want_signals"]


# ---------------------------------------------------------------------------
# Routes — Stage I3: Outreach endpoints (INTG7 / INTG8)
# ---------------------------------------------------------------------------

# Demo cohort throttle: batch the seed leads into a few cohorts (<= DAILY_SEND_CAP)
# so the Outreach Center timeline/calendar has several entries. Still uses the REAL
# schedule_outreach_cohort batcher (the DAILY_SEND_CAP=50 ceiling is never exceeded).
_DEMO_DAILY_CAP = 6


def _build_outreach_demo() -> dict:
    """Build a deterministic, offline run_outreach_pipeline-shaped result.

    Uses the REAL backend building blocks:
      - main.schedule_outreach_cohort(...) to batch the seeded outbound-eligible leads,
      - main.outreach_status_brief(...) to compute the rollup,
    with a deterministic dispatch_results (variant by index parity; "sent" iff the
    lead's stage shows outreach progress). No auth/network — pure offline demo.

    Returns {"cohorts": [...], "dispatch_results": [...], "brief": {...}}.
    crm_store / main imported lazily (import-safety / INTG1).
    """
    import crm_store  # lazy
    import main       # lazy

    leads = [r for r in crm_store.all_leads() if r.get("current_status") != "Blacklisted"]
    leads.sort(key=lambda r: r.get("uniq_id", ""))

    sched = main.schedule_outreach_cohort(leads, _DEMO_DAILY_CAP)
    cohorts = sched.get("cohorts", [])

    _SENT_STAGES = {"enrolled", "outreach", "replied", "in_crm"}
    dispatch_results = []
    global_index = 0
    for cohort in cohorts:
        for lead in cohort:
            dispatch_results.append({
                "domain": lead.get("domain", ""),
                "sent": lead.get("stage", "") in _SENT_STAGES,
                "variant": "A" if global_index % 2 == 0 else "B",
            })
            global_index += 1

    brief = main.outreach_status_brief({"cohorts": cohorts, "dispatch_results": dispatch_results})
    return {"cohorts": cohorts, "dispatch_results": dispatch_results, "brief": brief}


@app.get("/api/outreach/stats")
async def get_outreach_stats() -> dict:
    """INTG7: GET /api/outreach/stats → OutreachStats (from the full pipeline return)."""
    import api_adapters  # lazy
    return api_adapters.brief_to_outreach_stats(_build_outreach_demo())


@app.get("/api/outreach/cohorts")
async def get_outreach_cohorts() -> list:
    """INTG7: GET /api/outreach/cohorts → list[Cohort] (synthesized from real cohorts)."""
    import api_adapters  # lazy
    return api_adapters.pipeline_to_cohorts(_build_outreach_demo())


@app.get("/api/outreach/enrollments")
async def get_outreach_enrollments() -> list:
    """INTG8: GET /api/outreach/enrollments → list[EnrollmentEvent] (from real cohort data)."""
    import api_adapters  # lazy
    pipeline_return = _build_outreach_demo()
    cohorts_ui = api_adapters.pipeline_to_cohorts(pipeline_return)
    return api_adapters.cohorts_to_enrollments(cohorts_ui)


# NOTE — FE-mock-only in v1 (no backend route; the network tab stays real-data only):
#   getReachSeries, getAgentEvents, runDiscovery, getSwarmStages
# TODO I5: /api/outreach/reach, /api/outreach/agent-events, /api/pipeline/discover|swarm
