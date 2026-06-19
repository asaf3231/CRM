# Handback — Stage 5

## 1. What changed

### `main.py` — changes in place (no new files outside `tests/`)

**§1 Header block** — stage tag updated from "Stage 4" to "Stage 5".

**§3 `_SYSTEM_PROMPT_TEMPLATE`** — hardened with explicit Policy 1 and Policy 2 language:
- Policy 1 language: `MUST NOT assert` any brand market-position/tier/competitor fact not from the catalog; cites `brands_catalog.csv` as the authoritative source; warns against inventing brand facts.
- Policy 2 language: brands qualify `IF AND ONLY IF evaluate_icp_tags` returns `qualified=True` with count >= 3; explicitly forbids proceeding to angle-matching or PDF generation without this gate.

**§8 `gateway_validate`** — replaced the permissive pass-through stub with the full hardened validator:
- GW1: null/None and empty required-field rejection.
- GW2: format regexes on `target_domain` (raw, not normalized), `validated_angle_key`, `tier_label`/`tier` (string only).
- GW3: all rejections return structured `{"valid": False, "error": ...}` — never exceptions.
- GW4: PDF health via new `_check_pdf_health()` helper — `%PDF-` magic header, non-zero length, `%%EOF` marker.
- GW5: angles list capped to `MAX_ANGLES=3` via `cap_angles()`; `angles_capped` flag recorded.
- Internal control payloads (`type` in `{"final_output", "cap_exhausted", "internal"}`) pass through after GW1/GW5 only.

**§8 `_check_pdf_health(pdf_path)`** — new helper for GW4 PDF health check.

**§8 `cap_angles(angles, requested_count=None)`** — new Policy 5 helper:
- Net rule: `output_count = min(requested_count or MAX_ANGLES, MAX_ANGLES)`.
- Returns `{angles, count, requested_count, capped, override}`.

**§8 `parse_requested_count(query)`** — new helper to extract "top N" count from query text.

**§8 `apply_premium(base_value, tier, incidents)`** — new Policy 3 helper:
- PR1: Tier 1 → eligible.
- PR2: `incidents > INCIDENT_PREMIUM_THRESHOLD (=5)` strictly → premium.
- PR3: premium computed via `secured_calculator(f"{base_value} * {PREMIUM_MULTIPLIER}")` only.
- Returns full result dict with `eligible`, `premium_applied`, `value_with_premium`, `calculator_expr`, etc.

**§8 `is_zero_match(tool_results)`** — new Policy 6 helper:
- Returns True iff all `evaluate_icp_tags` results have `qualified=False`, OR all `match_solicitation_angle` results have `tier == 4`.
- Empty `tool_results` returns False.

**§8 `policy6_fallback()`** — new helper:
- Returns `FALLBACK_MESSAGE` constant directly — no LLM call, generative path bypassed.

**§8 `_is_borderline(icp_result, profile_data=None)`** — new internal helper for trust-gate:
- Borderline iff `count == 3` AND no strong indicators.
- Strong indicators: any pixel flag True, or `scale_growth_stage`/`ad_spend_signals` in tags.

**§8 `route_prospect(icp_result, domain, profile_data=None, slack_poster=None)`** — new TG helper:
- Borderline → posts to Slack webhook (via `os.environ["SLACK_WEBHOOK_URL"]`); never leaks URL.
- Clear-cut → `action="auto_proceed"`.
- Disqualified → `action="disqualified"`.
- `slack_poster` parameter allows test mocking.

**§10 `answer_question`** — minimal wiring additions (loop contract/precedence unchanged):
- Added `_run_tool_results` list to accumulate `evaluate_icp_tags` and `match_solicitation_angle` results.
- Added `_requested_count = parse_requested_count(query)` for Policy 5 tracking.
- After each tool dispatch, appends result to `_run_tool_results` for relevant tools.
- After all tools in a turn, checks `is_zero_match(_run_tool_results)` — if True, returns `policy6_fallback()` immediately, bypassing the next LLM call (FB4 — generative path not invoked).
- At `end_turn` terminal: checks `is_zero_match` again; includes `requested_count` in the final gateway payload; passes final payload through `gateway_validate` for GW5 ceiling enforcement.
- Updated docstring: termination precedence now mentions Policy-6 zero-match and GW5.

### `tests/test_policies.py` — NEW file

Covers: POL1, POL2, PR1–PR4, CL1–CL4, TG1–TG2, FB1–FB4, GW1–GW5, plus an ENV4 regression class.

