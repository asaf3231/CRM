# CLAUDE.md — Project Standards & Conventions

Project: **HW3 — Tool-Calling (Function-Calling) Agent**
Course: **LLM Software Engineering — Reichman University**
Deliverable: a single, modular, production-grade script `hw3.py`
Maintained by: Asaf

> Read this file at the start of every Claude Code session before writing or editing any code. This file defines the permanent rules for the project. Execution status belongs in `PLAN.md`; the test blueprint belongs in `QA_checklist.md`; decisions and verified facts belong in `NOTES.md`.

---

## 0. Working methodology

This project uses a lightweight four-file PM workflow:

```text
CLAUDE.md        = permanent rules and conventions  (this file)
PLAN.md          = current stage tracker and Definition of Done
QA_checklist.md  = the Test-Driven-Development blueprint (every DoD points here)
NOTES.md         = decisions, verified facts, blockers, and handbacks
```

At the start of every Claude Code session:

1. Read `CLAUDE.md`.
2. Read `PLAN.md`.
3. Read `QA_checklist.md`.
4. Read `NOTES.md`.
5. Identify the current stage.
6. Work only on that stage.
7. Stop at the stage boundary and report back.

Do not silently continue into the next stage. Do not change tool signatures, schemas, the loop contract, or the logging strings without surfacing the decision.

If `PLAN.md`, `QA_checklist.md`, or `NOTES.md` is missing, do **not** proceed with implementation. Draft the missing file in chat first and wait for Asaf to approve or create it.

---

## 1. Environment

The grader runs in a clean environment. Your code must run there with no manual fixups.

- **Python:** 3.10 or higher.
- **OS-agnostic:** must run on Windows / macOS / Linux. No hardcoded absolute paths. Build every path with `os.path.join` / `pathlib` and resolve everything relative to the current working directory.
- **Entry point:** `python hw3.py` with `input.json` already present in the cwd.

Create and activate a virtual environment before doing anything:

```bash
# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate

# Windows PowerShell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

You should see `(.venv)` in the prompt. Never `pip install` outside the venv.

### Pinned dependencies (non-negotiable)

`requirements.txt` must pin **at least** these, and the grader must be able to run `pip install -r requirements.txt && python hw3.py` in a fresh venv:

```text
openai==1.51.0
duckduckgo-search==6.2.10
```

- `sqlite3`, `json`, `base64`, `os`, `sys`, `ast`, `math`, `importlib.util` are **standard library** — do not list them.
- Add `pillow==10.4.0` **only** if you actually import PIL. The reference receipt can be read as raw bytes; prefer that and avoid the dependency.
- Add `mcp==1.27.1` **only** if you implement the optional bonus (`hw3_mcp.py`).
- Every other non-stdlib import must be added to `requirements.txt` with a pinned `==` version.

Import note: `duckduckgo-search==6.2.10` is imported as `from duckduckgo_search import DDGS` (underscore, not the newer `ddgs` package). Verify the import resolves before writing `web_search`.

### LLM client setup (Azure via the OpenAI SDK)

Use the class Azure deployment exactly as specified in `HW3.pdf` §"LLM setup". Use the standard `OpenAI` client (not `AzureOpenAI`) pointed at the Azure v1 base URL:

```python
from openai import OpenAI

deployment_name = "gpt-4.1-mini"
endpoint = "https://softwareengineeringusingai.openai.azure.com/openai/v1/"
GPT41_API_KEY = "<class key from HW3.pdf §LLM setup>"

