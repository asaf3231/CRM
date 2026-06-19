# PLAN.md — HW3 Tool-Calling Agent Project Plan

Project: **HW3 — Tool-Calling (Function-Calling) Agent**
Course: **LLM Software Engineering — Reichman University**
Maintained by: Asaf

> This file is the live execution tracker. `CLAUDE.md` defines the rules. `QA_checklist.md` defines how each stage is verified. `NOTES.md` records decisions, verified facts, blockers, and handbacks.

---

## How to use this file

- Work one stage at a time. Do not advance until the current stage's Definition of Done is satisfied.
- Read order for any session: `CLAUDE.md` → `PLAN.md` → `QA_checklist.md` → `NOTES.md`.
- **Every DoD item below references a check ID in `QA_checklist.md`** (e.g. `T1`, `C3`, `D2`). A stage is done only when every referenced check passes — and is *verified by running it*, not by inspection.
- Non-trivial `hw3.py` sections are drafted as labelled copy-pasteable blocks in chat for review, then landed. Small fixes can be edited directly. Always state *drafted only* vs *written and test-verified*.
- After each stage, append a handback to `NOTES.md`. Update the stage status only after PM/Asaf review.

Status values:

| Status | Meaning |
|---|---|
| ⬜ Not started | No work done yet |
| 🔄 In progress | Work started, not complete |
| 🟡 Awaiting verification | Code drafted/landed; QA checks not yet run/confirmed |
| ⚠️ Blocked | Cannot continue without a fix or decision |
| ✅ Complete | DoD satisfied, checks pass, reviewed |

---

## Stage tracker

| Stage | Name | DoD checks (QA_checklist.md) | Status |
|---:|---|---|---|
| 0 | Project setup & workflow files | meta (this file set) | ✅ Complete |
| 1 | Environment & gist verification | `E0`, `ENV1`, `ENV2`, `ENV3` | ✅ Complete |
| 2 | Tool layer (6 functions) | `T1`–`T6` | ✅ Complete |
| 3 | Tool JSON schemas | `S0`–`S9` | ✅ Complete |
| 4 | Agentic loop, dispatch, caps, logging | `L1`–`L5`, `C1`–`C5`, `D1`–`D4` | ✅ Complete |
| 5 | System prompt, user message, I/O | `P1`–`P4` | ✅ Complete |
| 6 | End-to-end sample query | `E1`–`E4` | ✅ Complete |
| 7 | Generalization & anti-leakage hardening | `G1`–`G6` | ✅ Complete |
| 8 | Optional MCP bonus | `M1`, `M2` | ✅ Complete |
| 9 | Submission packaging | `H1`–`H6` | ✅ Complete |

---

## Stage 0 — Project setup & workflow files

**Goal:** Create the four management files and prepare the workspace for test-driven implementation.

**Inputs:** `HW3.pdf`, `PM_Methodology_Prompt.md`, the `Reference/` benchmark files.

**Outputs:** `CLAUDE.md`, `PLAN.md`, `QA_checklist.md`, `NOTES.md`; the gist-layout decision locked (files at the repo root — see `NOTES.md` 2026-06-18). The gist fetch and skeleton `requirements.txt`/`partners.txt` are handled in Stage 1.

**Definition of Done:**
- [x] `CLAUDE.md` created (rules, environment, the 6-tool contract, anti-leakage, modular workflow).
- [x] `QA_checklist.md` created (stable check IDs, mapped to the rubric).
- [x] `PLAN.md` created (this file), every stage DoD references QA check IDs.
- [x] `NOTES.md` created and reviewed.
- [x] Gist-layout decision locked: files live at the repo root (dev-only), excluded at Stage 9 via an explicit allowlist (`H5`/`G1`). Gist fetch + skeleton `requirements.txt`/`partners.txt` belong to Stage 1.
- [x] Workflow is clear enough for a fresh agent to start Stage 1 cold (proven — Stages 1–2 executed cleanly from the four files).

**Status:** ✅ Complete (four files authored, reviewed, layout decision locked)
**Next action:** — (superseded; project now at Stage 3)

---

## Stage 1 — Environment & gist verification

**Goal:** Stand up a clean venv, confirm the sample files, and prove the Azure client is reachable — before writing agent code.