**Classes written:**
- `TestPOL1` (3 tests) — system prompt language for Policy 1 and 2.
- `TestPOL2` (4 tests) — ICP gate, qualification logic, is_zero_match integration.
- `TestPR1` (5 tests) — tier eligibility.
- `TestPR2` (5 tests) — incident boundary at 4/5/6 + constant values.
- `TestPR3` (4 tests) — secured_calculator path, SOP smoke (2150.0 * 1.15 = 2472.5), no raw eval.
- `TestPR4` (3 tests) — apply_premium integration.
- `TestCL1` (4 tests) — no-count → ≤3.
- `TestCL2` (3 tests) — requested > 3 → capped to 3 + override.
- `TestCL3` (3 tests) — requested ≤ 3 → exact count.
- `TestCL4` (5 tests) — gateway enforces ceiling; parse_requested_count.
- `TestTG1` (5 tests) — borderline → slack; clear-cut → auto-proceed; disqualified.
- `TestTG2` (3 tests) — URL not leaked; no URL configured; env-var name correct.
- `TestFB1` (4 tests) — byte-exact constant.
- `TestFB2` (6 tests) — is_zero_match logic.
- `TestFB3` (2 tests) — integration zero-match detection.
- `TestFB4` (3 tests) — no LLM call to compose fallback.
- `TestGW1` (5 tests) — null/empty rejection.
- `TestGW2` (8 tests) — format regexes domain/angle_key/tier.
- `TestGW3` (4 tests) — structured rejections, no exceptions.
- `TestGW4` (6 tests) — PDF health check.
- `TestGW5` (3 tests) — ceiling at gateway.
- `TestENV4PostStage5` (6 tests) — import-safety regression.

### `NOTES.md` — appended 3 decision entries
- Gateway format regexes (Stage-5 decision).
- Trust-Gate borderline indicator thresholds (Stage-5 decision).
- Slack webhook env-var name `SLACK_WEBHOOK_URL` (Stage-5 decision).
- Placeholders for the 3 items marked done.

### `PLAN.md` — status updated
- Stage 5 status changed from `🔄 In progress` to `🟡 Awaiting verification`.
- Current project state note updated to reflect executer handback.

---

## 2. DoD checklist — all DRAFTED ONLY (PM runs in .venv)

| Check | Status | How implemented |
|---|---|---|
| `POL1` | ⚠️ Drafted | `_SYSTEM_PROMPT_TEMPLATE` has explicit Policy 1 language ("MUST NOT assert"); cites `brands_catalog.csv` as sole source. TestPOL1 checks both. |
| `POL2` | ⚠️ Drafted | `_SYSTEM_PROMPT_TEMPLATE` has Policy 2 language; `evaluate_icp_tags` is the only gate; `is_zero_match` enforces no-bypass. TestPOL2 covers. |
| `PR1` | ⚠️ Drafted | `apply_premium` checks `tier == "Tier 1"`. TestPR1 5 tests. |
| `PR2` | ⚠️ Drafted | `incidents <= INCIDENT_PREMIUM_THRESHOLD` → no premium; `> 5` strictly → premium. Boundary-tested at 4/5/6 in TestPR2. |
| `PR3` | ⚠️ Drafted | `secured_calculator(f"{base_value} * {PREMIUM_MULTIPLIER}")` only; source-inspection test confirms. |
| `PR4` | ⚠️ Drafted | TestPR4 integration tests for all three eligibility/premium paths. |
| `CL1` | ⚠️ Drafted | `cap_angles(angles)` → ≤3; TestCL1. |
| `CL2` | ⚠️ Drafted | `cap_angles(angles, requested_count=5)` → 3, `override=True`; TestCL2. |
| `CL3` | ⚠️ Drafted | `cap_angles(angles, requested_count=2)` → exactly 2; TestCL3. |
| `CL4` | ⚠️ Drafted | `gateway_validate` calls `cap_angles` for payloads with `angles` key; TestCL4. |
| `TG1` | ⚠️ Drafted | `route_prospect` with borderline profile → `action="slack_gate"`; clear-cut → `"auto_proceed"`. TestTG1 5 tests. |
| `TG2` | ⚠️ Drafted | URL from `os.environ["SLACK_WEBHOOK_URL"]`; never in return value; `_SLACK_WEBHOOK_ENV_VAR` constant. TestTG2 3 tests. |
| `FB1` | ⚠️ Drafted | `FALLBACK_MESSAGE` constant checked byte-exact. TestFB1 4 tests. |
| `FB2` | ⚠️ Drafted | `is_zero_match` detects all-failed ICP or all-Tier-4 angle results. TestFB2 6 tests. |
| `FB3` | ⚠️ Drafted | Integration: is_zero_match on single-result lists. TestFB3 2 tests. |
| `FB4` | ⚠️ Drafted | `policy6_fallback()` source-inspected: no `_get_client`, no `client.messages`, returns constant. TestFB4 3 tests. |
| `GW1` | ⚠️ Drafted | Null/None and empty-field rejection in gateway_validate. TestGW1 5 tests. |
| `GW2` | ⚠️ Drafted | `_RE_DOMAIN`/`_RE_ANGLE_KEY`/`_RE_TIER_LABEL` applied to raw values. TestGW2 8 tests. |
| `GW3` | ⚠️ Drafted | All gateway paths return dicts, no raise. TestGW3 4 tests. |
| `GW4` | ⚠️ Drafted | `_check_pdf_health` checks `%PDF-`, non-zero length, `%%EOF`. TestGW4 6 tests. |
| `GW5` | ⚠️ Drafted | `gateway_validate` calls `cap_angles` when `angles` key present. TestGW5 3 tests. |