client = OpenAI(api_key=GPT41_API_KEY, base_url=endpoint)
```

- Use this **same** `client` and `deployment_name` for the main loop **and** for the tool-internal calls inside `extract_from_image` and `build_sql_query`. The grader provides no separate keys.
- The key is a shared class credential. It belongs in `hw3.py` (the assignment requires it hardcoded) — but do not paste it into any public location, and `hw3.py` is the only place it ships.

---

## 2. Source-of-truth files

Expected project layout. **Layout decision (locked 2026-06-18):** the course gist files live at the **repo root** — not in a `_gist/` subdir — so that dev runs mirror the grader's working directory exactly (the grader places its own `input.json` + query + validator + resources beside `hw3.py` and runs `python hw3.py`). They are dev-only and must never ship; exclusion is enforced at Stage 9 by an explicit allowlist plus checks `H5` and `G1`.

```text
hw3_209252154/                       # dev working dir == the grader's cwd model
│  # --- shipped: the submission allowlist ---
├── hw3.py                           # THE deliverable (single modular script)   [SHIP]
├── requirements.txt                 # pinned deps                                [SHIP]
├── partners.txt                     # <Full Name>, <ID> per line                 [SHIP]
├── receipt_analysis.log             # sample-run artifact                        [SHIP]
├── receipt_analysis_result.json     # sample-run artifact                        [SHIP]
├── hw3_mcp.py                       # optional bonus (not wired into the agent)  [SHIP if bonus]
├── mcp_setup.md                     # optional bonus (half a page max)           [SHIP if bonus]
│  # --- dev-only: NEVER shipped ---
├── CLAUDE.md                        # permanent project rules (this file)
├── PLAN.md                          # stage tracker and active plan
├── QA_checklist.md                  # TDD blueprint; every stage DoD references it
├── NOTES.md                         # decisions, verified facts, handbacks
├── HW3.pdf                          # assignment instructions
├── PM_Methodology_Prompt.md         # PM operating methodology
├── Reference/                       # quality benchmark from a prior project
├── tests/                           # dev-only TDD suite (not graded, not shipped)
│  # --- course gist files: at the repo root to mirror grader cwd; DEV-ONLY, NEVER shipped ---
├── input.json
├── receipt_analysis.txt
├── receipt_analysis_validate.py
├── receipt.png
├── orders.db
├── customers.db
├── prepare_dataset.py
└── README.md
```

Source-of-truth rules:

- `CLAUDE.md` defines how work must be done.
- `PLAN.md` defines what the current stage is.
- `QA_checklist.md` defines how each stage is verified.
- `NOTES.md` records why decisions were made.
- `hw3.py` is the only graded code deliverable. It must be self-contained.
- The gist files (`input.json`, `receipt_analysis.txt`, `*_validate.py`, `receipt.png`, `orders.db`, `customers.db`, `prepare_dataset.py`, `README.md`) live at the **repo root** so dev runs match the grader's cwd. They are development aids only and **must never be shipped**. The submission ZIP is built at Stage 9 from an **explicit allowlist** of required files (never by zipping the directory); exclusion is enforced by checks `H5` (no gist files shipped) and `G1` (anti-leakage grep). The grader provides its own copies at grading time.
- Do not duplicate long plans or decisions across files. Put each thing in the right place.

---

## 3. Assignment objective

Write one program, `hw3.py`, that solves multi-step help-desk queries with an **agentic tool-calling loop** built directly on the raw OpenAI API.

The loop sends the user query plus the tool list to the LLM. The LLM decides which tool to call and with what arguments. The program dispatches to the local Python implementation, appends the result as a `role: "tool"` message, and calls the LLM again. The loop ends when the LLM returns a message with no `tool_calls`, or when a cap is hit.

At runtime the agent must:

1. Read `input.json` → `query_name` (may include a subdirectory) and `resources[]` (each with `file_name` + free-form `description`).
2. Read the query text from `query_name` (resolved relative to cwd).
3. Construct the initial user message containing **both** the query text and the resource list.
4. Run the loop, choosing tools by reasoning over file extension + description (there is no explicit `type` field).
5. Write `<query_name_stem>.log` **always**, plus whatever output file(s) the query text asks for, via the `write_file` tool.

Grading is heavily weighted toward: correct loop primitives, sharp tool schemas, exact logging strings, exact cap accounting, and per-tool correctness under isolated unit testing. High correctness on a single query does not compensate for a vague schema or a wrong log literal.

---

## 4. Non-negotiable quality rules

### 4.1 No agent framework

You MUST use the raw OpenAI tool-calling API directly:
`client.chat.completions.create(..., tools=TOOL_SCHEMAS, tool_choice="auto")`, parse `response.choices[0].message.tool_calls`, dispatch by name, append `{"role": "tool", "tool_call_id": ...}` messages back.

You MUST NOT use LangGraph, LangChain agents, `create_react_agent`, `AgentExecutor`, `bind_tools`, or any other abstraction that hides the loop. **Detection of any of these anywhere in `hw3.py` zeros the entire "no framework" rubric row regardless of correctness elsewhere.** Do not even import them.

### 4.2 Anti-leakage / no hardcoding (the generalization rule)

The grader runs a hidden test bank with **different** queries, resources, schemas, column names, and output filenames. The sample (`receipt_analysis`, "Blue Moon Cafe", the `orders`/`customers` schemas, `receipt_analysis_result.json`) is a development aid only.

Therefore `hw3.py` must NOT contain:

- Any literal sample value: merchant names, totals, city names, the `orders`/`customers` column names, table names, or any expected answer.
- Any hardcoded output filename. The output path is read from the **query text** at runtime and passed to `write_file`.
- Any hardcoded resource filename, db path, or image path. All of these come from `input.json` / the query.
- Any branch like `if query == "receipt_analysis"`.

The agent must reason from `input.json` and the query text at runtime. Anything else "leaks" sample knowledge into the code and fails on the hidden bank. This is the single most important correctness rule after §4.1.

### 4.3 Exact cap accounting

Enforce two separate counters, both capped at 20 per query:

- `llm_calls` — every `client.chat.completions.create(...)` in the main loop = **1**. Additionally, each dispatch of `extract_from_image` or `build_sql_query` = **+1** (they invoke the LLM internally).
- `tool_calls` — every dispatched tool = **1** (calculator, execute_sql_query, web_search, write_file, extract_from_image, build_sql_query all count as 1 tool call each).

Worked example from the spec: 8 main-loop LLM calls + 1 `extract_from_image` + 2 `build_sql_query` ⇒ `llm_calls = 11`, `tool_calls = 3`. Caps are **hard**: hitting one is a failure (0 correctness for that query) even if output files were already written.

### 4.4 Exact logging literals

The grader greps for literal strings. Casing and whitespace matter. Emit, to **both stdout and the log file**:

```text
Calling LLM for next tool to invoke
** Entering tool <tool_name> **
Parameter <p> = <first 50 chars of value, then "..." if the value was longer>
** Exiting tool <tool_name> **
```

After the loop, exactly one of:

```text
final response is = <assistant final message>
** TERMINATED: LLM call cap reached **
** TERMINATED: tool call cap reached **
```

See §9 for the precise truncation and path rules.

### 4.5 Safety: no raw eval, read-only SQL, defensive SQL stripping

- `calculator` MUST NOT use raw `eval()`/`exec()`. Implement via `ast.parse(expr, mode="eval")` + a whitelist node walker (or a vetted safe-eval lib). Reject names, attributes, subscripts, and any non-whitelisted call.
- `execute_sql_query` MUST open the database **read-only** via `sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)`. Never open it writable. On `sqlite3.Error`, return `[{"error": "<message>"}]` — do not raise.
- `build_sql_query` MUST strip leading/trailing markdown code fences (` ```sql ` / ` ``` `) from the LLM output before returning, even though the prompt forbids them. The model will sometimes ignore the instruction; defensive stripping is required.
- Do not `eval`/`exec` anything else the LLM returns.

### 4.6 Fail loudly in tools, but never crash the loop

- An **uncaught Python exception in `hw3.py` zeros every functional rubric row.** The loop must be exception-safe end to end.
- Tool-level failures are data, not crashes: a tool error becomes `{"error": "..."}` (or `[{"error": "..."}]`), is appended back as a `role: "tool"` message, and the LLM decides whether to retry. **Do NOT force-terminate the loop on a tool error** — recovery is explicitly tested.
- Azure may raise `BadRequestError` (content filter). Catch it, surface the error message back to the LLM on a later turn so it can change approach, and continue the loop. The cap still applies — content-filter errors do not get unlimited retries.
- Use assertions/explicit errors only where they protect correctness without crashing a graded run (e.g. validating `input.json` shape at startup with a clear message).

---

## 5. Modular Script-Authoring Workflow

The deliverable is a **single file** (`hw3.py`) but it must read like a well-factored module. Organize it into clearly delineated sections, top to bottom, one responsibility each:

```text
1. Header comment block      # Name / ID / Email per partner (required, Part E)
2. Imports                   # stdlib first, then openai, then duckduckgo_search
3. Configuration             # client, deployment_name, caps, constants (no magic numbers inline)
4. Tool implementations      # the 6 pure functions, one per logical block
5. Tool schemas              # TOOL_SCHEMAS list (Part B)
6. Dispatch table            # TOOL_DISPATCH = {name: fn}
7. Logging helpers           # dual-write logger, parameter-truncation helper
8. Prompt construction       # SYSTEM_PROMPT, build_user_message(query_text, resources)
9. Agentic loop              # run_agent(...) with both counters and termination precedence
10. I/O + main()             # read input.json, resolve log path, run, guard with try/except
```

Authoring rules:

- **TDD first.** For each section, the matching `QA_checklist.md` test is written/known before the implementation, and must pass before the section is considered done.
- **One responsibility per section.** No business logic inside the logging helper, no logging inside the tools beyond what the loop emits.
- **No magic values inline.** `LLM_CAP`, `TOOL_CAP`, the deployment name, and the truncation length live in the Configuration section as named constants.
- **Default authoring mode:** for a non-trivial change, draft the section(s) in chat as a labelled, copy-pasteable block (e.g. `hw3.py — Section 4.2 build_sql_query`) so Asaf can review before it lands. Direct edits to `hw3.py` are fine once a section's design is approved or for small fixes. State clearly whether a block was **drafted only** or **written and test-verified**.
- Provide sections in the order they appear in the file. Do not assume code ran until tests confirm it (see `QA_checklist.md`).

---

## 6. The 6 tools — exact contract

Exactly **6 tools**, no more (adding tools earns no credit and dilutes the schemas). Each needs a Python function *and* a JSON schema. LLM-call accounting in **bold**.

| # | Signature | Returns | Accounting |
|---|---|---|---|
| 6.1 | `calculator(expression: str) -> str` | numeric result as a string | 1 tool, **0 LLM** |
| 6.2 | `extract_from_image(image_path: str) -> dict` | `{"merchant","date","total","items":[{"name","price"}]}` | 1 tool, **+1 LLM** |
| 6.3 | `build_sql_query(natural_language: str, schema_description: str) -> str` | bare SQL string (fences stripped) | 1 tool, **+1 LLM** |
| 6.4 | `execute_sql_query(sql: str, db_path: str) -> list[dict]` | rows as list of dicts keyed by column; `[{"error": "..."}]` on `sqlite3.Error` | 1 tool, **0 LLM** |
| 6.5 | `web_search(query: str) -> list[dict]` | top 3 `{"title","snippet","url"}` | 1 tool, **0 LLM** |
| 6.6 | `write_file(file_content: str, file_name: str) -> str` | `"Wrote N bytes to <file_name>"`; creates parent dirs | 1 tool, **0 LLM** |

Behavioral specifics that the unit tests in `QA_checklist.md` pin down:

- **6.1 calculator** — must support `+ - * / ** ( )` plus `sqrt, log, abs, round, min, max`, and int/float literals. `abs/round/min/max` are builtins; `sqrt/log` come from `math`. Decide and record `log`'s base in `NOTES.md` (natural log vs `log(x, base)`). Reject everything not whitelisted.
- **6.2 extract_from_image** — read bytes from `image_path`, base64-encode, detect mime from extension (`.png`/`.jpg`/`.jpeg`), send a vision message to `gpt-4.1-mini` asking for strict JSON of the documented shape, parse and return the dict. Increment the LLM counter when it runs.
- **6.3 build_sql_query** — prompt: *"Given this schema description and this natural-language request, return ONLY the SQL query (no markdown fences, no explanation, no commentary)."* Strip fences defensively. Returns SQL only; never executes it.
- **6.4 execute_sql_query** — read-only URI connection; rows → `list[dict]`; `sqlite3.Error` → `[{"error": str(e)}]`; never raises.
- **6.5 web_search** — `DDGS().text(query, max_results=3)` → list of `{"title","snippet","url"}`. Map the library's field names to exactly these keys.
- **6.6 write_file** — write text, create parent dirs (`os.makedirs(dirname, exist_ok=True)`), return the exact confirmation string where `N = len(file_content.encode("utf-8"))`.

---

## 7. Tool schema rules (Part B)

Each schema is `{"type": "function", "function": {"name", "description", "parameters"}}` with a JSON-Schema `parameters` object listing `properties`, `type`s, and `required`.

- Names must exactly match the function names.
- Every parameter needs a `type` and a `description`; mark the right ones `required`.
- **Descriptions steer the model** and are graded. Each description must say *when to use the tool*, not just what it does. Vague text like "does math" loses points. State the pairing rule for the SQL tools (`build_sql_query` "Always pair with `execute_sql_query` — this tool does NOT run the query"), and tell `web_search` to be used only for facts not present in the provided resources.
- Keep `TOOL_SCHEMAS` adjacent to the functions so they cannot drift apart.

---

## 8. Agentic loop rules

- Maintain `messages` starting with the system message and the constructed user message.
- Each iteration logs `Calling LLM for next tool to invoke`, then calls `create(...)`, increments `llm_calls`, and appends `msg.model_dump(exclude_none=True)` (the assistant message, including any `tool_calls`) back into `messages`.
- If `msg.tool_calls` is empty → log `final response is = <content>` and break (success iff requested output files exist).
- Otherwise iterate `msg.tool_calls`. For each: check the tool cap first; parse `json.loads(tc.function.arguments)`; log entry + parameters + exit; dispatch via `TOOL_DISPATCH[name](**args)`; increment `tool_calls`; if the tool is `extract_from_image` or `build_sql_query`, also `llm_calls += 1`; append `{"role": "tool", "tool_call_id": tc.id, "content": json.dumps(result, default=str)}`.
- **Message-plumbing invariant:** every `tool_call` in an assistant message must get exactly one matching `role: "tool"` reply (by `tool_call_id`) before the next `create(...)`. The model can request multiple tool calls in one turn; handle all of them.
- **Termination precedence (evaluate in this order):** (1) cap hit → log the matching `TERMINATED` line and exit (failure); (2) no `tool_calls` → `final response is = ...` and exit; (3) tool returned an error → append and let the LLM decide (do not terminate); (4) uncaught exception → fatal, avoid it.

---

## 9. Logging rules

- A single logging helper writes each line to **both** `sys.stdout` and the open log file handle (flush both). Missing either side costs Part D points.
- **Log path:** `<query_name_stem>.log` = `os.path.splitext(query_name)[0] + ".log"`, which preserves any subdirectory (`query1/receipt_analysis.txt → query1/receipt_analysis.log`). Create the log's parent directory if needed.
- **Parameter truncation:** for each tool argument, log `Parameter <name> = <value>` where the value is stringified and, if longer than 50 characters, cut to the first 50 chars followed by `...`. Values ≤ 50 chars are logged whole, with no trailing `...`.
- Log the literal strings from §4.4 exactly. Do not log intermediate `msg.content`; the grader does not look for it (printing it for debugging is fine).

---

## 10. Stable names and conventions

Use consistent identifiers so the loop and tests stay readable:

```python
LLM_CAP = 20
TOOL_CAP = 20
PARAM_LOG_LIMIT = 50
DEPLOYMENT_NAME = "gpt-4.1-mini"

