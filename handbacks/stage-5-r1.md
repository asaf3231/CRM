# Handback — Stage 5-r1

## 1. What changed

Two targeted corrections only; no governance helpers, schemas, tool implementations, or policy constants were touched.

**Files touched:**
- `/Users/asaframati/Documents/CRM/main.py` — Correction 1 applied
- `/Users/asaframati/Documents/CRM/tests/test_loop.py` — Correction 2 applied

### Correction 1 — Removed premature mid-loop zero-match short-circuit (main.py)

Deleted the 10-line block (original lines 2529–2538) that read:

```python
# Stage 5: Policy-6 zero-match detection AFTER all tools in this turn.
# Checked here so we can exit BEFORE the next LLM call (FB2).
# The generative path is BYPASSED — we do not call the model to apologize.
if is_zero_match(_run_tool_results):
    dual_log("[policy-6] Zero-match detected. Returning FALLBACK_MESSAGE.", log_path)
    metrics_line = (...)
    dual_log(metrics_line, log_path)
    return policy6_fallback()
```

Replaced with a clarifying comment and kept the `messages.append({"role": "user", "content": tool_result_blocks})` line that was previously being skipped on the short-circuit path:

```python
# Append one user turn with all tool_result blocks 1:1 (L3).
# Policy-6 zero-match is decided ONLY at the end_turn terminal (~line 2401),
# not mid-loop — a single failed ICP result must not end a multi-turn run.
messages.append({"role": "user", "content": tool_result_blocks})
```

The correct end_turn zero-match check (original ~line 2401, now same location) is fully preserved and untouched. `is_zero_match` now only fires at the `end_turn` terminal, satisfying CLAUDE.md §6.7 termination precedence.

### Correction 2 — Deleted obsolete TestGatewayValidateStub class (tests/test_loop.py)

Deleted the entire class and its section comment header (original lines 949–972, 24 lines total):

```
# ===========================================================================
# gateway_validate stub tests (L4)
# ===========================================================================

class TestGatewayValidateStub:
    test_stub_returns_valid_true
    test_stub_passes_payload_through
    test_stub_does_not_raise
```

These three tests asserted the old Stage-4 permissive pass-through stub behavior (`{"valid": True, "payload": payload}`). The gateway was hardened in Stage 5; those assertions are wrong by design. Real gateway behavior is fully covered by GW1–GW5 in `tests/test_policies.py` (96/96 green). The file now ends cleanly at line 947 (the `TestTruncateForLog` class).

## 2. DoD checklist

| QA ID | Status | How verified |
|---|---|---|
| FB2 | drafted-only | end_turn zero-match check preserved at ~line 2401; returns `policy6_fallback()` (the constant), discarding model prose. No dedicated LLM apology call. |
| FB4 | drafted-only | Same end_turn check — generative path bypassed; `policy6_fallback()` returns `FALLBACK_MESSAGE` byte-exactly. |
| L3 | drafted-only | `messages.append({"role": "user", "content": tool_result_blocks})` now always executes after the tool dispatch for-loop — the post-turn short-circuit that was skipping it is removed. The `test_multiple_tool_use_blocks_answered_1to1` test's turn-1 `evaluate_icp_tags` fake returning `qualified=False` will no longer trigger early exit. |
| RS2 | drafted-only | Cap check (TOOL_CALL_CAP) unchanged; still fires before each dispatch attempt. |
| RS5 | drafted-only | No new code paths that raise; the outer `except Exception` in the loop still catches anything. |
| GW1–GW5 | not touched | `tests/test_policies.py` 96/96 — these are the real gateway tests; no changes to the gateway or its tests. |

All items are **drafted only** — the PM sandbox runs the full regression. The executer cannot run Python.

## 3. QA results

Cannot run Python in this sandbox. The PM must execute:

```
cd /Users/asaframati/Documents/CRM
.venv/bin/python -m pytest tests/test_loop.py tests/test_policies.py -v 2>&1 | tail -30
```

Expected outcome: `test_policies.py` stays 96/96; `test_loop.py` previously had 2 failures — `test_multiple_tool_use_blocks_answered_1to1` (L3, fixed by Correction 1) and the 3 `TestGatewayValidateStub` tests (removed by Correction 2) — so the result should go from 2 failed / 371 passed to 0 failed / 369 passed (3 obsolete tests removed, 1 previously-failing test now passes, net: -2 tests total, 0 failures).

Also recommended:
```
.venv/bin/python -c "import main, lead_store, rag_engine"   # ENV4
grep -rn "eval(\|exec(" /Users/asaframati/Documents/CRM/main.py   # G1
grep -rn "TestGatewayValidateStub\|test_stub_returns_valid\|test_stub_passes_payload" /Users/asaframati/Documents/CRM/tests/test_loop.py   # should be empty
```

## 4. Decisions made

- Deleted `test_stub_does_not_raise` along with the other two stub tests: it was inside the same `TestGatewayValidateStub` class and asserted stub behavior (`gateway_validate(None)` must not raise). The hardened gateway raises `ValueError` on `None` input (GW1), so this test would fail too. Deleting the whole class is correct per the brief.
- Kept the clarifying comment at the `messages.append` call site to make the policy-6 placement decision explicit for future readers.

## 5. DECISION-NEEDED

None. Both corrections are narrowly scoped, no contract changes, no schema changes, no policy constant changes, no graded literal changes.

## 6. Deviations

None from the brief. Exactly the two specified changes were made and nothing else.

## 7. Blockers / risks

None. The changes are minimal and surgical. The only risk is that another test in `test_loop.py` was implicitly relying on the mid-loop short-circuit behavior — the PM's full regression will surface that immediately if so.

## 8. Next recommended action

PM runs the full regression:
```
.venv/bin/python -m pytest tests/ -v 2>&1 | tail -40
```
If result is 0 failures (369 passed, 1 skipped), mark Stage 5 complete and advance to Stage 6 (Hybrid RAG / RRF angle engine, `briefs/stage-6.md`).
