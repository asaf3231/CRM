# Handback — Stage 10

## 1. What changed

**Files touched:**

- `/Users/asaframati/Documents/CRM/main.py` — written and test-verified:
  - Section 3 (Configuration): added `ICP_ANCHOR_COUNT = 5`.
  - Section 5 (Tools): added `_parse_icp_json()` helper and `build_icp_document()` (Tool 9), placed after `secured_calculator` before Section 6.
  - Section 6 (Schemas): added Schema 9 (`build_icp_document`) to `TOOL_SCHEMAS` (Anthropic-shaped, `seed` string required, description >= 50 chars stating when to use + anchor-cap constraint).
  - Section 7 (Dispatch): added `"build_icp_document": build_icp_document` to `TOOL_DISPATCH`; bumped both `assert len(...) == 8` to `== 9`; updated the comment from `== 8` to `== 9`.
  - `_SYSTEM_PROMPT_TEMPLATE`: changed `"the 8 tools available to you"` → `"the tools available to you"` (count-agnostic).

- `/Users/asaframati/Documents/CRM/tests/test_icp_builder.py` — new file, 40 tests, written and test-verified.

- `/Users/asaframati/Documents/CRM/tests/test_schemas.py` — updated:
  - `EXPECTED_TOOL_NAMES` list: added `"build_icp_document"`.
  - `TestS0.test_exactly_8_schemas`: changed `== 8` → `== 9` in assertion and docstring.
  - `TestS0.test_import_time_assert_passed`: changed both `== 8` lines → `== 9`.

- `/Users/asaframati/Documents/CRM/NOTES.md` — Stage 10 handback appended.

**Not touched:** `evaluate_icp_tags`, `_ICP_TAGS`, `ICP_TAG_THRESHOLD`, the RRF engine, gateway, any graded literal, any other tool.

## 2. DoD checklist

| Check | Status | How verified |
|---|---|---|
| `ICPB1` structured shape | ✅ written + test-verified | `TestICPB1Shape` (11 tests): exact 7-key set, correct types for all fields, `json.dumps()` round-trip |
| `ICPB2` anchors capped at `ICP_ANCHOR_COUNT=5` | ✅ written + test-verified | `TestICPB2AnchorCap` (4 tests): LLM returns 8 → only 5; 4+domain supplement → still ≤5; 0+10 domains → ≤5 |
| `ICPB3` import-safety re-proven (`ENV4`) | ✅ run | `python -c "import main, lead_store, rag_engine"` from empty tmp dir → exit 0; `_anthropic_client is None` |
| `ICPB4` anti-leakage (`G2`) | ✅ written + test-verified | `TestICPB4AntiLeakage` (2 tests): source inspection confirms no catalog domain literals; `_ICP_TAGS` read at runtime |
| `ICPB5` Policy 2 unchanged | ✅ written + test-verified | `TestICPB5Policy2Unchanged` (4 tests): `_ICP_TAGS` keys identical before/after call; `ICP_TAG_THRESHOLD` still 3; `evaluate_icp_tags` still qualifies at ≥3 correctly |
| `ICPB6` generalizes to 2nd seed | ✅ written + test-verified | `TestICPB6Generalization` (5 tests): seed 1 (footwear) and seed 2 (pet food) both produce correct shape; deterministic under mock; `icp_tags` from vocabulary |

## 3. QA results

Command: `.venv/bin/python -m pytest tests/ --tb=short -q`

Output (tail):
```
511 passed, 1 skipped, 245 warnings in 30.15s
```

New ICP builder tests isolated:
```
.venv/bin/python -m pytest tests/test_icp_builder.py -v
40 passed in 0.40s
```

ENV4 check:
```
python -c "import main, lead_store, rag_engine; print('ENV4 OK')"
ENV4 OK
_anthropic_client: None
ICP_ANCHOR_COUNT: 5
build_icp_document in TOOL_DISPATCH: True
len(TOOL_SCHEMAS): 9
```

G1 grep (no raw eval/exec):
```
grep -En "eval\(|exec\(" main.py | grep -v "ast.parse|#"
(no output — clean)
```

The 1 skipped is `S10` (live API smoke, gated on `ANTHROPIC_API_KEY`) — same as baseline, not a new skip.

## 4. Decisions made

1. `_parse_icp_json` mirrors `_parse_query_list` with 3 strategies (bare JSON → fenced block → first `{...}` blob → empty dict). Malformed LLM output returns an empty dict, and the tool assembles a valid shape with fallback defaults — never crashes.
2. `build_icp_document` uses `ANALYZER_MODEL` (Sonnet 4.6) for ICP synthesis (the brief says it's "the reasoning step"). `_vector_a_search` provides grounded research and is fully monkeypatched in tests.
3. `icp_tags` values in the prompt are drawn from `list(_ICP_TAGS.keys())` at runtime — no hardcoded list in the function or prompt (ICPB4).
4. Anchor supplement logic: after capping LLM anchors at 5, if fewer than 5 remain, grounded-research domains are appended as stub anchors (name=domain, domain=domain, why=generic sentence). The cap is checked at both stages.
5. `test_schemas.py` was updated as part of the sanctioned 8→9 bump — the three failing assertions were previously hardcoded to `== 8`.

## 5. DECISION-NEEDED

None. All changes are within the sanctioned scope of the brief:
- Tool count 8→9 was explicitly sanctioned in NOTES.md Phase 2 decision (2026-06-19).
- System-prompt count-agnostic wording was explicitly prescribed in the brief.
- No tool signature, JSON schema (other than the new schema 9), policy constant, loop contract, or graded literal was changed.

## 6. Deviations

None from the brief. The brief said `ICP_ANCHOR_COUNT` was "already added to Configuration §3" — it was not present, so it was added as part of this stage. This is not a deviation; it's completing the brief's stated requirement.

## 7. Blockers / risks

- Live path (grounded `_vector_a_search` + `_get_client()` ANALYZER_MODEL call) gated on `ANTHROPIC_API_KEY` (OQ-7) — offline tests pass fully; live smoke remains SKIPPED as before.
- No new external dependencies added.
- Baseline suite was 471 passed (post-premium-removal). After Stage 10: 511 passed (+40 new tests, +3 updated schema tests that changed from failing back to passing = net +40 new tests in `test_icp_builder.py`).

## 8. Next recommended action

Dispatch Stage 11 (L5a mini-CRM lead workspace — new module `crm_store.py`, checks `CRM1`–`CRM8`).
