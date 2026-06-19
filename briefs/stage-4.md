# Brief — Stage 4: Agentic loop, anti-loop cap & resiliency
Read first: CLAUDE.md → PLAN.md → QA_checklist.md → NOTES.md (esp. §6.5–§6.7, §7), then this brief.

Goal: Build the raw Anthropic Messages-API agentic loop in `answer_question` (`main.py` §10),
with the 15-call anti-loop cap + safe error state, call-logging metrics, the dual-write logger,
Claude resiliency (BadRequestError + refusal), and the gateway hook — all test-driven.

## Context you must know (settled — do not relitigate)
- **Stages 1–3 are ✅ PM-verified.** The 8 tools (§5), `TOOL_SCHEMAS` (§6), `TOOL_DISPATCH` (§7,
  with import-time three-way assert) all exist and pass. The log-line **constants** already exist in
  §3 (`LOG_CALLING_LLM`, `LOG_ENTER_TOOL`, `LOG_PARAM`, `LOG_EXIT_TOOL`, `LOG_FINAL`, `LOG_CAP_HIT`).
  `truncate_for_log` exists; `dual_log` is a print-only placeholder (§9); `answer_question` is a
  `NotImplementedError` placeholder (§10); `gateway_validate` is a `NotImplementedError` placeholder (§8).
- **Keep `answer_question(query, catalog_df=None, policies=None)` signature as-is.** Do NOT add a
  `client=` param. Tests inject the fake by monkeypatching `main._get_client` to return a
  `FakeReasoningClient`. (`_get_client` already lazy-builds the real Anthropic client from
  `os.environ["ANTHROPIC_API_KEY"]`.)

## Scope (do ONLY this stage)
Implement in `main.py`:
- **§10 `answer_question`** — the raw loop, exactly per CLAUDE.md §6.7:
  - `client = _get_client()`; loop calls `client.messages.create(model=REASONING_MODEL,
    max_tokens=<const>, tools=TOOL_SCHEMAS, messages=messages, thinking={"type":"adaptive"})`.
    Do NOT pass `temperature`/`top_p`/`budget_tokens` (they 400 on 4.7+).
  - **Check `stop_reason` BEFORE reading `response.content`** (a refusal may have empty content).
  - Iterate `response.content` for `tool_use` blocks; dispatch by `block.name` via `TOOL_DISPATCH`
    with `block.input` as kwargs. **Inject `catalog_df`** for `extract_and_score_pool` (NOTES Stage-3
    entry: `TOOL_DISPATCH[name](**{**block.input, "catalog_df": catalog_df})`).
  - Append the assistant turn (the full `response.content`), then a user turn of
    `{"type":"tool_result","tool_use_id":block.id,"content":<result-as-str/json>}` blocks — **one per
    `tool_use`, ids 1:1** — then loop.
  - **Termination precedence (exact):** (1) tool-call cap hit → safe error state + `LOG_CAP_HIT`,
    exit; (2) `stop_reason=="end_turn"` (no `tool_use`) → return the final text answer (log `LOG_FINAL`);
    (3) a terminal zero-match / validation-failure **signal** → return `FALLBACK_MESSAGE` (the full
    *policy trigger logic* is Stage 5 — here just support returning the constant when such a signal is
    raised; do not build the Policy-6 detection); (4) tool error (`{"error":...}` result) or
    `stop_reason=="refusal"` → feed it back as a tool_result / user turn, continue.
- **§6.5 cap** — a single counter caps dispatch at `TOOL_CALL_CAP (=15)`. On the **16th** attempted
  dispatch, STOP into the safe error state — do **not** make the 16th call. Emit `LOG_CAP_HIT`
  (`** TERMINATED: tool call cap reached **`). The cap is hard.
- **§9 logging/metrics** — make `dual_log(message, log_path="reactfirst_run.log")` write to **both**
  stdout and the log file (open/append at call time only — import-safety preserved). Track per-tool
  counts + total (≤15); write metrics to the log AND include them in the returned result structure
  (RS4). Use `truncate_for_log` for param values (first 50 chars).
