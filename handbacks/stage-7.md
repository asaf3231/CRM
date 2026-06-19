# Handback — Stage 7

## 1. What changed

### main.py — two targeted additions (no tool signatures/schemas/policies/loop contract changed)

**Addition A — `_run_tool_results` tracking expanded (§10, ~line 2558)**

Added tracking of `request_reactfirst_pdf` results alongside the existing `evaluate_icp_tags` and `match_solicitation_angle` tracking. Each tracked entry now carries `{"tool_name", "result", "input"}` (the `input` dict carries `target_domain`, `validated_angle_key`, `calculated_risk_score` — used by `write_qualified_leads`).

**Addition B — `write_qualified_leads` helper + call site (§11)**

New function `write_qualified_leads(run_tool_results, output_dir=None) -> Optional[str]`:
- Collects all `request_reactfirst_pdf` entries where `result["ok"] is True`.
- Enriches each lead with `tier` from the positionally-matched `match_solicitation_angle` result.
- Caps at `MAX_ANGLES=3` via `cap_angles()` (Policy 5 — same chokepoint as gateway).
- Writes `qualified_leads.json` to `os.getcwd()` (or `output_dir` when supplied) as:
  ```json
  {"qualified_leads": [...], "count": N, "capped": bool}
  ```
- Returns the absolute path, or `None` if no ok=True PDFs in the run.
- Import-safe: opens files only when called, never at import time.
- OS-agnostic: paths built with `pathlib.Path` / `os.path`.

Call site in `answer_question`'s `end_turn` success terminal (after gateway validation, before metrics log line), wrapped in a broad `try/except` so artifact write failure never crashes the pipeline (RS5 preserved).

**No-match behavior (E4 documented decision):** `write_qualified_leads` is called only from the success path. The Policy-6 path returns `FALLBACK_MESSAGE` before the call site — so `qualified_leads.json` is NOT written on no-match runs.

### tests/test_e2e.py — new file (Stage 7 E2E suite)

Covers E1–E4 plus `TestWriteQualifiedLeads` unit tests:

- `FakeReasoningClient` (same pattern as `test_loop.py`) scripts the reasoning model's multi-turn tool sequence with zero network.
- `tmp_cwd` fixture: `monkeypatch.chdir(tmp_path)` so all artifacts land in a throwaway temp directory.
- `catalog_df` fixture: 2-row 9-column DataFrame (AlphaBrand/BetaBrand, no real catalog values, no hardcoded production domains).
- Per-tool monkeypatches via `monkeypatch.setitem(main.TOOL_DISPATCH, ...)` for network-dependent tools.
- `_make_valid_pdf_bytes()`: GW4-valid PDF stub (`%PDF-1.4\n...%%EOF`).
- `_icp_profile_4_tags()`: deterministic profile triggering 5 ICP tags (ecommerce_dtc, paid_social_advertising, scale_growth_stage, ad_spend_signals, brand_marketing_team) → `qualified=True`, clear-cut.
- `_icp_profile_2_tags()`: profile triggering 1 ICP tag → `qualified=False`.

**Classes:**
- `TestE1HappyPath` — 9-turn scripted run (generate → fanout → extract → analyze → evaluate → match → calculator → pdf → end_turn); checks qualified_leads.json, log, ≤3 angles, ≥1 GW4-valid PDF.
- `TestE2WithinCap` — same happy-path shape, verifies total LLM calls ≤ 15 with headroom; `[metrics]` and `total_calls=` present in log.
- `TestE3VectorCRecovery` — patches `main._vector_a_search` and `main._vector_b_search` to return 0 domains; spy on `main._vector_c_search`; asserts `vector_c_calls > 0` AND pipeline completes.
- `TestE4NoMatchFallback.test_e4_all_icp_fail_yields_fallback` — ICP profile < 3 tags → all `evaluate_icp_tags` return `qualified=False` → result is exactly `FALLBACK_MESSAGE`; `[policy-6]` in log; no extra LLM call; no `qualified_leads.json`.
- `TestE4NoMatchFallback.test_e4_all_tier4_angles_yields_fallback` — ICP passes but all `match_solicitation_angle` return Tier 4 → result is exactly `FALLBACK_MESSAGE`; no `qualified_leads.json`.
- `TestWriteQualifiedLeads` — unit tests for the helper directly: None on empty input, None on all-fail PDFs, single lead written correctly, >3 leads capped to MAX_ANGLES=3 with `capped=True`, import-safety.

### Files touched
- `/Users/asaframati/Documents/CRM/main.py` — two minimal additions (§10 tracking + §11 helper + call site)
- `/Users/asaframati/Documents/CRM/tests/test_e2e.py` — new file (Stage 7 E2E suite)
- `/Users/asaframati/Documents/CRM/NOTES.md` — Stage 7 decision appended

## 2. DoD checklist