TOOL_SCHEMAS = [...]                 # the 6 JSON schemas
TOOL_DISPATCH = {"calculator": calculator, ...}   # name -> callable
SYSTEM_PROMPT = "..."                # graded under Part B
```

- Tool function names == schema names == dispatch keys. A mismatch breaks dispatch correctness (Part A).
- Avoid vague names (`tmp`, `res2`, `do_thing`). Helper names should say what they do (`build_user_message`, `truncate_for_log`, `dual_log`, `resolve_log_path`).

---

## 11. Testing requirements

This project is test-driven. `QA_checklist.md` is the authoritative blueprint; `hw3.py` is built section-by-section against it.

- Every tool has an **isolated** unit test (the grader scores tools in isolation — §2 of `QA_checklist.md`).
- LLM-calling tools are tested with a **mocked** client for logic, plus one guarded live smoke test (to conserve the shared quota).
- The loop, cap accounting, and logging are tested with a **fake client** that scripts tool-call sequences — including a "never stops" client to prove the cap fires (§5 of `QA_checklist.md`).
- Tests live in `tests/` and are dev-only; they are not shipped and not graded, but no stage is "done" until its referenced QA checks pass.

---

## 12. Completion checklist

Before marking any stage complete:

- [ ] The section(s) for this stage run without errors.
- [ ] The QA_checklist checks referenced by this stage's DoD all pass.
- [ ] No forbidden framework imported (§4.1).
- [ ] No hardcoded sample value or output filename (§4.2).
- [ ] Counters and caps behave per the worked example (§4.3).
- [ ] Log literals are byte-exact and written to both sinks (§4.4, §9).
- [ ] `calculator` rejects non-whitelisted input; SQL is read-only; fences stripped (§4.5).
- [ ] No uncaught exception path; tool errors recover (§4.6).
- [ ] `NOTES.md` updated with decisions, verified facts, and a handback.
- [ ] `PLAN.md` status ready for PM review/update.

Before final submission:

- [ ] Fresh-venv `pip install -r requirements.txt && python hw3.py` succeeds.
- [ ] Sample run produced `receipt_analysis.log` + `receipt_analysis_result.json` matching the shipped validator values.
- [ ] `requirements.txt` pins every non-stdlib import.
- [ ] `partners.txt` present: `<Full Name>, <ID>` per line.
- [ ] `hw3.py` header block has each partner's Name / ID / Email.
- [ ] No gist file is in the ZIP.
- [ ] ZIP named `hw3_<ID>.zip` (solo) or `hw3_<ID1>_<ID2>.zip` (pair).

---

## 13. Claude Code handback format

When a stage is complete, report back with:

1. **What changed** — sections of `hw3.py` drafted vs written, new tests, files touched.
2. **DoD checklist** — each item ✅ or ⚠️; separate *drafted only* from *written and test-verified*.
3. **QA results** — which `QA_checklist.md` IDs were run and their pass/fail.
4. **Decisions made** — anything not explicitly specified (e.g. `log` base, `web_search` failure shape).
5. **Deviations** — anything done differently from `PLAN.md`, with reason.
6. **Blockers or risks** — quota pressure, flaky web search, ambiguous query text, framework temptation.
7. **Next recommended action** — one concrete next step only.

Do not silently advance to the next stage.
