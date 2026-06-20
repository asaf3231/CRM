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
import threading
from typing import List, Optional

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Single-job lock for live discovery (one run at a time). Constructing a Lock is
# side-effect-free, so this is import-safe (ENV4).
_DISCOVERY_LOCK = threading.Lock()


# ---------------------------------------------------------------------------
# Lifespan — startup / shutdown hook
# Seed fires on ASGI startup (lifespan), NEVER at import time (INTG1).
# ---------------------------------------------------------------------------

@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    """ASGI lifespan context manager.

    On startup: lazily imports api_seed and (1) calls seed_demo() to populate
    the crm_store with the 16 deterministic example leads (seed-if-empty), and
    (2) calls seed_icp_if_empty() to persist the ICP document into the durable
    `icp_documents` collection (connection-plan C6 / CONN9).
    The import happens HERE (inside lifespan body), never at module top-level,
    preserving the import-safety contract (INTG1 / ENV4).
    """
    import api_seed  # lazy — preserves import-safety
    api_seed.seed_demo()
    api_seed.seed_icp_if_empty()

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


class IcpUpdate(BaseModel):
    """Request body for PUT /api/icp (CONN13). Mirrors the FE IcpDocument (camelCase).

    All fields optional so a partial edit merges into the stored doc (merge-preserve);
    only the keys the client sends are updated, the rest are preserved server-side.
    """
    title: Optional[str] = None
    description: Optional[str] = None
    keywords: Optional[List[str]] = None
    industryVerticals: Optional[List[str]] = None
    geographicFocus: Optional[List[str]] = None
    sizeBand: Optional[str] = None
    icpTags: Optional[List[str]] = None
    qualificationCriteria: Optional[List[dict]] = None
    anchorCompanies: Optional[List[dict]] = None


# ---------------------------------------------------------------------------
# Routes — Stage I1 scaffold
# ---------------------------------------------------------------------------

@app.get("/api/health")
async def health() -> dict:
    """INTG3 / CONN2: liveness + DB-awareness probe.

    When MONGO_URI is set, pings Mongo (admin 'ping') and reports db: "up"|"down".
    When unset (offline/mongomock), reports db: "mock". A down/unreachable Mongo
    returns a graceful degraded body (status "degraded"), never a 500/hang.
    db is imported lazily so import-safety (ENV4) is preserved.
    """
    import db  # lazy — no client built at import

    if not db.using_real_mongo():
        return {"status": "ok", "db": "mock"}
    try:
        db.get_mongo_client().admin.command("ping")
        return {"status": "ok", "db": "up"}
    except Exception:  # noqa: BLE001 — surface as degraded, never crash
        return {"status": "degraded", "db": "down"}


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
    """INTG4 / CONN3: GET /api/leads/stats → LeadDiscoveryStats.

    Computes the funnel from the REAL persisted workspace (crm_store.all_leads),
    not the static SEED_STATS — so the dashboard header reflects the actual DB.
    Blacklisted records are excluded pre-compute. crm_store and api_adapters are
    imported lazily (import-safety / INTG1).
    """
    import crm_store        # lazy
    import api_adapters     # lazy

    leads = [r for r in crm_store.all_leads() if r.get("current_status") != "Blacklisted"]
    return api_adapters.compute_stats_from_leads(leads)


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
    """INTG6 / CONN9: GET /api/icp → IcpDocument.

    Serves the ICP from the durable `icp_documents` collection
    (api_seed.get_icp_document) — not the in-memory SEED_ICP constant — so the
    response reflects the persisted (and editable) doc. Falls back to SEED_ICP
    if the collection is empty (never 500/empty). api_seed and api_adapters
    imported lazily (import-safety / INTG1).
    """
    import api_seed         # lazy
    import api_adapters     # lazy

    return api_adapters.icp_doc_to_ui(api_seed.get_icp_document())


@app.get("/api/icp/suggestions")
async def get_icp_suggestions() -> list:
    """INTG6 / CONN9: GET /api/icp/suggestions → list[str].

    Returns the want_signals from the persisted ICP document (not the static
    SEED_ICP constant). api_seed imported lazily.
    """
    import api_seed  # lazy

    return api_seed.get_icp_document().get("want_signals", [])