| QA ID | Status | How verified |
|---|---|---|
| `E1` | ⚠️ Drafted only | test_e2e.py::TestE1HappyPath::test_e1_artifacts_produced — asserts qualified_leads.json + reactfirst_run.log + ≥1 GW4-valid PDF + ≤3 angles. PM must run in .venv. |
| `E2` | ⚠️ Drafted only | test_e2e.py::TestE2WithinCap::test_e2_call_count_within_cap — asserts total_llm_calls ≤ TOOL_CALL_CAP with headroom; [metrics]/total_calls= in log. PM must run in .venv. |
| `E3` | ⚠️ Drafted only | test_e2e.py::TestE3VectorCRecovery::test_e3_vector_c_fires_when_ab_under_threshold — patches A and B to 0 domains; spy asserts vector_c_calls > 0; pipeline completes. PM must run in .venv. |
| `E4` | ⚠️ Drafted only | test_e2e.py::TestE4NoMatchFallback (2 tests) — ICP-fail and Tier-4-angle seeds both yield exactly FALLBACK_MESSAGE; no qualified_leads.json; no extra LLM call (FB4). PM must run in .venv. |

All checks are **drafted only** — this sandbox cannot run Python/pytest. PM verifies in `.venv`.

## 3. QA results

No checks run. PM is the sole verifier per ORCHESTRATION §"Reviewer independence".

**Expected command (PM):**
```
.venv/bin/python -m pytest tests/test_e2e.py -v   # stage checks
.venv/bin/python -m pytest tests/ -v              # full regression (must stay 428+/1 skip baseline)
```

## 4. Decisions made

1. **qualified_leads.json shape:** `{"qualified_leads": [...], "count": int, "capped": bool}` where each lead is `{"domain", "angle_key", "tier", "pdf_path"}`. Documented in NOTES.md.
2. **No-match behavior:** `qualified_leads.json` is NOT written on no-match runs. The Policy-6 early-return path executes before the write call site. Documented in NOTES.md and brief.
3. **Tier enrichment strategy:** positional matching (i-th successful PDF corresponds to i-th `match_solicitation_angle` result in run order). Simple and deterministic for the typical sequential pipeline flow.
4. **`_run_tool_results` expansion:** `request_reactfirst_pdf` entries now carry `{"tool_name", "result", "input"}` (input dict included) so `write_qualified_leads` can access `target_domain` and `validated_angle_key` without re-parsing the result.
5. **ICP profile fixtures:** generic language only — no real brand names, domains, or catalog values. Verified against `_ICP_TAGS` patterns to confirm 4-tag/1-tag counts.
6. **Catalog fixture:** 2 synthetic rows (AlphaBrand/BetaBrand) with fictional `.com` domains not in the real `brands_catalog.csv`. CAT5/G2 clean.
7. **Tool patching strategy:** `monkeypatch.setitem(main.TOOL_DISPATCH, ...)` for compute-heavy / network-dependent tools; `monkeypatch.setattr(main, "_vector_a_search", ...)` for vector sub-functions in E3 (so the real `execute_3way_fanout` runs but with mocked internals, exercising the real recovery logic).

## 5. DECISION-NEEDED

None. No tool signatures, schemas, policy constants, loop contract, or graded literals were changed or require a decision.

## 6. Deviations

- **`extract_and_score_pool` and `secured_calculator` NOT patched** in any E2E test — they run real code. `extract_and_score_pool` is pure (no network) and uses the injected catalog_df fixture; `secured_calculator` is the AST walker (no network). This is intentional: running more real code in the E2E path increases confidence.
- **`evaluate_icp_tags` NOT patched** — runs real code with crafted profile strings. This is intentional and ensures the ICP gate is exercised end-to-end.

## 7. Blockers / risks

1. **Cannot run Python in this sandbox** — all checks are drafted only. PM must verify.
2. **`monkeypatch.setitem` on `main.TOOL_DISPATCH`** — if the dispatch dict is somehow not mutable per-test (e.g. some pytest isolation issue), tests may fail. The pattern was used successfully in `test_loop.py` with `main.TOOL_DISPATCH["secured_calculator"] = fake_fn`, but that test used direct dict assignment with manual restore. If `monkeypatch.setitem` behaves differently, PM may need to switch to the manual pattern.
3. **E3 Vector C spy**: the `execute_3way_fanout` function runs the real ThreadPoolExecutor A∥B. With mocked A/B both returning 0 domains synchronously, there's no timing issue, but if the thread executor timeout behavior differs under test conditions, C might not fire as expected. Low risk (the mock functions return immediately).
4. **`_check_pdf_health` on mock PDF path**: the mock PDF is written to `os.getcwd()/assets/` which is the `tmp_cwd`. If `request_reactfirst_pdf` mock is called but `os.getcwd()` returns a different directory (e.g. if `monkeypatch.chdir` is applied after the call), the gateway check could fail. The test ordering (`tmp_cwd` fixture applies chdir before the test body) should prevent this.
5. **Full regression must stay at 428+/1 baseline** — the tracking expansion in the loop and the `write_qualified_leads` call in the success terminal are both wrapped in try/except. Existing tests that use `answer_question` and never call `request_reactfirst_pdf` will have no `request_reactfirst_pdf` entries in `_run_tool_results` → `write_qualified_leads` returns None immediately. No regression expected.

## 8. Next recommended action

PM runs the Stage 7 verification:
```
cd /Users/asaframati/Documents/CRM
.venv/bin/python -m pytest tests/test_e2e.py -v
.venv/bin/python -m pytest tests/ -v
```
Verify: `test_e2e.py` all pass; full regression stays at 428+ passed, 1 skipped; ENV4 holds post-edit (`python -c "import main, lead_store, rag_engine"` in an empty temp dir exits 0). If all green → Stage 7 ✅ → Stage 8 (generalization & anti-leakage hardening).
