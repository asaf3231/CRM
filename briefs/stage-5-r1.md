# Brief — Stage 5 (retry r1): Governance — corrections required
Read first: CLAUDE.md → PLAN.md → QA_checklist.md → NOTES.md → briefs/stage-5.md (the original), then this.

The Stage-5 implementation is **95% correct and PM-verified green** on the governance suite
(`tests/test_policies.py` = 96/96) — gateway GW1–GW5, Policy 3 (`apply_premium` boundary + via
`secured_calculator`), Policy 5 `cap_angles`, Policy 6 `is_zero_match`/`policy6_fallback`, trust-gate,
POL1/POL2 prompt — are all correct. Do **NOT** redo them. Only the two items below need fixing; the
full `tests/` regression then goes from **2 failed / 371 passed** to fully green.

## Corrections required

### Correction 1 — remove the premature MID-LOOP zero-match short-circuit (real bug)
`answer_question` (§10) has **two** `is_zero_match(_run_tool_results)` checks:
- the **end_turn** check (~line 2401) — **CORRECT, keep it.** When the model concludes (`end_turn`)
  and a zero-match was detected during the run, it returns `policy6_fallback()` and bypasses the
  model's prose. This satisfies FB2/FB4 (no dedicated apology call).
- the **post-turn** check (~lines 2529–2538, the comment "Policy-6 zero-match detection AFTER all
  tools in this turn") — **REMOVE THIS ONE.** It is over-eager: it fires after *any* turn that
  contains a single `evaluate_icp_tags` result with `qualified=False` (because `is_zero_match` of one
  failed ICP result is `True`), terminating the run **before** the agent can evaluate more candidates
  in later turns — and it `return`s **before** the `tool_result` user turn is appended (~line 2541),
  so it also skips the L3 1:1 plumbing on that path.

Fix: delete the post-turn check block (the `if is_zero_match(_run_tool_results): ... return
policy6_fallback()` at ~2529–2538) so the loop always appends the `tool_result` user turn (~line 2541)
and continues; Policy-6 zero-match is decided **only** at the `end_turn` terminal (and the cap path
remains the safe error state). This matches CLAUDE.md §6.7 precedence (zero-match → fallback at the
terminal) and does **not** change the loop contract.

Rationale: a single mid-discovery `qualified=False` must not end a multi-turn run. FB2/FB4 are already
satisfied by the end_turn check (the fallback is returned as the constant, the model is never asked to
compose an apology). This is the bug that broke `tests/test_loop.py::TestL3Plumbing::
test_multiple_tool_use_blocks_answered_1to1` (its turn-1 `evaluate_icp_tags` fake returns
`qualified=False`, which the post-turn check treated as a terminal zero-match).

### Correction 2 — delete the obsolete Stage-4 gateway-STUB tests
`tests/test_loop.py::TestGatewayValidateStub` (`test_stub_returns_valid_true` +
`test_stub_passes_payload_through`) asserts the **old permissive pass-through stub** behavior
(`{"valid":True,"payload":payload}`). The gateway is now **hardened** (Stage 5), so those assertions
are wrong by design. **Delete the entire `TestGatewayValidateStub` class** — the real gateway behavior
is fully covered by GW1–GW5 in `tests/test_policies.py`. Do not weaken the hardened gateway to satisfy
a stub test.

## Must stay true after the fix (PM will verify all)
- FB2: zero-match at the **end_turn** terminal still returns **only** `FALLBACK_MESSAGE` (byte-exact).
- FB4: the generative path is still bypassed — no dedicated LLM call to compose the fallback (the
  end_turn check returns the constant, discarding any model prose). Keep/adjust the FB4 test so it
  asserts this against the end_turn path.
- L3: `tests/test_loop.py::TestL3Plumbing::test_multiple_tool_use_blocks_answered_1to1` passes — the
  loop appends the assistant turn then a user turn with 2 `tool_result` blocks (ids 1:1) and proceeds
  to the 2nd `messages.create`.
- RS2/RS5 and all of `test_loop.py` stay green; `test_policies.py` stays 96/96.
- ENV4 holds; no `eval`/`exec`; no framework; no catalog values hardcoded; no secret leaked.

## Do NOT
Change any tool signature / JSON schema / policy constant / graded literal / the loop contract beyond
removing the premature short-circuit as specified. Do NOT touch §5 tools, §6/§7 schemas, `lead_store.py`,
`rag_engine.py`, or the governance helpers that already pass. If removing the post-turn check seems to
break a real FB requirement, STOP and surface **DECISION-NEEDED** with specifics.

## Deliver
Update `handbacks/stage-5.md` (or write `handbacks/stage-5-r1.md`) noting exactly the two changes; mark
*drafted only* (PM runs the full regression). Return it as your final message.