@app.put("/api/icp")
async def update_icp(body: IcpUpdate) -> dict:
    """CONN13: PUT /api/icp → persist an edited ICP, return the saved IcpDocument.

    Maps the UI IcpDocument (camelCase) back to storage shape (api_adapters.ui_to_icp_doc),
    merge-persists it into the durable `icp_documents` collection
    (api_seed.upsert_icp_document — merge-preserve), and returns the saved doc via
    icp_doc_to_ui so the client gets exactly what a subsequent GET /api/icp would serve.
    Only the fields the client sent are updated; the rest are preserved. The ICP carries
    no private contact fields (no Policy-4 gate). api_seed/api_adapters imported lazily (INTG1).
    """
    import api_seed       # lazy
    import api_adapters   # lazy

    ui = {k: v for k, v in body.model_dump().items() if v is not None}
    storage_fields = api_adapters.ui_to_icp_doc(ui)
    saved = api_seed.upsert_icp_document(storage_fields)
    return api_adapters.icp_doc_to_ui(saved)


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


# ---------------------------------------------------------------------------
# Routes — Stage C4: live, ICP-driven discovery (async job; connection-plan C4)
# Gated by ENABLE_LIVE + a DISCOVERY_TOKEN header + a single-job lock. A run is
# 2-5 min, so POST kicks off a background thread and returns a jobId; the FE polls
# GET .../{jobId}. pipeline_runner + os are imported lazily (import-safety / ENV4).
# ---------------------------------------------------------------------------

class DiscoverRequest(BaseModel):
    """Request body for POST /api/pipeline/discover (CONN7)."""
    seed: Optional[str] = None


def _live_enabled() -> bool:
    return os.environ.get("ENABLE_LIVE", "").strip().lower() in {"1", "true", "yes", "on"}


@app.post("/api/pipeline/discover")
async def start_discovery(
    body: DiscoverRequest,
    x_discovery_token: Optional[str] = Header(default=None),
) -> dict:
    """CONN7: kick off a live discovery run; return {jobId, status:"running"} immediately.

    403 if ENABLE_LIVE is not set; 401 on a missing/invalid DISCOVERY_TOKEN; 409 if a
    run is already in progress (single-job lock). The actual run executes on a daemon
    thread (pipeline_runner.run_discovery), writing progress to the pipeline_jobs doc.
    """
    if not _live_enabled():
        raise HTTPException(status_code=403, detail="live discovery disabled (ENABLE_LIVE not set)")
    expected = os.environ.get("DISCOVERY_TOKEN", "")
    if not expected or x_discovery_token != expected:
        raise HTTPException(status_code=401, detail="invalid or missing discovery token")

    import pipeline_runner  # lazy

    if not _DISCOVERY_LOCK.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="a discovery run is already in progress")
    try:
        job_id = pipeline_runner.create_job(body.seed)
    except Exception:
        _DISCOVERY_LOCK.release()
        raise

    def _run() -> None:
        try:
            pipeline_runner.run_discovery(job_id, body.seed)
        finally:
            _DISCOVERY_LOCK.release()

    threading.Thread(target=_run, daemon=True).start()
    return {"jobId": job_id, "status": "running"}


@app.get("/api/pipeline/discover/{job_id}")
async def discovery_status(job_id: str) -> dict:
    """CONN7: poll a discovery job → {jobId, status, stage, discovered[], qualified[], saved[]}."""
    import pipeline_runner  # lazy

    job = pipeline_runner.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    return {
        "jobId": job["job_id"],
        "status": job.get("status"),
        "stage": job.get("stage"),
        "seed": job.get("seed", ""),
        "discovered": job.get("discovered", []),
        "qualified": job.get("qualified", []),
        "saved": job.get("saved", []),
        "error": job.get("error"),
    }


# NOTE — still FE-mock-only (no backend route): getReachSeries, getAgentEvents, getSwarmStages.
#   runDiscovery is now backed by POST/GET /api/pipeline/discover above.