**Inputs:** the course gist (8 files), pinned deps from `CLAUDE.md` §1.

**Outputs:** the 8 gist files fetched to the **repo root**; working `.venv`; `requirements.txt` with the two pinned deps; confirmation logs; one verified-live client smoke response; env facts in `NOTES.md`.

**Definition of Done (QA: `E0`, `ENV1`, `ENV2`, `ENV3`):**
- [ ] `E0` — `python prepare_dataset.py` confirms all 8 gist files present.
- [ ] `ENV1` — `pip install -r requirements.txt` succeeds in a fresh venv.
- [ ] `ENV2` — `openai`, `duckduckgo_search` (via `from duckduckgo_search import DDGS`), and the stdlib modules import cleanly.
- [ ] `ENV3` — one minimal `create()` call returns a message (key/endpoint/deployment live).
- [x] Env facts (Python version, resolved dep versions, DDGS import path) logged in `NOTES.md`.

**Status:** ✅ Complete (2026-06-18 — all four checks run & confirmed; see NOTES.md Stage 1 handback)
**Findings carried forward:** `httpx==0.27.2` pinned (openai-1.51.0 vs httpx-0.28 `proxies` crash); PDF key has a `9`→`-` decode caveat (apply at Stage 5); gist DB schemas recorded in NOTES (dev-only — do not hardcode).
**Agent instruction:** Do not write tool/loop code yet. Fetch the gist files to the repo root (`git clone https://gist.github.com/MeirKaD/60c7568500154e9d02c65bdf3d652eb9.git`, then move the 8 files to the root). They stay at the root for dev and are excluded from the submission at Stage 9 via the allowlist.

---

## Stage 2 — Tool layer (the 6 functions)

**Goal:** Implement the 6 pure-Python tool functions to their exact contracts, test-first, each verified in isolation.

**Inputs:** `CLAUDE.md` §6; fixtures from `QA_checklist.md` §1.

**Outputs:** the 6 functions in `hw3.py` (Section 4); `tests/test_tools.py`.

**Definition of Done (QA: `T1`–`T6`):**
- [x] `T1` — calculator: arithmetic + `sqrt/log/abs/round/min/max`; **rejects** non-whitelisted input; returns `str`; no raw `eval`.
- [x] `T2` — extract_from_image: base64 + mime; returns the documented dict; robust parse; one guarded live check (T2.4 live PASS).
- [x] `T3` — build_sql_query: returns bare SQL; strips ` ```sql ` / ` ``` ` fences; no execution.
- [x] `T4` — execute_sql_query: read-only `?mode=ro`; `list[dict]`; errors → `[{"error":...}]`; never raises.
- [x] `T5` — web_search: ≤3 `{title,snippet,url}`; defined failure shape. ⚠️ T5.4 live SKIPPED (DDGS `202 Ratelimit` for this IP — env, not code; mapping proven offline).
- [x] `T6` — write_file: writes, makes parent dirs, returns `"Wrote N bytes to <file_name>"`.
- [x] Decisions logged in `NOTES.md`: `log` base, `web_search` failure shape, mime detection.

**Status:** ✅ Complete (PM-gated 2026-06-18 — PM re-ran the offline suite: `33 passed, 2 skipped`; `G1` grep clean; no framework imports; all 6 tool defs present with correct signatures). `T2.4` live PASS; `T5.4` live deferred to Stage 6 (DDGS IP ratelimit — env, not code). Sections 1–3 minimal/provisional; Section 4 complete. See NOTES Stage 2 handback.
**Agent instruction:** Mock the LLM/network for logic tests; run live checks sparingly. Each tool must pass standalone — the grader scores them in isolation.

---

## Stage 3 — Tool JSON schemas

**Goal:** Write the 6 schemas with descriptions sharp enough to steer tool choice (Part B).

**Inputs:** the finished functions; `CLAUDE.md` §7.

**Outputs:** `TOOL_SCHEMAS` and `TOOL_DISPATCH` in `hw3.py` (Sections 5–6); `tests/test_schemas.py`.

