# Brief — Stage 11: Layer 5a — mini-CRM lead workspace (`crm_store.py`)
Read first: CLAUDE.md → PLAN.md (Stage 11 + Phase 2 section) → QA_checklist.md (§10, `CRM1`–`CRM8`) → NOTES.md (2026-06-19 Phase 2 entry), then this brief.

Goal: Create a NEW module `crm_store.py` — a stateful mini-CRM **lead workspace** over the existing
contacts store — so qualified leads become durable, manageable records. This is the CRM heart (SLED
Layer 5, re-skinned). **Model it exactly on `lead_store.py`'s lazy-singleton + auth-gate pattern.**

## Scope — do ONLY Stage 11
Build `crm_store.py`, the `compute_win_prob` helper, the additive CRM upsert in `write_qualified_leads`,
and `tests/test_crm_store.py`. Do NOT build L5b contact-discovery (that is Stage 12) or any L6 outreach.
Do NOT add a new LLM tool this stage (no `TOOL_SCHEMAS`/`TOOL_DISPATCH` change — tool count stays 9).

## The module to build — `crm_store.py`

Mirror `lead_store.py` (read it first). Import-safe: ZERO side effects at import; all work lazy.

### Lazy singleton (CRM1)
```python
_leads_collection = None
def get_crm_collection():
    """mongomock 'leads' collection in db 'gtm_db'. Built on FIRST call, not at import.
    Unlike lead_store, this starts EMPTY (no file load) — it is a workspace populated by upserts."""
```
After `import crm_store`, the module-level singleton MUST be `None` (ENV4). No file I/O at import.

### Lead record shape (CRM2) — keyed on brand `Uniq_Id`
```python
{
  "uniq_id": str,            # PRIMARY KEY (== brands_catalog Uniq_Id)
  "domain": str,
  "status": str,            # e.g. "qualified" | "contacted" | "disqualified"
  "stage": str,             # workspace pipeline stage, e.g. "new" | "researching" | "outreach" | "won"
  "profile": dict,          # arbitrary enrichment blob (from analyze_company_chunk etc.)
  "contact_ids": list,      # references to lead_store contacts (emails or ids) — see CRM4
  "win_prob": float,        # 0.0..1.0 from compute_win_prob
  "outreach_state": dict,   # reserved for L6 (default {})
  "notes": str,
  "updated_at": str,        # ISO 8601 UTC timestamp (datetime.now(timezone.utc).isoformat())
}
```

### Functions
- `upsert_lead(record: dict) -> dict` — idempotent upsert keyed on `uniq_id` (mongomock
  `replace_one({"uniq_id":...}, doc, upsert=True)`). Same `uniq_id` UPDATES in place, never duplicates
  (CRM3). Sets/refreshes `updated_at`. Fills missing optional keys with safe defaults. Returns the
  stored record **without** mongo's `_id` (strip it, like `lead_store` does). JSON-serializable.
- `get_lead(uniq_id: str) -> dict | None` — fetch by key, `_id` stripped; `None` if absent.
- `update_lead_stage(uniq_id: str, stage: str) -> dict` — update `stage` + `updated_at`; returns the
  updated record (or `{"error": "not_found"}` if no such lead — generic, leaks nothing).
- `attach_contact(caller_key: str, uniq_id: str, target_email: str) -> dict` — **AUTH-GATED (CRM4)**:
  calls `lead_store.authenticate_and_get_contact(caller_key, target_email)`; on the `{"error":"unauthorized"}`
  denial, return it UNCHANGED and DO NOT modify the lead (no field leaked). On success, and only if the
  contact is NOT opted out (`lead_store.is_opted_out`, CRM5), append the contact identifier to the lead's
  `contact_ids` and return `{"ok": True, "uniq_id":..., "contact_ids":[...]}`. NEVER put
  `corporate_access_key` (or any secret) into the lead record, the return, or a log (CRM7).
- `outbound_eligible_contacts(caller_key: str, uniq_id: str, emails: list) -> list` (CRM5) — return only
  the auth-passing, NON-opted-out contacts; opted-out ones are excluded.

