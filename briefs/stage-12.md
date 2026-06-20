# Brief — Stage 12: Layer 5b — Profile Expander / contact discovery (`discover_contacts`)
Read first: CLAUDE.md → PLAN.md (Stage 12 + Phase 2) → QA_checklist.md (§10, `DISC1`–`DISC5`) → NOTES.md (2026-06-19 Phase 2 entry + Stage 10/11 handbacks), then this brief.

Goal: Add ONE new LLM-callable tool, `discover_contacts`, that finds candidate contacts for a qualified
brand (mocked Apollo + LLM-grounded search) and attaches their references to the CRM lead workspace.
Tool count **9 → 10**. Re-skin of SLED Layer-5 "Profile Expander".

## Scope — do ONLY Stage 12
The new tool + schema + dispatch + assert bump (9→10) + `tests/test_contact_discovery.py`. No L6.

## Governance design decision (READ — this shapes the whole tool)
`discover_contacts` is a **discovery/enrichment** tool that surfaces **NEW** candidate contacts. It must
**NOT** become a back-door around the Policy-4 auth gate:
- It performs **NO privileged read** of the auth-gated `lead_store` contacts collection.
- It exposes **NO stored private contact field** (no `email`/`corporate_access_key`/`interaction_history_count`
  from existing records).
- It surfaces only **freshly-discovered candidate data** (mocked) and attaches candidate **references** to
  the CRM lead's `contact_ids` (workspace metadata in `crm_store`).
- The Policy-4 gate (`lead_store.authenticate_and_get_contact`) remains the single, un-bypassed path to
  existing private records. Auth + `opt_out_status` for actual outbound are enforced LATER at L6 dispatch.

## The contract to build

### Signature & return
```python
def discover_contacts(brand_id: str, domain: str) -> dict:
```
Returns a JSON-serializable dict with EXACTLY these keys (DISC1):
```python
{
  "brand_id": str,
  "contacts": list[dict],   # each: {"first_name","last_name","role","email","linkedin_url"}
  "count":    int,          # == len(contacts)
}
```
The `email` values are **discovered/derived candidates** (e.g. pattern-guessed public emails), NOT pulled
from `contacts.json`. `count` must equal `len(contacts)`.

### Internal flow
1. Use the existing grounded path `_vector_a_search` (`main.py:374`) and/or one `_get_client()` Claude
   call (model: `LIGHT_MODEL`) to surface candidate people for `domain`. (Both monkeypatched in tests.)
2. Normalize to the contact shape above; de-dup by `email`.
3. **Attach to the CRM** (DISC3): call `crm_store.upsert_lead(...)` / a `crm_store` helper to append the
   discovered candidate identifiers (emails) to the lead's `contact_ids` for `brand_id`. This is workspace
   metadata — it writes NO private field and NO secret. If the lead does not yet exist, upsert a minimal
   record `{uniq_id: brand_id, domain, ...}`.
4. Wrap the whole body in `try/except`; on failure return `{"error": "discover_contacts failed: ..."}`
   (tool errors are data, never crashes — CLAUDE.md §6.6).

### Registration (mechanical — same as Stage 10)
- Add the function in `main.py` §5 (after `build_icp_document`, before §6 schemas).
- Add an Anthropic-shaped schema to `TOOL_SCHEMAS` (`name`/`description`/`input_schema`). Description
  ≥50 chars: *when to use* (after a brand qualifies, to find who to approach) + key constraint (returns
  discovered candidates only; does NOT read private CRM records — those need the auth gate). Inputs:
  `brand_id` (string, required) + `domain` (string, required).
- Add `"discover_contacts": discover_contacts` to `TOOL_DISPATCH`.
- **Bump the three import-time asserts 9 → 10** (`main.py`, the `len(...) == 9` lines). The system-prompt
  wording is already count-agnostic ("the tools available to you") — leave it.
- Update `tests/test_schemas.py`: add `"discover_contacts"` to the expected-names list and bump any
  `== 9` schema-count assertions to `== 10` (mirror how Stage 10 updated them to 9).

### Hard constraints (graded)
- **Import-safety (DISC5 / ENV4):** no client/model at import; lazy `_get_client()`. Prove
  `import main, lead_store, rag_engine, crm_store` side-effect-free.
- **DISC3 governance:** NO read of the auth-gated contacts collection; NO stored private field exposed;
  NO `corporate_access_key` anywhere. Discovery only writes `contact_ids` workspace metadata.
- **Anti-leakage (DISC4 / G2/G4):** no real catalog literals, no contacts.json values, no secrets
  hardcoded. Tool count == 10; three-way name-identity assert passes.
- **Deterministic under the mock (DISC2):** monkeypatched client + `_vector_a_search` → stable output.

## Testing — `tests/test_contact_discovery.py` (TDD; PM runs the full suite)
Mirror the Stage-10 mocking pattern (monkeypatch `main._get_client` + `main._vector_a_search`) and the
Stage-11 singleton-reset (`crm_store._leads_collection = None`). Cover:
- `DISC1` exact key set + `count == len(contacts)` + JSON-serializable.
- `DISC2` deterministic under the mock; de-dup by email; no live egress.
- `DISC3` after a call, the CRM lead for `brand_id` has the discovered emails in `contact_ids`, AND the
  function never touched `lead_store` private records — assert no stored `corporate_access_key`/private
  email appears in the output, and that `discover_contacts` returns only the mocked candidate data.
- `DISC4` `len(TOOL_SCHEMAS) == 10`, name-identity holds, `discover_contacts` in dispatch; no catalog/secret literals.
- `DISC5` import-safety holds (ENV4).
- Use only synthetic data; no real `corporate_access_key`/catalog literals in the test.

## Do NOT
- Advance past Stage 12 (no L6). Do not modify `lead_store.py`'s auth semantics, `evaluate_icp_tags`,
  the RRF engine, the gateway, `crm_store`'s auth gate, or any graded literal.
- **Do not edit PLAN.md status** — leave stage status to the PM. (You may append your handback to NOTES.md.)
- Any contract change beyond the sanctioned tool-count bump (9→10) → **DECISION-NEEDED**, then stop.

## Deliver
Write `handbacks/stage-12.md` (CLAUDE.md §12 format): what changed; DoD `DISC1`–`DISC5` (drafted vs
written); tests written; decisions; deviations; blockers; one next action. Append it to NOTES.md and
return it as your final message.