**Definition of Done (QA: `S0`–`S9`):**
- [x] `S0` — exactly 6 schemas; names == function names == dispatch keys (PM re-verified: three-way match `True`, dispatch resolves to matching callables).
- [x] `S1`–`S7` — each schema well-formed; all props `"string"`-typed; `required` arrays byte-exact per the table.
- [x] `S8` — descriptions state *when to use*; SQL-pair rule + "does NOT run" + copy-schema-from-input.json present; web-search scoped to resources; no empty/vague text.
- [x] `S9` — one gated live call: `create(..., tools=TOOL_SCHEMAS, tool_choice="auto")` accepted (no 400).

**Status:** ✅ Complete (PM-gated 2026-06-18 — re-ran full offline suite `56 passed, 3 skipped`; independent `S0` three-way match + `required`/types + `S8` content all pass; `G1`/framework clean). Single-source `TOOLS` pairing with an import-time `name == fn.__name__` assert prevents drift.
**Agent instruction:** Keep schemas adjacent to functions so they cannot drift.

---

## Stage 4 — Agentic loop, dispatch, caps, logging

**Goal:** Build the raw-API loop with exact dispatch, cap accounting, and logging literals.

**Inputs:** Stages 2–3; `CLAUDE.md` §8, §9, §10; `FakeLLMClient`.

**Outputs:** `run_agent(...)`, dual-write logger, truncation helper in `hw3.py` (Sections 7, 9); `tests/test_loop.py`.

**Definition of Done (QA: `L1`–`L5`, `C1`–`C5`, `D1`–`D4`):**
- [x] `L1`–`L5` — raw `create(..., tools, tool_choice="auto")`; dispatch by name; `tool_call_id` plumbing; message ordering; no-framework grep clean.
- [x] `C1`–`C5` — LLM cap and tool cap both fire with the exact `TERMINATED` lines; name-based `+1 LLM` increment for the two LLM-backed tools (per the corrected `C3` rule); termination precedence; clean `final response is =` stop.
- [x] `D1`–`D4` — literal strings byte-exact; written to both stdout and file; 50-char truncation; `.log` path/stem/subdir correct.

**Status:** ✅ Complete (PM-gated 2026-06-18 — re-ran full suite `76 passed, 3 skipped`, `test_loop.py` `20 passed`; independently grepped all 7 log literals byte-exact in `hw3.py`; framework + `G1` clean; zero live calls). Accepted deviation: `Entering` logged before `json.loads` (balances Entering/Exiting on malformed JSON; identical for well-formed graded input). See NOTES Stage 4 handback + PM gate.
**Agent instruction:** Drive every loop test from `FakeLLMClient` — no live calls. Prove the cap with a "never stops" client.

---

## Stage 5 — System prompt, user message, I/O

**Goal:** Wire `input.json` parsing, prompt/user-message construction, and output-path resolution.

**Inputs:** Stage 4 loop; `CLAUDE.md` §3, §7; the sample `input.json`.

**Outputs:** `SYSTEM_PROMPT`, `build_user_message(...)`, `main()` + input parsing in `hw3.py` (Sections 8, 10).

**Definition of Done (QA: `P1`–`P4`):**
- [x] `P1` — system prompt sets role, the 6 tools, per-sub-problem tool preference, and the "write output then stop" rule.
- [x] `P2` — initial user message includes both the query text and the resource list.
- [x] `P3` — parses `query_name` + `resources[]`; resolves `query_name` relative to cwd incl. subdir; clean error on malformed `input.json`.
- [x] `P4` — output filename/shape taken from the query text at runtime, produced via `write_file`.

**Status:** ✅ Complete (PM-gated 2026-06-18 — re-ran full suite `92 passed, 3 skipped`, `test_io.py` 16; independently confirmed `SYSTEM_PROMPT` names all 6 tools + pairing + stop rule ("...DO NOT call any tool"), `build_user_message` carries query+file_name+description, and `P4`/`G1` greps clean; zero live calls). Header scaffolded (ID `209252154` in; Name/Email TODO).
**Agent instruction:** The system prompt is graded (Part B). Make tool-preference guidance explicit and concise.

---

## Stage 6 — End-to-end sample query

**Goal:** Run the full agent on the gist sample and match the shipped validator values.

