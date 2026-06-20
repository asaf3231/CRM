# Handback — Stage 11

## 1. What changed

**New files:**
- `/Users/asaframati/Documents/CRM/crm_store.py` — NEW module. Lazy mongomock mini-CRM lead workspace (SLED Layer 5). Import-safe (zero side effects). Contains:
  - `_leads_collection = None` (module-level lazy singleton, CRM1)
  - `get_crm_collection()` — lazy builder, db `gtm_db`, collection `leads`, starts EMPTY
  - `upsert_lead(record)` — idempotent upsert keyed on `uniq_id` (CRM3)
  - `get_lead(uniq_id)` — fetch by key, `None` if absent
  - `update_lead_stage(uniq_id, stage)` — update stage + `updated_at`
  - `attach_contact(caller_key, uniq_id, target_email)` — Policy-4 auth-gated (CRM4)
  - `outbound_eligible_contacts(caller_key, uniq_id, emails)` — opt-out filtered (CRM5)
  - `compute_win_prob(tier_label, incidents, icp_count, pixel_count)` — deterministic, catalog-sourced, clamped to [0,1] (CRM6)

- `/Users/asaframati/Documents/CRM/tests/test_crm_store.py` — 53 tests covering CRM1–CRM8 + ENV4 cross-check.

**Modified files:**
- `/Users/asaframati/Documents/CRM/main.py` — two additive changes:
  1. Section 2: added `import crm_store` (import-safe; listed after `import pandas`)
  2. `write_qualified_leads`: added CRM upsert loop after the JSON file write, wrapped in `try/except` so CRM failures never affect the file write, shape, or return
- `/Users/asaframati/Documents/CRM/tests/test_integration.py` — added `"crm_store"` to `TestH1PinnedDependencies.LOCAL_MODULES` so the H1 test correctly classifies it as first-party (not unpinned third-party)
- `/Users/asaframati/Documents/CRM/NOTES.md` — appended Stage 11 handback with compute_win_prob weights

## 2. DoD checklist

| Check | Status | How verified |
|---|---|---|
| `CRM1` — lazy singleton; None after import | ✅ written+verified | `test_singleton_is_none_at_import`, `test_collection_builds_on_first_call`, `test_collection_is_singleton`, `test_collection_starts_empty`; ENV4 from empty `/tmp` dir; all pass |
| `CRM2` — record shape on upsert | ✅ written+verified | `TestCRM2RecordShape` — all 10 required keys, correct types, no `_id`, JSON-serializable, defaults applied |
| `CRM3` — upsert/get/update_stage round-trip; idempotent | ✅ written+verified | `TestCRM3RoundTrip` — upsert→get; not-found→None; two upserts→one doc; field update; stage update+timestamp; missing uniq_id raises |
| `CRM4` — auth gate is single chokepoint | ✅ written+verified | `TestCRM4AuthGate` — valid key attaches; no-key→denial; wrong-key→identical denial; denial does NOT modify lead; denial leaks no field; key never in result string |
| `CRM5` — opt_out suppressed from outbound | ✅ written+verified | `TestCRM5OptOutSuppression` — opted-out attach→`ok=False,reason=opted_out`; email not in contact_ids; `outbound_eligible_contacts` excludes opted-out |
| `CRM6` — compute_win_prob deterministic, catalog-sourced, clamped | ✅ written+verified | `TestCRM6WinProb` — deterministic; tier ordering; float return; clamp at 0.0 and 1.0; unknown tier fallback; bonus scaling+capping; exact arithmetic checks; unit-interval sweep |
| `CRM7` — no secret in payload/log/tracked file | ✅ written+verified | `TestCRM7NoSecretLeak` — upsert, get, attach success, outbound eligible results all checked via JSON serialization; no `corporate_access_key` key or value appears |
| `CRM8` — write_qualified_leads upserts CRM; JSON stays ≤3-capped | ✅ written+verified | `TestCRM8WriteQualifiedLeads` — upserts happen; JSON shape unchanged (domain/angle_key/tier/pdf_path); 4 entries→capped to 3; CRM failure does NOT break file write |

## 3. QA results

**`tests/test_crm_store.py` alone:**
```
.venv/bin/python -m pytest tests/test_crm_store.py -v
======================== 53 passed, 1 warning in 0.47s =========================
```

**Full regression:**
```
.venv/bin/python -m pytest tests/ -q
564 passed, 1 skipped, 245 warnings in 31.86s
```
(1 skipped = S10, gated on `ANTHROPIC_API_KEY` — unchanged from Stage 10 baseline of 511.)

**ENV4 import-safety (from empty `/tmp`):**
```
cd /tmp && .venv/bin/python -c "import sys; sys.path.insert(0, '/Users/asaframati/Documents/CRM'); import main, lead_store, rag_engine, crm_store; print('import-safe: ok'); ..."
import-safe: ok
main._anthropic_client: None
lead_store._collection_instance: None
rag_engine._collection_instance: None
crm_store._leads_collection: None
```

**G1 grep (no raw eval/exec):**
```
grep -n "eval(\|exec(" crm_store.py main.py | grep -v "#" | ...
(no output — clean)
```

## 4. Decisions made

1. **compute_win_prob weights (CRM6 / Policy 1):**
   - `tier_base`: "Tier 1" → 0.40 / "Tier 2" → 0.25 / "Tier 3" → 0.10 / unknown → 0.10
   - `icp_bonus`: +0.10 × min(icp_count, 5)  — primary qualification signal
   - `incident_bonus`: +0.04 × min(incidents, 5) — PR crisis urgency signal
   - `pixel_bonus`: +0.05 × min(pixel_count, 3) — tracking infrastructure maturity
   - `final`: max(0.0, min(1.0, sum)) — clamped to [0,1]
   - Max theoretical: 1.25 → 1.0. Min theoretical: 0.10 → 0.0.

2. **CRM upsert key in write_qualified_leads**: uses `domain` as `uniq_id` (qualified leads are domain-indexed in the CRM workspace). Stage 12 can enrich with catalog `Uniq_Id` when available.

3. **Singleton reset vs importlib.reload in tests**: the `seeded_stores`/`fresh_crm` fixtures reset singletons directly (`._leads_collection = None`) instead of `importlib.reload()` — avoids `ImportError: module not in sys.modules` caused by `test_catalog.py` ENV4 tests that remove+re-import modules in the same pytest session. Test-hygiene decision, not a contract change.

4. **LOCAL_MODULES update in test_integration.py**: added `"crm_store"` as a first-party module. H1 contract (all third-party imports pinned) is preserved.

## 5. DECISION-NEEDED

None. No tool signature, schema, policy constant, loop contract, or graded literal was changed.

## 6. Deviations

None from the brief. `write_qualified_leads` signature, return value, and `qualified_leads.json` shape/cap are byte-stable. Tool count stays 9. `TOOL_SCHEMAS`/`TOOL_DISPATCH` unchanged.

## 7. Blockers / risks

None. No new external dependencies, no new API keys. All external transports remain mocked. Live smokes still gated on OQ-7 (unchanged).

## 8. Next recommended action

Dispatch **Stage 12** (L5b Profile Expander / contact discovery — `discover_contacts` tool, checks `DISC1`–`DISC5`).