---

## 3. QA results — DRAFTED ONLY (not run; PM verifies in .venv)

All checks are drafted only. The sandbox cannot run Python/pytest. The PM is the sole verifier per ORCHESTRATION protocol. Expected command:

```
.venv/bin/python -m pytest tests/test_policies.py -v
```

Plus full regression:
```
.venv/bin/python -m pytest tests/ -v
```

Baseline: 277 passed, 1 skipped (S10) from Stage 4.

---

## 4. Decisions made

1. **Gateway treats `type` in `{final_output, cap_exhausted, internal}` as control payloads** — these are internal loop artifacts, not outbound PDFs. They pass through GW1 and GW5 only. Rationale: the gateway is designed for outbound payloads; internal signals should not be blocked by domain/angle_key format checks.

2. **Gateway checks RAW domain (not normalized)** — the gateway is the last line of defense; all callers should pre-normalize before calling it. If an unnormalized `https://` URL reaches the gateway, that is a caller error and should be rejected. Rationale: consistent with "gateway is the last defense" contract.

3. **Trust-gate borderline thresholds** (recorded in NOTES.md):
   - Strong indicator tags: `scale_growth_stage` and `ad_spend_signals` only.
   - Strong pixel: any of `tiktok_pixel`, `meta_pixel`, `gtm` = True.
   - Borderline = exactly 3 tags + ALL strong indicators absent.

4. **Slack webhook env-var** = `SLACK_WEBHOOK_URL` (recorded in NOTES.md).

5. **`is_zero_match` empty list returns False** — an empty result list means no ICP or angle tools have run yet, which is not a zero-match signal. Zero-match requires at least one result, all failing.

6. **Policy-6 check is done mid-loop (after each turn) and again at end_turn** — the mid-loop check avoids making a spurious next LLM call to compose an apology (FB4 requirement). The end_turn check provides a final safety net.

7. **`raw_result` variable initialized in both branches** of `if tool_fn is None / else` so that the Stage-5 tracking code at the bottom always finds it defined.

8. **`cap_angles` forwards-referenced from `gateway_validate`** — Python resolves this at call time (not definition time), so the function-definition ordering (gateway defined before cap_angles) is safe.

---

## 5. DECISION-NEEDED

None. All OQ-5 requirements proceed on Asaf's recorded default (caller-supplied base value). All other policy constants, tool signatures, JSON schemas, the loop contract, graded literals, and the FALLBACK_MESSAGE are unchanged.

---

## 6. Deviations

- **`gateway_validate` path dispatch**: internal payloads (`type` in `{final_output, cap_exhausted, internal}`) bypass domain/angle_key GW2 checks. This was an unspecified decision (not contradicting the brief) recorded in section 4 above. Rationale: these types are loop control signals, not outbound payloads — blocking them on domain format would break RS2/L4.

- **PDF health check (`%%EOF` vs `%EOF`)**: the gateway looks for `b"%%EOF"` (double percent) in the file. In actual PDF files, the marker is `%%EOF` — a literal string where the leading `%` starts a comment and the second `%` is literal. This is the correct check. The brief says "%%EOF marker" which matches.

---

## 7. Blockers / risks

- **ENV4 regression risk**: `route_prospect` calls `dual_log` (defined in §9); `gateway_validate` calls `cap_angles` (defined later in §8). Both are fine at runtime due to Python's function-body name resolution semantics, but the PM should re-verify `import main` from an empty dir is still clean.

- **`answer_question` loop change is minimal but behavioral**: the Policy-6 mid-loop check fires after dispatching ICP or angle tools and detecting all-failures. This should not affect passing tests from Stage 4 because those tests don't set up all-failing ICP/angle results. The PM should confirm the Stage-4 regression still passes (full 277 + 1 skip).

- **`FakeReasoningClient` in test_loop.py**: the Stage-4 tests mock the LLM client but don't mock ICP/angle results — so `_run_tool_results` will be empty in those runs, and `is_zero_match([])` returns False. No regression expected.

- **`_SYSTEM_PROMPT_TEMPLATE` has moved**: Stage 4 placed it in Section 10. The brief says to update "§3 `_SYSTEM_PROMPT_TEMPLATE`." Looking at the code, the template is defined in the Section 10 comment block as a module-level string constant immediately before `answer_question`. This location is import-safe and functionally correct; renaming the section is cosmetic only and was not done to avoid touching working Stage-4 code.

---

## 8. Next recommended action

PM: run `.venv/bin/python -m pytest tests/test_policies.py -v` and then the full regression `.venv/bin/python -m pytest tests/ -v` in `.venv`. If both pass, mark Stage 5 ✅ and advance to Stage 6 (Hybrid RAG / RRF angle engine, brief `briefs/stage-6.md`).