- **§6.6 resiliency** — wrap `messages.create`: catch `anthropic.BadRequestError` (400) → log/surface
  the message back into `messages` so the next turn can adapt, continue (cap still counts the turn);
  `stop_reason=="refusal"` → treat as recoverable, surface, continue. Tool-level `{"error":...}` is
  data, not a crash (RS3). **No uncaught exceptions** anywhere — `answer_question` and `main()` return
  a clean structured failure instead (RS5).
- **§8 gateway hook (L4) — the ONE §8 line you may scaffold:** route every outbound payload (the
  `request_reactfirst_pdf` path + the final output) through `gateway_validate` as the single chokepoint.
  Replace the `gateway_validate` `NotImplementedError` with a **minimal permissive pass-through stub**
  (e.g. returns `{"valid": True, "payload": payload}`), clearly commented `# Stage 5 hardens this`. The
  loop must *call* it on outbound so L4's spy passes; Stage 5 fills in the real validation. Leave all
  other §8 policy helpers as placeholders.
- **`tests/test_loop.py`** — driven entirely by a `FakeReasoningClient` (build it here or in a
  conftest): `.messages.create(...)` returns scripted `Message`-shaped objects from a queue (content
  = list of blocks with `.type` in {`text`,`tool_use`} + `.id`/`.name`/`.input`/`.text`; `stop_reason`
  ∈ {`end_turn`,`tool_use`,`refusal`}); can raise `anthropic.BadRequestError` or return a refusal on a
  chosen turn. Monkeypatch `main._get_client` to return it. NO live calls.

## QA checks to PASS (run, not inspect — by the PM)
`L1` raw API shape (manual loop, reads `stop_reason` + `tool_use`); `L2` dispatch by name with input
as kwargs (+ `catalog_df` injection); `L3` `tool_use_id`→`tool_result` 1:1 plumbing (assistant turn
appended, every `tool_use` answered before next `create`); `L4` gateway called on every outbound
(spy); `L5` no-framework/no-tool-runner grep clean. `RS1` BadRequestError + refusal both handled
(stop_reason checked before content); `RS2` cap fires at **15**, no 16th dispatch, `LOG_CAP_HIT`
emitted (prove with a never-stops fake client); `RS3` tool error → continue; `RS4` per-tool + total
metrics (≤15) in log + result; `RS5` no uncaught exceptions. **Your sandbox cannot run Python** —
write the tests, mark *drafted only*; PM runs them in `.venv`.

## Constraints (from CLAUDE.md that bite this stage)
- Raw Anthropic Messages API only. **No** LangGraph/LangChain/`create_react_agent`/`AgentExecutor`/
  SDK tool-runner/`bind_tools` — not even imported (L5 grep-enforced).
- Import-safety holds (ENV4): the loop builds the client lazily inside `answer_question`; `dual_log`
  opens the file only when called; nothing new at import.
- No `eval`/`exec` (grep clean). Log lines stay the §3 constants (stable convention, not graded —
  only `FALLBACK_MESSAGE` is byte-exact).
- Do NOT touch §5 tool bodies, §6 schemas, §7 dispatch, §3/§4 config/loader, or `lead_store.py`/
  `rag_engine.py`. Do NOT build the real Policy-6/gateway logic (Stage 5) beyond the permissive
  pass-through stub described above.

## Inputs / files you may touch
Create/edit: `main.py` §10 (`answer_question`), §9 (`dual_log` + metrics), §8 (`gateway_validate`
pass-through stub ONLY), `main()` in §11 if needed for exception-safety; `tests/test_loop.py`
(+ optional `tests/conftest.py` for `FakeReasoningClient`).

## Do NOT
Advance past Stage 4. Change a tool signature / JSON schema / policy constant / a graded literal
(`FALLBACK_MESSAGE`). The loop contract is defined in §6.7 — implement it faithfully; if you believe
it must change, STOP and surface **DECISION-NEEDED**.

## Deliver
Write `handbacks/stage-4.md` in the standard format; separate *drafted only* from *written and
test-verified* (all drafted-only — PM verifies). List every `L*`/`RS*` check covered. Return it as
your final message.