**Inputs:** Stages 1–5; the gist sample files already at the repo root (run `python hw3.py` in place — the root already mirrors the grader's cwd).

**Outputs:** `receipt_analysis.log`, `receipt_analysis_result.json`; an E2E note in `NOTES.md`.

**Definition of Done (QA: `E1`–`E4`):**
- [x] `E1` — both artifacts produced; JSON parses.
- [x] `E2` — values match the validator within tolerance (`Blue Moon Cafe` / `87.45` / `1240.30` / `7.05` / `Haifa`) — **validator returns True**.
- [x] `E3` — run stays within 20/20 with headroom (**11 tool / 16 LLM**).
- [x] `E4` — structurally covered (no natural error this run; Stage 4 `C4` recovery tests cover it).

**Status:** ✅ Complete (2026-06-18 — first live run passed on attempt 1; validator True; `tool_calls=11`, `llm_calls=16`; G1/framework clean. See NOTES Stage 6 handback.)
**Agent instruction:** Passing here must come from generic runtime reasoning, never from hardcoding sample values (re-checked in Stage 7).

---

## Stage 7 — Generalization & anti-leakage hardening

**Goal:** Prove the agent generalizes to the hidden bank, not just the sample.

**Inputs:** the working agent; a second synthetic query authored for the test.

**Outputs:** hardened `hw3.py`; `tests/test_generalization.py`; anti-leakage audit note in `NOTES.md`.

**Definition of Done (QA: `G1`–`G6`):**
- [x] `G1` — anti-leakage grep clean: no sample merchant/total/city/filename/schema literals. (`receipt.png`/`orders.db` kept as illustrative description examples — decided & PM-concurred.)
- [x] `G2` — OS-agnostic paths; nothing hardcoded absolute.
- [x] `G3` — fenced SQL still executes end-to-end.
- [x] `G4` — broken SQL recovers in the loop.
- [x] `G5` — simulated `BadRequestError` caught and surfaced; loop continues; cap respected.
- [x] `G6` — a different synthetic query (DB-only → `summary.txt`) produces the right output with no code change.

**Status:** ✅ Complete (PM-gated 2026-06-18 — G5 diff read line-by-line (only sanctioned change); generalization suite `12 passed, 1 skipped` + full suite `104 passed, 4 skipped` re-run by PM; G6 ground truth re-derived by direct SQL → `summary.txt` exact match (revenue 20600.0/count 3), output name ≠ query stem, 5 LLM/3 tool, no code change; G1/framework greps clean. See NOTES "PM gate: Stage 7 ✅".)
**Agent instruction:** This is the highest-leverage correctness stage. Treat any hardcoded sample value found in `G1` as a blocker.

---

## Stage 8 — Optional MCP bonus

**Goal:** Standalone `hw3_mcp.py` + `mcp_setup.md` demonstrating the MCP pattern.

**Inputs:** Bright Data free tier; Node 18+; `mcp` SDK.

**Outputs:** `hw3_mcp.py`, `mcp_setup.md`; `mcp==1.27.1` added to `requirements.txt` (only if attempted).

**Definition of Done (QA: `M1`, `M2`):**
- [x] `M1` — script connects, lists tools, invokes ≥1, prints the result; not wired into the agent.
- [x] `M2` — setup doc ≤ half a page: signup, `BRIGHTDATA_API_TOKEN`, exact verify command.

**Status:** ✅ Complete (PM-gated 2026-06-18 — PM re-ran the live M1 independently: connected to the Bright Data server, listed 5 tools, `search_engine("Reichman University")` returned a real organic-results JSON array; `mcp_setup.md` ≤ half page; `requirements.txt` has `mcp==1.27.1` with httpx/openai compat re-confirmed (`import mcp` ok, httpx 0.27.2, openai constructs); token absent from every shipped/source file; `hw3.py` byte-unchanged (suite 104/4, framework clean). See NOTES "PM gate: Stage 8 ✅".)
**Agent instruction:** Do not start unless Asaf approves — the required tasks come first, and the bonus caps the grade at 100. Standalone only: never modify or import `hw3.py`; never block Stage 9.

---

## Stage 9 — Submission packaging

**Goal:** Produce the clean, fresh-venv-verified submission ZIP.

**Inputs:** the completed `hw3.py` and supporting files; partner identity details.

**Outputs:** `requirements.txt`, `partners.txt`, header block in `hw3.py`, the sample `.log` + `_result.json`, the ZIP.

**Definition of Done (QA: `H1`–`H6`):**
- [x] `H1` — every non-stdlib import pinned: `openai==1.51.0`, `duckduckgo-search==6.2.10`, `httpx==0.27.2`, `mcp==1.27.1` (hw3.py: openai + duckduckgo_search; hw3_mcp.py: mcp).
- [x] `H2` — fresh-venv `pip install -r requirements.txt` exit 0; `import hw3` constructs the client (httpx compat holds); `python hw3.py` runs and prints a clean error with no `input.json` (no traceback). Full sample run already validated at Stage 6 / G6 on the current code.
- [x] `H3` — `partners.txt` = `Asaf Ramati, 209252154`.
- [x] `H4` — header block carries Name (Asaf Ramati) / ID (209252154) / Email (asaf.ramati@post.runi.ac.il).
- [x] `H5` — ZIP built from the explicit 7-file allowlist; listing = only those 7 (no gist/tests/Reference/HW3.pdf/working-`.md`/db/png).
- [x] `H6` — ZIP named `hw3_209252154.zip` (solo).

**Status:** ✅ Complete (PM-built & verified 2026-06-18 — `hw3_209252154.zip` = 7 files; fresh-venv unzip→install→`import hw3`→`python hw3.py` all clean; deps resolve to openai 1.51.0 / httpx 0.27.2 / mcp 1.27.1; G1/framework greps clean; offline suite 104/4. See NOTES "Stage 9 — submission packaged".)
**Agent instruction:** Build the ZIP from an **explicit allowlist** of required files only (never zip the directory); verify by unzipping into a fresh dir and running `python hw3.py` once.

---

## Standard stage handback format

At the end of every stage, the agent reports (also appended to `NOTES.md`):

1. **What changed** — `hw3.py` sections drafted vs written; tests added; files touched.
2. **DoD checklist** — each referenced QA ID ✅ / ⚠️, with *drafted only* vs *written and test-verified* separated.
3. **QA results** — which check IDs were actually run and their pass/fail.
4. **Decisions made** — anything not explicitly specified.
5. **Deviations** — anything different from this plan, with reason.
6. **Blockers / risks** — quota pressure, flaky web search, framework temptation, ambiguous query text.
7. **Next recommended action** — one concrete next step.

Do not mark a stage complete if its QA checks were only drafted but not run.

---

## Current project state

- **Current stage:** ✅ **PROJECT COMPLETE** — all stages 0–9 done & verified. Submission `hw3_209252154.zip` built and fresh-venv-verified.
- **Completed:** Stages 0–8 (Stage 6 live E2E validator True 11/16; Stage 7 `G1`–`G6` incl. G5 content-filter recovery + G6 exact match; Stage 8 MCP bonus M1/M2 live-verified — all PM-gated); **Stage 9 (packaging `H1`–`H6`) PM-completed 2026-06-18** — `hw3_209252154.zip` = 7 allowlist files; fresh-venv unzip→install→`import hw3`→`python hw3.py` all clean (openai 1.51.0 / httpx 0.27.2 / mcp 1.27.1 resolve); header H4 + `partners.txt` H3 set. See NOTES "Stage 9 — submission packaged".
- **In progress:** None.
- **Resolved decisions:** Solo — Asaf Ramati, 209252154, asaf.ramati@post.runi.ac.il. MCP bonus attempted & shipped. ZIP `hw3_209252154.zip`.
- **Carry-overs / notes:** Shipped `receipt_analysis.log`/`_result.json` are the Stage-6 validated artifacts (current code's sample behavior unchanged — G5 is a no-op on the clean path; header/banner edits are comments). The `# === Section N ===` banner comments were trimmed from `hw3.py` (cosmetic; functionally verified intact). Bright Data token is in the chat transcript — Asaf may rotate it. `T5.4` web_search live happy-path never exercised (no query needs it).
- **Next action:** Asaf submits `hw3_209252154.zip` to Moodle. (Optional: rotate the Bright Data token; restore hw3.py section banners if desired.)