### `compute_win_prob` (CRM6) — put in `crm_store.py`
```python
def compute_win_prob(tier_label: str, incidents: int, icp_count: int, pixel_count: int) -> float:
```
- **Deterministic**, pure function. **Catalog/record-sourced inputs only** (Policy 1) — `tier_label`
  from `Estimated_Ad_Spend_Tier`, `incidents` from `Historical_Social_Incidents`, `icp_count` from
  `evaluate_icp_tags`, `pixel_count` from `analyze_company_chunk`. NO parametric invention, NO LLM.
- Combine into a bounded **[0.0, 1.0]** score (clamp). Choose explicit, documented weights, e.g.:
  `Tier 1`→0.40 / `Tier 2`→0.25 / `Tier 3`→0.10 base; `+0.10 * min(icp_count, 5)`;
  `+0.04 * min(incidents, 5)`; `+0.05 * min(pixel_count, 3)`; then `max(0.0, min(1.0, score))`.
  **Record the exact weights you pick in the handback + NOTES.** Boundary-test the clamp (0.0 and 1.0).

## CRM8 — wire `write_qualified_leads` (main.py:2765) ADDITIVELY
Keep its existing signature, return value, and the `qualified_leads.json` shape/≤3-cap **byte-stable**
(E1/E4/`CL*` tests must stay green). After it builds the capped lead list, ALSO upsert each into the CRM
via `crm_store.upsert_lead(...)`, wrapped in `try/except` so a CRM failure never breaks the file write
or changes the return. Import `crm_store` at the TOP of `main.py` with the other first-party imports
(import-safe — `crm_store` does nothing at import).

## Hard constraints (graded)
- **Import-safety (CRM1/ENV4):** prove `import main, lead_store, rag_engine, crm_store` is side-effect-free
  and `crm_store._leads_collection is None` after import.
- **Auth gate is the single chokepoint (CRM4):** no path in `crm_store.py` reads/exposes a private
  contact field without going through `lead_store.authenticate_and_get_contact`. Denial is generic and
  leaks no field and no key.
- **No secret in any payload/log/tracked file (CRM7 / G4).**
- **Deterministic, catalog-sourced win-prob (CRM6 / Policy 1).**
- OS-agnostic paths; tool/helpers fail loudly but never crash the caller.

## Testing — `tests/test_crm_store.py` (TDD; PM runs it)
Your sandbox may or may not run Python — write tests carefully regardless; PM runs the FULL suite.
Reuse the fixture style in `tests/test_lead_store.py` (it seeds a mongomock contacts store from a temp
`contacts.json`; reset both singletons between tests — `lead_store._collection_instance = None` and
`crm_store._leads_collection = None`). Cover every check:
- `CRM1` import-safe + lazy (singleton None post-import; collection builds on first call).
- `CRM2` shape on upsert.
- `CRM3` idempotent upsert (two upserts of same `uniq_id` → one record, fields updated) + get + update_stage round-trip.
- `CRM4` `attach_contact` with valid key attaches; no-key and wrong-key both return the generic denial and DO NOT modify the lead / leak any field or key.
- `CRM5` opted-out contact excluded from `outbound_eligible_contacts` and not attached.
- `CRM6` `compute_win_prob` deterministic (same inputs→same output) + catalog-sourced + clamped to [0,1] at both boundaries.
- `CRM7` no `corporate_access_key` value appears in any returned record/log.
- `CRM8` after a `write_qualified_leads` run, the CRM has upserted records AND `qualified_leads.json` is unchanged (≤3 capped) — assert the file write/return is identical to before (mock the PDF entries like the existing E2E tests).
- Do NOT use any real `corporate_access_key`/secret literal in the test — use synthetic keys like the existing `tests/test_lead_store.py` (`TestKey001`, etc.).

## Do NOT
- Advance past Stage 11. No L5b discovery, no L6, no new LLM tool, no TOOL_SCHEMAS/DISPATCH change.
- Touch `lead_store.py`'s auth semantics, `evaluate_icp_tags`, the RRF engine, the gateway, or any graded literal.
- Change `write_qualified_leads`'s file shape, cap, signature, or return — additive CRM upsert ONLY.
- Any contract change beyond this brief → **DECISION-NEEDED** in the handback, and stop.

## Deliver
Write `handbacks/stage-11.md` (CLAUDE.md §12 format): what changed; DoD `CRM1`–`CRM8` (drafted vs
written); tests written; decisions (esp. the win-prob weights); deviations; blockers; one next action.
Return it as your final message. Append the handback to NOTES.md as well.
