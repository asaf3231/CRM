# NOTES.md — HW3 Tool-Calling Agent Running Project Log

Project: **HW3 — Tool-Calling (Function-Calling) Agent**
Course: **LLM Software Engineering — Reichman University**
Maintained by: Asaf

> This file is the project memory. `CLAUDE.md` defines the rules. `PLAN.md` tracks stages. `QA_checklist.md` is the test blueprint. `NOTES.md` records verified facts, decisions, blockers, deviations, and stage handbacks.

---

## How to use this file

- Append-oriented. Do not delete past decisions unless Asaf asks.
- Record **why** a choice was made, not only what was done.
- Every non-obvious decision (e.g. `log` base, web-search failure shape, prompt wording that fixed a loop) goes here.
- Copy a number here only after it was actually computed/observed (a real log line, a test result), not from memory.
- If a decision changes, add a new **Correction** entry rather than rewriting history.
- Keep entries short and decision-oriented. Long explanations belong in code comments or the section design.

Recommended entry format:

```markdown
## [YYYY-MM-DD] — [Topic]

**Type:** Decision / Verified fact / Blocker / Deviation / Handback / Correction
**Entry:** What happened or what was decided.
**Reason:** Why this choice / why it matters.
**Source:** Assignment / test output / web research / Asaf decision / agent handback.
**Impact:** What it affects downstream.
```

---

## Locked workflow decisions

### 2026-06-17 — Four-file lightweight methodology

**Type:** Decision
**Entry:** The project uses a four-file workflow: `CLAUDE.md` (rules), `PLAN.md` (stage tracker), `QA_checklist.md` (TDD blueprint), `NOTES.md` (log). Read order: CLAUDE → PLAN → QA → NOTES.
**Reason:** Extends the prior three-file PM method with an explicit test blueprint, because this assignment is graded largely on exact, testable behaviors (tool contracts, log literals, cap accounting).
**Impact:** Every `PLAN.md` stage DoD references `QA_checklist.md` check IDs; a stage is done only when those checks pass.

### 2026-06-17 — Test-driven, section-modular single file

**Type:** Decision
**Entry:** `hw3.py` is one file but organized into 10 labelled sections (`CLAUDE.md` §5). Each section is written test-first against its QA checks.
**Reason:** The grader requires a single `python hw3.py` entry point, but the code must stay reviewable and each tool must pass in isolation.
**Impact:** Non-trivial sections are drafted as labelled blocks in chat for review; handbacks separate *drafted only* from *written and test-verified*.

### 2026-06-17 — Gist files are dev-only and quarantined

**Type:** Decision
**Entry:** The 8 gist files live under `_gist/` and must never enter the submission ZIP. `tests/` and `Reference/` are likewise excluded.
**Reason:** The grader provides its own input/query/validator/resources; shipping the sample files is explicitly forbidden and risks accidental hardcoding.
**Impact:** Stage 9 (`H5`) audits the ZIP for any gist artifact.

### 2026-06-18 — Gist layout: files at repo root (supersedes the `_gist/` quarantine)

**Type:** Correction
**Entry:** The 8 gist files live at the **repo root**, not under `_gist/`. They remain strictly dev-only and must never ship.
**Reason:** `prepare_dataset.py` and `hw3.py` both read from the current working directory, which is exactly how the grader runs (it places `input.json` + query + validator + resources beside `hw3.py` and runs `python hw3.py`). Keeping the gist files at the root makes every dev run a faithful copy of the grader's environment; the `_gist/` copy-into-scratch approach added friction for no benefit.
**Source:** Asaf decision, 2026-06-18 (Option a).
**Impact:** Supersedes the 2026-06-17 quarantine entry. Submission is built at Stage 9 from an **explicit allowlist** (never by zipping the directory); exclusion enforced by `H5` + `G1`. Updated: `CLAUDE.md` §2, `PLAN.md` Stages 0/1/6/9 + project state, `QA_checklist.md` `H5`.

---

## Assignment facts from HW3 instructions

Verified against `HW3.pdf`. These are the contract; deviating loses rubric points.

### Deliverable & entry point
**Type:** Verified fact
**Entry:** One program `hw3.py`, run as `python hw3.py`, with `input.json` already in the cwd. It produces `<query_name_stem>.log` always, plus the output file(s) the query text asks for.
**Source:** HW3.pdf pp.1, 3–4.
**Impact:** Output filename is runtime-derived from the query, never hardcoded.

### Raw OpenAI API only — no framework
**Type:** Verified fact
**Entry:** Must use `client.chat.completions.create(..., tools=..., tool_choice="auto")` and raw `tool_calls` plumbing. LangGraph / LangChain agents / `create_react_agent` / `AgentExecutor` / `bind_tools` are forbidden anywhere in `hw3.py`.
**Source:** HW3.pdf pp.3–4, 20.
**Impact:** Any such import zeros the 8-pt "no framework" row regardless of correctness. (`QA` `L1`, `L5`.)

### The 6 tools (exact)
**Type:** Verified fact
**Entry:** `calculator`, `extract_from_image`, `build_sql_query`, `execute_sql_query`, `web_search`, `write_file` — signatures and return shapes per `CLAUDE.md` §6. Exactly 6; adding tools earns no credit.
**Source:** HW3.pdf §6.1–6.6, p.27 FAQ.
**Impact:** Stages 2–3; checks `T1`–`T6`, `S0`.

### LLM-call accounting
**Type:** Verified fact
**Entry:** Caps: ≤20 LLM calls and ≤20 tool calls per query, separate counters. Each main-loop `create()` = 1 LLM. `extract_from_image` and `build_sql_query` add +1 LLM each (internal call) on top of counting as 1 tool. Worked example: 8 main + 1 image + 2 sql ⇒ `llm_calls=11`, `tool_calls=3`. Caps are hard (hitting one = 0 correctness for that query).
**Source:** HW3.pdf pp.12, 26.
**Impact:** Stage 4; checks `C1`–`C5`.

### Logging literals (grep-exact)
**Type:** Verified fact
**Entry:** Per step: `Calling LLM for next tool to invoke`, `** Entering tool <name> **`, `Parameter <p> = <first 50 chars, then "..." if longer>`, `** Exiting tool <name> **`. Terminal (exactly one): `final response is = <content>` / `** TERMINATED: LLM call cap reached **` / `** TERMINATED: tool call cap reached **`. Written to both stdout and `<stem>.log`.
**Source:** HW3.pdf p.15.
**Impact:** Stage 4; checks `D1`–`D4`. Casing/whitespace are byte-significant.

### Log path rule
**Type:** Verified fact
**Entry:** Log file = stem of `query_name` (basename minus `.txt`) with subdirectory preserved → `.log`. e.g. `query1/receipt_analysis.txt → query1/receipt_analysis.log`.
**Source:** HW3.pdf pp.1, 4.
**Impact:** Use `os.path.splitext(query_name)[0] + ".log"`; create parent dir. Check `D4`.

### Safety constraints
**Type:** Verified fact
**Entry:** `calculator` must not use raw `eval()` (AST whitelist or safe-eval lib). `execute_sql_query` opens SQLite read-only via `sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)` and returns `[{"error": ...}]` on `sqlite3.Error`. `build_sql_query` must strip markdown fences defensively.
**Source:** HW3.pdf §6.1, §6.4, p.25 Safety, p.27 FAQ.
**Impact:** Stage 2; checks `T1.3`, `T4.2`, `T4.4`, `T3.2`.

### Termination & errors
**Type:** Verified fact
**Entry:** Loop ends for exactly one of: cap hit (failure), final message with no tool_calls (success iff output files exist), or — without terminating — a tool error is fed back for recovery. An uncaught exception crashes the program and zeros functional rows.
**Source:** HW3.pdf pp.14–15.
**Impact:** Loop must be exception-safe; tool errors never force-terminate. Checks `C4`, `G4`, `G5`.

### Validation is grader-side
**Type:** Verified fact
**Entry:** The agent does NOT import or call `*_validate.py`. The agent only writes the output file in the shape the query specifies; the grader imports `<stem_underscored>_validate.py` and calls `<stem_underscored>_answer(answer_dict)`.
**Source:** HW3.pdf pp.16–17, p.27 FAQ.
**Impact:** No validator code in `hw3.py`. Output shape is read from the query text.

### Environment & pinned deps
**Type:** Verified fact
**Entry:** Python ≥3.10, OS-agnostic, no hardcoded paths. Pin `openai==1.51.0` and `duckduckgo-search==6.2.10`; `pillow==10.4.0` only if PIL is used; `mcp==1.27.1` only for the bonus. stdlib (`sqlite3, json, base64, os, sys, ast, importlib.util`) not listed.
**Source:** HW3.pdf pp.22, 24.
**Impact:** Stage 1 + Stage 9; checks `ENV1`, `ENV2`, `H1`, `H2`.

### LLM client setup
**Type:** Verified fact
**Entry:** Use the class Azure deployment via `from openai import OpenAI`, `base_url="https://softwareengineeringusingai.openai.azure.com/openai/v1/"`, `deployment_name="gpt-4.1-mini"`, with the class API key hardcoded (provided in HW3.pdf §"LLM setup"). Same `client` for the main loop and the tool-internal calls.
**Source:** HW3.pdf pp.24–25, p.27 FAQ.
**Impact:** Stage 1 connectivity (`ENV3`); reused in `extract_from_image` / `build_sql_query`.

### Submission set
**Type:** Verified fact
**Entry:** Required: `hw3.py` (with header block), `requirements.txt` (pinned), `partners.txt` (`<Full Name>, <ID>` per line, even solo), the sample `.log`, the sample `_result.json`. Optional: `hw3_mcp.py` + `mcp_setup.md` (bonus), `notes.txt` (caveats). ZIP: `hw3_<ID>.zip` solo / `hw3_<ID1>_<ID2>.zip` pair. No gist files.
**Source:** HW3.pdf pp.22–23.
**Impact:** Stage 9; checks `H1`–`H6`.

### Grading shape
**Type:** Verified fact
**Entry:** 100 pts + 5 bonus. A: loop & tools 40 (tools 18, no-framework 8, caps 6, dispatch 8). B: schemas & prompt 15 (schemas 8, system prompt 4, user message 3). C: correctness 30 (3 simple ×6 + 2 complex ×6, partial-credit tiers). D: logging & output 10 (log 6, output files 4). E: hygiene 5. Bonus: MCP +5 (capped at 100).
**Source:** HW3.pdf pp.20–22, 25–26.
**Impact:** Drives stage priority; mapped in `QA_checklist.md` "Check-to-rubric map".

---

## Discovery & data observations

> Fill during Stages 1–6 as the sample is explored. Do not guess; record only observed values.

### Gist contents (observed)
**Type:** Verified fact · **Source:** Stage 1, 2026-06-18. The 8 gist files are at the repo root. The gist also ships a 9th file `mcp_setup.md` (a bonus reference) — NOT moved to the root (the brief lists only 8); left out of the repo for now.
- **`input.json`:** `query_name="receipt_analysis.txt"`; `resources[]` = `receipt.png` (receipt image), `orders.db`, `customers.db`, each with a free-form `description` (no `type` field — tool choice must reason from extension + description, per `CLAUDE.md` §4.2).
- **`orders.db`:** `CREATE TABLE orders (order_id INTEGER PRIMARY KEY, merchant TEXT NOT NULL, amount REAL NOT NULL, order_date TEXT NOT NULL, customer_id TEXT NOT NULL)`.
- **`customers.db`:** `CREATE TABLE customers (customer_id TEXT PRIMARY KEY, name TEXT NOT NULL, city TEXT NOT NULL, country TEXT NOT NULL)`.
> These schemas/column names are sample-specific — dev knowledge only. They MUST NOT appear as literals in `hw3.py` (`G1`); the agent gets them from the resource `description`s at runtime.

### Sample query shape (observed)
**Type:** Verified fact · **Source:** `receipt_analysis.txt`, read 2026-06-18 (verbatim intent): extract merchant name + total from `receipt.png`; query `orders.db` for all historical orders from that merchant; sum their `amount`; compute the receipt total as a % of that sum (rounded to 2 dp); join `customers.db` to find the city of the customer who placed the most expensive historical order from that merchant; write `receipt_analysis_result.json` with fields `merchant`, `receipt_total`, `historical_total`, `percentage_of_historical`, `top_customer_city`. Output filename + JSON shape are dictated by the query text (drives `P4`).

### Known-good sample answer (from brief; verify in Stage 6)
`{"merchant": "Blue Moon Cafe", "receipt_total": 87.45, "historical_total": 1240.30, "percentage_of_historical": 7.05, "top_customer_city": "Haifa"}` — reference run ≈ 8 tool calls / ≈ 10–12 LLM calls.
> These belong only in the validator and the test scratch dir. They must NOT appear as literals in `hw3.py` (`G1`).

### Environment facts (observed)
**Type:** Verified fact · **Source:** Stage 1 execution, 2026-06-18.
- **Python:** 3.10.17 (satisfies ≥3.10).
- **Resolved deps (`pip freeze`):** `openai==1.51.0`, `duckduckgo_search==6.2.10` (pip normalizes the dist name to an underscore; PyPI package is `duckduckgo-search`).
- **DDGS import path:** `from duckduckgo_search import DDGS` works → `duckduckgo_search.duckduckgo_search.DDGS`. Stdlib imports (`sqlite3, ast, base64, json`) clean.
- **`prepare_dataset.py` (E0):** prints *"All 6 required gist files found (out of 8 — README.md and this script are not checked)."* All 8 files confirmed at the repo root by an independent existence check too.
- **ENV3 smoke test:** one live `client.chat.completions.create(model="gpt-4.1-mini", ...)` returned `"OK"`; response `model` = `gpt-4.1-mini-2025-04-14`. Key/endpoint/deployment are live. Exactly one live LLM call spent this stage.

### 2026-06-18 — httpx must be pinned (openai 1.51.0 incompatible with httpx ≥0.28)
**Type:** Blocker (resolved) / Decision
**Entry:** A fresh `pip install -r requirements.txt` resolved `httpx==0.28.1`, and constructing `OpenAI(...)` then raised `TypeError: Client.__init__() got an unexpected keyword argument 'proxies'`. httpx 0.28 removed the `proxies=` kwarg that `openai==1.51.0` still passes. Added `httpx==0.27.2` to `requirements.txt`; verified a clean fresh-venv install + client construction afterward.
**Reason:** Without the pin the grader's fresh-venv `pip install -r requirements.txt && python hw3.py` would crash before any agent code runs (zeros functional rows). This is a transitive dep but it must be pinned for reproducibility (`CLAUDE.md` §1: "every other non-stdlib import pinned").
**Source:** Stage 1 ENV3 failure + fix, observed live.
**Impact:** `requirements.txt` now has 3 lines. Re-verify under `H1`/`H2` at Stage 9. Deviates from the Stage 1 brief's "only the two deps" — justified as a blocker fix.

### 2026-06-18 — API key recovery from HW3.pdf (digit-9 decode caveat)
**Type:** Verified fact
**Entry:** The class key lives in `HW3.pdf` §"LLM setup" (`GPT41_API_KEY = "..."`, 84 chars, alongside `deployment_name="gpt-4.1-mini"` and the documented endpoint). The PDF has no embedded plain text; it was decoded via the ToUnicode CMaps. **Caveat:** the body font has **no glyph for digit `9`** — every `9` renders as `-` during extraction (cross-checked: gist id `…652eb9`→`…652eb-`, "23:59"→"23:5-"). The raw-decoded key contained a `--` run; corrected `--`→`99` and the live smoke test then succeeded, confirming the correction. The literal key is intentionally NOT stored here; it ships only in `hw3.py` (`CLAUDE.md` §1).
**Source:** Stage 1, PDF decode + live verification.
**Impact:** When `hw3.py` hardcodes the key at Stage 5, take it from the PDF and apply the `9`-decode fix (or copy from the verified value used in this session). Resolves open question #4 partially (gist + setup inspected).

---

## Structural / implementation decisions

> Fill as `hw3.py` sections are built.

### calculator — `log` base, whitelist node set, output normalization
**Type:** Decision · **Source:** Stage 2, 2026-06-18.
- **`log` base:** natural log via `math.log`; `log(x, base)` also supported (Python's `math.log` already accepts an optional second arg). Verified: `log(e)==1`, `log(8,2)==3`.
- **Whitelist node set (AST walker, no raw eval):** `ast.Expression`; `ast.Constant` (int/float only — `bool`, complex, str, None rejected); `ast.BinOp` over `Add/Sub/Mult/Div/Pow`; `ast.UnaryOp` over `UAdd/USub`; `ast.Call` **only** when `func` is a bare `ast.Name` in `{sqrt,log,abs,round,min,max}` (keyword args rejected). Everything else — bare names, attributes (`os.system`), subscripts, comprehensions, lambdas, `&`/bitwise, `__import__`, `open` — raises and is **never executed**. Rejections return an `"Error: <msg>"` string (loop-safe), so `calculator` always returns `str`.
- **Output normalization:** float results are `round(result, 10)` before `str()` to clear IEEE-754 noise. Needed because `(45.20 + 12.50) / 100` is the double `0.5770000000000001`, but QA `T1.1` expects the string `"0.577"`. 10 dp removes ~1e-16 drift while leaving `1024` (int) and `47.9583` untouched. Verified against `T1.1`/`T1.2`.

### web_search — failure shape
**Type:** Decision · **Source:** Stage 2, 2026-06-18.
On any `DDGS` exception/timeout (incl. the common `202 Ratelimit`), return `[{"error": "<message>"}]` — consistent with `execute_sql_query`. Never raises. Native DDGS fields `title/body/href` are mapped to `title/snippet/url`; results capped at 3.

### extract_from_image — JSON-forcing strategy + mime detection
**Type:** Decision · **Source:** Stage 2, 2026-06-18.
- Uses `response_format={"type":"json_object"}` on `gpt-4.1-mini` — **confirmed supported** on the deployment by the live `T2.4` check (the risk flagged in the brief did not materialize).
- Defensive parsing on top anyway (`_parse_json_object`): strips ```` ```json ```` fences, then falls back to first `{` … last `}`. Unparseable/empty → `{"error": ...}` dict (never an uncaught exception).
- **MIME from extension:** `.png→image/png`, `.jpg/.jpeg→image/jpeg`, default `image/png`; bytes base64-encoded into a `data:{mime};base64,{b64}` URL.
- Any failure (missing file, parse fail, API error) returns an `{"error": ...}` dict.

### Tool schemas / dispatch — single-source pairing (no drift)
**Type:** Decision · **Source:** Stage 3, 2026-06-18.
- Section 5 holds six named schema literals (`CALCULATOR_SCHEMA` … `WRITE_FILE_SCHEMA`) directly beside the functions. Section 6 pairs each function with its schema in one `TOOLS` list, then **derives** `TOOL_SCHEMAS = [schema …]` and `TOOL_DISPATCH = {schema["function"]["name"]: fn …}`. Dispatch keys therefore come from the schema names, so a schema name can never silently diverge from a function name.
- An import-time `assert schema["function"]["name"] == fn.__name__` over `TOOLS` fails loudly if anyone edits a name on only one side.
- Schema order mirrors function order: calculator, extract_from_image, build_sql_query, execute_sql_query, web_search, write_file.
- Descriptions written to **steer** (S8): calculator says "NEVER compute arithmetic yourself" + lists `+ - * / ** sqrt log abs round min max`; extract_from_image states it returns merchant/date/total/items for image files; build_sql_query names the `execute_sql_query` pairing, says it does NOT run the query, and to copy `schema_description` from the resource description in input.json; execute_sql_query says it returns row dicts or `[{"error":...}]` so you can rebuild and retry; web_search says use ONLY for facts not in the provided resources; write_file says use it to produce the requested output file then stop. Parameter-level descriptions enriched (calculator example `(45.20 + 12.50) / 100`; schema_description "copied … from input.json").
- No sample-specific literals in any schema (G1 stays clean); generic examples only.

### System prompt + user message — final wording (Section 8)
**Type:** Decision · **Source:** Stage 5, 2026-06-18.
- **SYSTEM_PROMPT** (Section 8) establishes: the agent answers by calling tools and cannot read files / do math / query DBs / browse itself; names all 6 tools with a one-line role each; per-sub-problem preference — calculator for ALL arithmetic ("never compute … in your head"), .db → build_sql_query **then** execute_sql_query (always paired, "does NOT run the query"), copy schema_description from the resource description, combine related needs into ONE query because each build_sql_query costs an LLM call; extract_from_image for receipt/invoice images; web_search ONLY for facts not in the resources/query; write_file to produce the query-specified output file(s) (filename/shape read from the query, never invented). Efficiency line names the 20/20 budget and "never recompute". Stop rule: when solved and all output files written, reply with a short summary and NO tool call; do not call tools after writing output.
- **build_user_message(query_text, resources)** returns one string: verbatim query text under `=== QUERY ===`, then an `=== Available resource files ===` block listing each resource as `- <file_name>: <description>` (verbatim, so the model can copy a description into schema_description), then a one-line reminder to write the output and finish with no tool call. Empty-resources case prints `(no resource files were provided)`.
- **No sample literals** in either (G1 clean). Generic examples only ("result.json", "reports/summary.txt") — none of the sample's `receipt_analysis_result.json`.

### Input parsing + main() (Section 10)
**Type:** Decision · **Source:** Stage 5, 2026-06-18.
- `load_input(input_path="input.json")` → `(query_name, resources, query_text)`. Validates: file exists; valid JSON; top-level object; non-empty string `query_name`; `resources` is a list (defaults to `[]`); query file exists. Raises `FileNotFoundError`/`ValueError` with a clear message on any violation (callers turn it into a clean print, never a traceback).
- `main()` is exception-safe end to end: `load_input` failure → `print("Error: …")` and return (no LLM call). Otherwise `resolve_log_path` → open log `"w"` (parent dir already created by `resolve_log_path`) → `messages=[system,user]` → `run_agent(messages, log_file, client)` in a try/except that reports a failure to both stdout and the log, with the log closed in `finally`. The log handle is held open for the whole `run_agent` call (dual-log invariant).
- **No output path in main():** the only file opened for writing is the resolved `log_path`; the output file is produced by the `write_file` tool inside the loop, with its name taken from the query text (P4 / G1). Asserted by `test_P4_main_does_not_construct_output_path`.

### Content-filter resilience — main-loop BadRequestError handling (Section 9, Stage 7)
**Type:** Decision · **Source:** Stage 7, 2026-06-18 (the one sanctioned Stage-7 code change; mechanism specified by the PM brief §4).
- **Catch type:** ONLY `openai.BadRequestError`, wrapped around the main-loop `create()` (Section 9). Added `BadRequestError` to the Section-2 import (`from openai import OpenAI, BadRequestError`). Any other exception is deliberately left to propagate to `main()`'s existing handler — no blanket `except`, so real bugs surface and the loop cannot spin on an unexpected error (proven by `test_G5_only_bad_request_is_caught`).
- **Recovery message:** on `BadRequestError`, no assistant message was produced, so we append a **`role:"user"`** note — `"The previous request was rejected (content filter / bad request): <err>. Adjust your approach and continue."` — which the model sees on the next turn so it can change approach.
- **Counting:** the failed attempt is counted toward `llm_calls` (`llm_calls += 1` in the except branch) so the top-of-loop cap bounds retries — content-filter errors must NOT retry forever (`CLAUDE.md` §4.6). With a persistent filter the loop terminates at `LLM_CAP` (`G5b`).
- **No graded log literal added or altered.** Updated the stale "Stage 7 will wrap this" comment at the old line 700.

### Anti-leakage audit (Stage 7, `G1`/`G2`) + the `receipt.png`/`orders.db` judgment call
**Type:** Decision / Verified fact · **Source:** Stage 7, 2026-06-18.
- **`G1` authoritative grep** (`blue moon|87\.45|1240\.3|haifa|receipt_analysis_result|orders\(|customers\(`, case-insensitive) on `hw3.py` → **0 hits**. Codified as `test_G1_authoritative_grep_clean`.
- **Curated extras** (also asserted absent, `test_G1_no_sample_specific_identifiers`): the sample output keys `top_customer_city`, `percentage_of_historical`, `historical_total`, `receipt_total`, and the gist column names `order_id`, `order_date`, `customer_id` — none present. `merchant` is intentionally NOT forbidden (it is part of the documented `extract_from_image` contract, `CLAUDE.md` §6 — not sample leakage).
- **`G2`**: no quoted absolute path (POSIX `/Users|/home|/tmp|...` or Windows drive) in `hw3.py`; `os.path` + `os.makedirs` used for path construction. Codified in `test_G2_*`. (A naive `[A-Za-z]:\\` grep false-positives on `:\n` inside strings like `"...six tools:\n"`; the test requires a quote before the drive letter to avoid that.)
- **Judgment call — `receipt.png` / `orders.db` as schema-description examples (hw3.py ~L371/L442):** **KEPT** as illustrative "e.g." text, not branching logic. Rationale: (1) they are generic filename examples that steer the model toward "use the resource's own filename", not hardcoded answers or sample-specific logic; (2) the `G1` grep targets `orders\(`/`customers\(` (table-literal shape) and `receipt_analysis_result` — none of which these match; (3) the descriptions are graded (S8) and genericizing them ("an image file", "a .db file") would weaken the steer for no anti-leakage benefit. Per the brief this was the recommended option (keep + justify); genericizing would have been a non-G5 code change requiring PM sign-off, which was not warranted.
- **Related minor note — `resolve_log_path` docstring (hw3.py ~L572)** uses `query1/receipt_analysis.txt -> query1/receipt_analysis.log` as the log-path example. KEPT: this is the assignment's own canonical example of the log-path rule (`HW3.pdf`), in a comment, referencing the *input* query name (not an output value or answer). The authoritative `receipt_analysis_result` grep stays clean.

### Loop — dispatch, counters, termination (Section 9)
**Type:** Decision · **Source:** Stage 4, 2026-06-18.
- **Client injectable:** `run_agent(messages, log_file=None, client=client)` — `client` defaults to the module client (bound at def time), and tests pass a `FakeLLMClient`. `messages` is mutated in place; `run_agent` returns a dict `{llm_calls, tool_calls, final_content, terminated, messages}` (`terminated ∈ {"llm_cap","tool_cap","final"}`) for assertions.
- **Counters are name-based and independent.** Every main-loop `create()` = +1 LLM. A successful dispatch of a tool whose name is in `LLM_BACKED_TOOLS = {"extract_from_image","build_sql_query"}` = +1 extra LLM. Every dispatched tool = +1 tool. The +1-LLM increment is keyed on the tool **name**, independent of the tool's internals — so tests stub those two tools (no network) and the increment still fires.
- **Termination precedence (§8):** (1) LLM cap checked at the **top** of the loop, before `create()`, so it beats a would-be `final` on the next turn; (2) no `tool_calls` → `final response is = <content>`; (3) tool error → appended as a `role:"tool"` message, loop continues (never terminates); (4) no uncaught exception. Tool cap is checked **before** each dispatch inside the turn — hitting it stops mid-turn with no further dispatch and breaks the whole loop (no next `create()` follows, so the unmatched `tool_calls` never reach the API — L4 stays satisfied).
- **Defensive dispatch:** `json.loads(arguments)` + the dispatch are wrapped in one `try/except`. Bad-JSON args, a non-dict decode, an unknown tool name, or a raising tool all become `{"error": str(e)}`, appended as the tool reply — the loop recovers, never crashes (covers 4.6 and forward G4). A failed parse/dispatch still increments `tool_calls` (one tool_call slot consumed, one reply sent) but does **not** add the +1 LLM (no internal call happened; `dispatched` flag gates it).
- **Parameter-logging order:** arguments are logged in `json.loads` insertion order (the order the model emitted them), matching the sample trace — not schema order.
- **Logging-line placement (minor deviation from the brief's literal step order):** `** Entering tool <name> **` is logged immediately after the tool-cap check and **before** `json.loads`, so `Entering`/`Exiting` are always balanced even on a bad-JSON turn. The brief lists "parse, then Entering"; for well-formed input (the graded path) the two orderings are identical. `Parameter` lines still come after `Entering` and only for successfully-parsed dict args.
- **`model_dump(exclude_none=True)` round-trip:** the assistant message is re-appended via `msg.model_dump(exclude_none=True)`; `tool_calls` survive (verified by `test_L4_assistant_message_round_trips_tool_calls`), and a `None` content is dropped — matching how the OpenAI SDK serialises a tool-call turn.

---

## Bonus (MCP) decisions

**2026-06-18 — Bonus approved (Asaf).** Attempting the MCP showcase (Stage 8).
- **Compat (PM-verified, dry-run):** `mcp==1.27.1` requires `httpx>=0.27.1`; our `httpx==0.27.2` satisfies it, so adding `mcp` does NOT upgrade httpx and `openai==1.51.0` keeps working (no return of the Stage 1 `proxies` crash). Node v23.11.0 / npx 10.9.2 present. Server runs via `npx -y @brightdata/mcp`.
- **Token handling (security):** Asaf provided a Bright Data free-tier API token. It is held in the **environment only** (an env var read by `hw3_mcp.py`); the literal value is **never** written to any repo file — not `hw3_mcp.py`, not `mcp_setup.md`, not this log, not the ZIP. Unlike the shared Azure key (which the assignment requires hardcoded in `hw3.py`), this personal credential must not be committed.
- **Verify command:** `python hw3_mcp.py` (with `BRIGHTDATA_API_TOKEN` exported). Record the tool invoked + printed result in the Stage 8 handback.

---

## Open questions & blockers

| # | Question / Blocker | Raised by | Date | Status | Resolution |
|---|---|---|---|---|---|
| 1 | Partner full name(s) and email(s) for `partners.txt` and the `hw3.py` header block. ID `209252154` is known from the folder name; confirm solo vs pair. | PM | 2026-06-17 | Resolved | Asaf 2026-06-18: **SOLO** — Asaf Ramati, ID 209252154, email **asaf.ramati@post.runi.ac.il**. ⇒ `partners.txt` = `Asaf Ramati, 209252154`; `hw3.py` header Name/ID/Email; ZIP `hw3_209252154.zip` (H6). |
| 2 | Will the optional MCP bonus be attempted? (Adds `mcp==1.27.1` + Node 18+ dependency.) | PM | 2026-06-17 | Resolved | Asaf 2026-06-18: **ATTEMPT** → Stage 8 active. PM pre-verified compat: mcp 1.27.1 needs httpx>=0.27.1 (our 0.27.2 satisfies it — openai untouched); Node v23.11.0/npx 10.9.2 present. |
| 3 | Final due date — `HW3.pdf` says "TBD at 23:59". | PM | 2026-06-17 | Resolved | Asaf 2026-06-18: not needed for tracking. |
| 4 | Actual gist contents (schemas, row counts, label spellings) not yet inspected. | PM | 2026-06-17 | Resolved | Stage 1, 2026-06-18: `input.json` + both DB schemas + sample query inspected and recorded above. Gist also ships a 9th file `mcp_setup.md` (bonus ref), not moved to root. |

---

## Stage handbacks

### Standard handback template

```markdown
### Stage N handback

`[YYYY-MM-DD] [Agent/PM] Stage N status.`

**What changed:** hw3.py sections drafted vs written; tests added; files touched.
**DoD checklist:** ✅ / ⚠️ per referenced QA ID; drafted-only vs written-and-verified separated.
**QA results:** which check IDs were run, pass/fail.
**Decisions made:** non-obvious decisions, or None.
**Deviations:** anything different from PLAN.md, or None.
**Blockers / risks:** open issues, or None.
**Next recommended action:** one concrete next step.
```

### Stage 0 handback

`[2026-06-17] [PM] Stage 0 in progress.`

**What changed:** Read `HW3.pdf` (27 pp), `PM_Methodology_Prompt.md`, and the `Reference/` benchmark (CLAUDE/PLAN/NOTES). Authored `CLAUDE.md`, `QA_checklist.md`, `PLAN.md`, and this `NOTES.md`.
**DoD checklist:** ✅ `CLAUDE.md`, ✅ `QA_checklist.md`, ✅ `PLAN.md`, ✅ `NOTES.md` drafted. ⚠️ Gist relocation to `_gist/`, skeleton `requirements.txt`/`partners.txt`, and Asaf review still pending.
**QA results:** None run yet (no code).
**Decisions made:** Four-file methodology; section-modular single file; gist quarantine; "anti-leakage" reinterpreted for this assignment as *no hardcoding of sample-specific values / runtime reasoning from `input.json`*.
**Deviations:** Added a fourth file (`QA_checklist.md`) beyond the methodology's three, per Asaf's request.
**Blockers / risks:** Open questions 1–4 above (partner identity, bonus go/no-go, due date, gist not yet inspected).
**Next recommended action:** Asaf reviews the four files; on green-light, begin Stage 1 (environment & gist verification).

### Stage 1 handback

`[2026-06-18] [Agent] Stage 1 — Environment & gist verification: COMPLETE (all 4 DoD checks run & confirmed).`

**What changed:** Cloned the course gist and moved the 8 sample files to the repo root (`input.json`, `receipt_analysis.txt`, `receipt_analysis_validate.py`, `receipt.png`, `orders.db`, `customers.db`, `prepare_dataset.py`, `README.md`); removed the clone dir. Created `requirements.txt` (now 3 pinned lines — see deviation). Created `.venv` and installed deps. No agent code written (per scope).
**DoD checklist (written-and-verified, not inspected):**
- ✅ `E0` — `python prepare_dataset.py` confirms the required gist files present at root.
- ✅ `ENV1` — fresh-venv `pip install -r requirements.txt` exits 0; `openai==1.51.0` + `duckduckgo-search==6.2.10` (+`httpx==0.27.2`) resolved.
- ✅ `ENV2` — `openai`, `duckduckgo_search`, `sqlite3`, `ast`, `base64`, `json` import; `from duckduckgo_search import DDGS` works.
- ✅ `ENV3` — one live `create()` returned `"OK"` (`gpt-4.1-mini-2025-04-14`); key/endpoint/deployment live.
- ✅ Env facts recorded above.
**QA results:** E0 ✅, ENV1 ✅ (verified in a throwaway fresh venv too), ENV2 ✅, ENV3 ✅. Exactly one live LLM call spent.
**Decisions made:** (1) Pinned `httpx==0.27.2` to fix the openai-1.51.0/httpx-0.28 `proxies` crash. (2) API key recovered from `HW3.pdf` with a `9`→`-` decode correction, verified live. (3) Did not move the gist's 9th file `mcp_setup.md` (bonus ref) to root — only the 8 specified.
**Deviations:** `requirements.txt` has 3 lines instead of the brief's 2 — the `httpx` pin is a required blocker fix (the grader would hit the same crash otherwise).
**Blockers / risks:** None open. Shared Azure key live but quota-limited — keep using fakes/mocks for tests. The PDF key-decode caveat is documented so it isn't re-broken at Stage 5.
**Next recommended action:** On green-light, start Stage 2 (the 6 tool functions, test-first against `T1`–`T6`) — beginning with the pure ones (`calculator`, `execute_sql_query`, `write_file`).

### Stage 2 handback

`[2026-06-18] [Agent] Stage 2 — Tool layer (6 functions): COMPLETE (T1–T6 offline pass; T2.4 live pass; T5.4 live ratelimited→skipped).`

**What changed:**
- **Written & test-verified** `hw3.py` Section 4 — all 6 tools: `calculator` (+`_calc_eval` AST walker), `extract_from_image` (+`_parse_json_object`), `build_sql_query` (+`_strip_sql_fences`), `execute_sql_query`, `web_search`, `write_file`.
- **Written (minimal/provisional)** `hw3.py` Sections 1–3: header stub (partner Name/Email TBD, ID `209252154` in place); imports (stdlib → `openai` → `duckduckgo_search`); Configuration (`LLM_CAP/TOOL_CAP/PARAM_LOG_LIMIT`, `DEPLOYMENT_NAME`, `ENDPOINT`, `GPT41_API_KEY`, module-level `client`). These are intentionally minimal so the two LLM tools are callable in isolation; finalized at Stage 5.
- New file `tests/test_tools.py` (35 tests; offline by default, live gated behind `RUN_LIVE=1`).
- Installed `pytest` into `.venv` (dev-only; not added to `requirements.txt`). `requirements.txt` untouched.
- API key recovered cleanly from `HW3.pdf` p.24 via `pypdf` this session (84 chars, `9`s intact, no `-` — the prior session's ToUnicode `9→-` artifact did not occur with `pypdf`); confirmed live by `T2.4`.

**DoD checklist (all written-and-test-verified unless noted):**
- ✅ `T1` calculator — arithmetic + `sqrt/log/abs/round/min/max/**`; rejects `__import__`/`open`/attribute/bare-name/subscript/comprehension/lambda/bitwise (never executed; proven by a no-side-effect file check); always returns `str`.
- ✅ `T2` extract_from_image — base64 + mime (.png/.jpg/.jpeg); returns documented dict; robust parse of fenced/prose JSON; missing file & unparseable → `{"error":...}`. **`T2.4` live: PASS** (merchant ≈ "Blue Moon Cafe", total ≈ 87.45).
- ✅ `T3` build_sql_query — bare SQL; strips ```` ```sql ````/```` ``` ````/```` ```SQL ```` fences; never executes; prompt carries the "ONLY the SQL … no markdown/explanation" instruction.
- ✅ `T4` execute_sql_query — read-only `file:{db}?mode=ro` (uri=True, asserted via connect spy); `list[dict]`; INSERT blocked + file unchanged; invalid SQL → `[{"error":...}]`; never raises.
- ✅ `T5` web_search — mocked DDGS maps `title/body/href → title/snippet/url`, caps at 3; failure → `[{"error":...}]`. ⚠️ **`T5.4` live: SKIPPED** — DDGS returns `202 Ratelimit` for this IP (env flakiness flagged in the brief, not a code defect). Live *error path* confirmed; happy-path mapping proven offline.
- ✅ `T6` write_file — writes content, creates parent dirs, returns exactly `"Wrote N bytes to <file_name>"` with UTF-8 byte count (verified with a 5-byte `"café"`).
- ✅ Decisions logged (above): `log` base + whitelist node set + float normalization; web_search failure shape; extract_from_image JSON-forcing + mime.
- ✅ Sections 1–3 noted minimal/provisional; Section 4 complete.

**QA results:** offline `33 passed, 2 skipped` (the 2 skips are the gated live tests). Live run: `T2.4` PASS, `T5.4` SKIP (ratelimit). `G1` spot-grep on `hw3.py` (`blue moon|87.45|1240.3|haifa|receipt_analysis_result|orders\(|customers\(`) → no matches (clean). (Full `G1` audit is Stage 7.)

**Decisions made:** see the three "Structural / implementation decisions" entries above. Additional: calculator returns an `"Error: …"` string (not a raise) on rejection, for loop-safety while keeping the `str` return contract.

**Deviations:**
- Float-normalization (`round(result,10)`) added to `calculator` beyond the brief — required to satisfy `T1.1`'s expected string `"0.577"` (raw `str(float)` gives `0.5770000000000001`).
- `pytest` installed into the venv (dev-only tooling); deliberately **not** added to `requirements.txt`.
- Key was hardcoded now (Section 3) rather than waiting for Stage 5, because `extract_from_image`/`build_sql_query` must be live-callable in isolation this stage. The `9→-` decode fix was unnecessary here (pypdf decoded correctly); value re-verified live.

**Blockers / risks:**
- DDGS IP rate-limiting blocks the `T5.4` live happy-path locally; revisit opportunistically (E2E Stage 6 / from a different network). Not a code defect.
- Shared Azure quota: exactly **1** live LLM call spent this stage (T2.4). Keep using mocks.
- Header partner Name/Email still TBD (open question #1); key currently lives in `hw3.py` per spec.

**Next recommended action:** PM gate Stage 2 → Stage 3 (tool JSON schemas `S0`–`S9`), keeping `TOOL_SCHEMAS`/`TOOL_DISPATCH` adjacent to the functions.

### 2026-06-18 — PM gate: Stage 2 ✅

**Type:** Handback (PM verification)
**Entry:** PM independently re-ran the offline suite (`./.venv/bin/python -m pytest -q` → `33 passed, 2 skipped`, matching the handback), re-ran the `G1` anti-leakage grep on `hw3.py` (clean — no business literals), the forbidden-framework grep (none — early positive for `L5`), and confirmed all 6 tool `def`s present with correct names. Stage 2 gated complete; `PLAN.md` flipped to ✅ (Stages 0–2). Stage 3 active.
**Reason:** Methodology requires the PM to verify, not inspect — numbers re-derived from source.
**Impact:** Two watch-items carried to Stage 6: retry `T5.4` from a non-ratelimited network; verify `calculator`'s `round(...,10)` float normalization never disturbs an exact-match validator (low risk — string contract, `T1.1` passed). Accepted deviations: key hardcoded at Stage 2 (de-risks the LLM tools; PDF decoded cleanly so the `9`→`-` fix was unneeded); `pytest` kept out of `requirements.txt` (dev-only, correct).

### Stage 3 handback

`[2026-06-18] [Agent] Stage 3 — Tool JSON schemas: COMPLETE (S0–S8 offline pass; S9 one gated live acceptance pass).`

**What changed:**
- **Written & test-verified** `hw3.py` Section 5 (six schema literals) and Section 6 (single-source `TOOLS` pairing → derived `TOOL_SCHEMAS`/`TOOL_DISPATCH` + import-time name-match assertion), appended after `write_file`. No Stage-2 function behavior touched; no signature changes needed.
- New file `tests/test_schemas.py` (S0–S9; offline by default, S9 live-gated behind `RUN_LIVE=1`, same mechanism as Stage 2).

**DoD checklist (all written-and-test-verified):**
- ✅ `S0` — exactly 6 schemas; three-way match (schema names == 6 function names == `TOOL_DISPATCH` keys; each `schema["function"]["name"] == fn.__name__`; dispatch resolves to the right callable); no 7th tool.
- ✅ `S1`–`S6` — each schema `{"type":"function","function":{name,description,parameters}}`; `parameters` is an `object` with non-empty `properties`; every property typed `"string"` with a non-empty description.
- ✅ `S7` — `required` arrays exactly: calculator `[expression]`, extract_from_image `[image_path]`, build_sql_query `[natural_language, schema_description]`, execute_sql_query `[sql, db_path]`, web_search `[query]`, write_file `[file_content, file_name]`.
- ✅ `S8` — descriptions state *when to use*; calculator "NEVER compute yourself" + ops list; extract_from_image returns merchant/date/total/items; build_sql_query names the execute_sql_query pairing + "does NOT run" + schema-from-input.json; execute_sql_query run + error-shape/retry; web_search "only … not in the provided resources"; write_file produces the requested output; param-level examples enriched; no empty/"does math" text.
- ✅ `S9` — `create(model, messages, tools=TOOL_SCHEMAS, tool_choice="auto")` accepted, no 400 (one live call).

**QA results:** offline `tests/test_schemas.py` → `23 passed, 1 skipped` (skip = live S9); full offline suite → `56 passed, 3 skipped`. `S9` live → `1 passed` (exactly **1** live LLM call spent this stage). `G1` spot-grep on `hw3.py` → 0 matches (clean); forbidden-framework grep → 0 (L5 stays clean).

**Decisions made:** single-source pairing + import-time name assertion (recorded above under "Tool schemas / dispatch"). Test asserts the `does not run`/`not run` pairing phrasing, the `web_search` "only … resources" scope, and parameter-level enrichment, so S8 regressions fail fast.

**Deviations:** None. (One micro-fix during the stage: added "schema_description copied from … input.json" to the build_sql_query description so it references the schema — matches the brief's S8 requirement.)

**Blockers / risks:** None. Shared Azure quota: 1 live call spent. Header partner Name/Email still TBD (open #1) — unrelated to this stage.

**Next recommended action:** PM gate Stage 3 → open Stage 4 (agentic loop, dispatch, caps, logging: `L1`–`L5`, `C1`–`C5`, `D1`–`D4`), driven by `FakeLLMClient` with a "never stops" client to prove both caps.

### Stage 4 handback

`[2026-06-18] [Agent] Stage 4 — Agentic loop, dispatch, caps, logging: COMPLETE (L1–L5, C1–C5, D1–D4 all run & pass offline; zero live calls).`

**What changed:**
- **Written & test-verified** `hw3.py` Section 7 (logging helpers: `dual_log`, `truncate_for_log`, `resolve_log_path`) and Section 9 (`run_agent` — the raw-API loop with both counters + termination precedence). Added a Section 8 placeholder comment (SYSTEM_PROMPT/`build_user_message` land at Stage 5).
- **Section 3:** added one named constant `LLM_BACKED_TOOLS = {"extract_from_image","build_sql_query"}` for the loop's name-based +1-LLM accounting (no magic values inline, per §5).
- New file `tests/test_loop.py` (20 tests; fully offline — `FakeLLMClient` + stubbed LLM-backed tools, no network). Fakes mimic the OpenAI message object (`.content`, `.tool_calls`, `.model_dump(exclude_none=)`).

**DoD checklist (all written-and-test-verified):**
- ✅ `L1` — loop calls `create(model, messages, tools=TOOL_SCHEMAS, tool_choice="auto")` (asserted `tools is TOOL_SCHEMAS`, `tool_choice=="auto"`).
- ✅ `L2` — dispatch by name with `json.loads(arguments)` unpacked as kwargs (`calculator("2+3")` → tool reply `"5"`).
- ✅ `L3` — tool reply is `{"role":"tool","tool_call_id":tc.id,...}`, ids match 1:1.
- ✅ `L4` — multi-tool-call turn: both replies appended before the next `create()`; `tool_calls` survive the `model_dump` round-trip.
- ✅ `L5` — framework grep clean (`grep -Ei "langgraph|langchain|create_react_agent|AgentExecutor|bind_tools" hw3.py` → no matches).
- ✅ `C1` — never-stops client: `llm_calls` stops at 20, logs `** TERMINATED: LLM call cap reached **`; tool isolated at 10 in the +2-LLM/+1-tool recipe.
- ✅ `C2` — 21 calculator calls in one turn: cap trips at the 21st (no 21st dispatch), `** TERMINATED: tool call cap reached **`, `tool_calls==20`, `llm_calls==1`.
- ✅ `C3` — sequence extract/build/build/calculator→final: hand-computed `llm_calls==8` (5 creates +1 image +2 build), `tool_calls==4`. (Per the updated C3: the PDF 8/1/2⇒11/3 is formula arithmetic, not a single trace.)
- ✅ `C4` — cap precedence over `final` (LLM_CAP=1 monkeypatch: cap line fires, `final response is =` never logged); tool error + bad-JSON args + raising tool all recover without terminating.
- ✅ `C5` — no-tool-call message → `final response is = <content>`, clean exit, no cap.
- ✅ `D1`/`D2` — the four literals appear verbatim in **both** stdout and the `.log` file.
- ✅ `D3` — truncation: `>50` → first 50 + `...`; `<=50` → verbatim, no ellipsis (boundary 50/51 unit-tested).
- ✅ `D4` — `resolve_log_path("query1/x.txt")=="query1/x.log"` with parent dir created; no-subdir case correct.

**QA results:** `tests/test_loop.py` → `20 passed`. Full offline suite → `76 passed, 3 skipped` (the 3 skips are the Stage 2–3 gated live tests; none added this stage). Framework grep clean; `G1` spot-grep clean. **Zero live LLM calls spent this stage.**

**Decisions made:** see "Loop — dispatch, counters, termination (Section 9)" above — client injection, name-based counters, termination precedence, defensive dispatch, parameter-logging order, and the one logging-placement deviation.

**Deviations:** `** Entering tool <name> **` is logged just before `json.loads` rather than just after (the brief's literal step order is "parse → Entering"). Reason: keeps `Entering`/`Exiting` balanced on a bad-JSON turn; identical to the brief for all well-formed (graded) input. Logged as a decision above.

**Blockers / risks:** None. `run_agent` is exception-safe end to end (bad-JSON args, unknown tool, and a raising tool all recover — three dedicated tests). Header partner Name/Email still TBD (open #1, unrelated).

**Next recommended action:** PM gate Stage 4 → open Stage 5 (`SYSTEM_PROMPT`, `build_user_message`, `input.json` parsing, `main()`; `P1`–`P4`), wiring `run_agent` into a real `main()` with `resolve_log_path` opening the log file.

### 2026-06-18 — PM gate: Stage 3 ✅

**Type:** Handback (PM verification)
**Entry:** PM re-ran the full offline suite (`56 passed, 3 skipped`, matching the handback) and an independent structural probe of `hw3.TOOL_SCHEMAS`/`TOOL_DISPATCH`: count==6, `S0` three-way match (names == functions == dispatch) `True`, every dispatch entry resolves to the matching callable, `required` arrays byte-exact per the table, all properties `"string"`-typed, and `S8` content present (`build_sql_query` names `execute_sql_query`; `web_search` scoped to provided resources; no empty descriptions). `G1`/framework greps clean. `PLAN.md` flipped to ✅ (Stage 3); Stage 4 active.
**Reason:** PM verifies by re-deriving, not inspecting.
**Impact:** Schema layer locked. Single-source `TOOLS` pairing + import-time `name == fn.__name__` assert means Stage 4 dispatch can trust `TOOL_DISPATCH` keys. No new risks; carry-overs unchanged (T5.4 live; calculator float-norm watch).

### Stage 5 handback

`[2026-06-18] [Agent] Stage 5 — System prompt, user message, I/O: COMPLETE (P1–P4 all run & pass offline; zero live calls).`

**What changed:**
- **Written & test-verified** `hw3.py` Section 8 (`SYSTEM_PROMPT`, `build_user_message`) — replaced the placeholder; and Section 10 (`load_input`, `main()`, `if __name__ == "__main__"`) appended after the loop.
- **Finalized** Sections 1–3: header note trimmed (the "MINIMAL/PROVISIONAL" caveat removed; Sections 1–3 are now final); Name/Email left as a clearly-marked TODO (open #1), ID `209252154` in place. No config/import/tool/schema/loop code changed.
- New file `tests/test_io.py` (16 tests; fully offline — no live LLM/network).

**DoD checklist (all written-and-test-verified):**
- ✅ `P1` — SYSTEM_PROMPT names all 6 tools, states the build_sql_query→execute_sql_query pairing + "does NOT run", scopes web_search to non-resource/external facts, carries the "write output then stop / no tool call" rule, "never compute yourself" arithmetic preference, and the 20/20 efficiency line; non-trivial length (>400 chars).
- ✅ `P2` — `build_user_message` output contains the verbatim query text and every resource `file_name` + `description`; empty-resources case handled.
- ✅ `P3` — `load_input` parses `query_name` + `resources[]`, resolves a subdir `query_name` relative to cwd and reads its text; `resolve_log_path` yields the subdir-preserving `.log` with parent dir created; malformed JSON / missing `query_name` / missing query file each raise a clean error; `main()` on malformed/missing input prints `Error: …` and returns (no traceback, no LLM call).
- ✅ `P4` — grep of `hw3.py`: no `receipt_analysis_result` / `_result.json` literal; `main()` opens only `log_path` for writing (the output path comes from the query via `write_file`).

**QA results:** `tests/test_io.py` → `16 passed`. Full offline suite → `92 passed, 3 skipped` (the 3 skips are the unchanged Stage 2–3 live-gated tests). Framework grep clean (`L5`); `G1` spot-grep clean. **Zero live LLM calls spent this stage.**

**Decisions made:** see "System prompt + user message — final wording" and "Input parsing + main()" above (prompt content, user-message format, `load_input` validation contract, exception-safe `main()` with the log held open across `run_agent`).

**Deviations:** None. (Offline-only honored — the first live end-to-end run is Stage 6.)

**Blockers / risks:** None new. Carry-overs unchanged: partner Name/Email TODO (open #1) before Stage 9; `T5.4` live web_search retry + calculator float-norm watch at Stage 6. `main()` reads `input.json` from cwd — the first real run against the gist sample is Stage 6 (protects quota).

**Next recommended action:** PM gate Stage 5 → open Stage 6 (end-to-end sample run: `python hw3.py` at the repo root → `receipt_analysis.log` + `receipt_analysis_result.json`, match the validator within tolerance; `E1`–`E4`).

### 2026-06-18 — PM gate: Stage 4 ✅

**Type:** Handback (PM verification)
**Entry:** PM re-ran the full offline suite (`76 passed, 3 skipped`) and the loop suite alone (`tests/test_loop.py` `20 passed`), both matching the handback. Independently grepped `hw3.py` for all seven byte-exact log literals — `Calling LLM for next tool to invoke`, `** Entering tool `, `** Exiting tool `, `Parameter `, `final response is = `, `** TERMINATED: LLM call cap reached **`, `** TERMINATED: tool call cap reached **` — all present. Framework + `G1` greps clean. Zero live calls spent.
**Reason:** PM verifies by re-deriving; the Part-D literals are grep-scored, so source-level confirmation matters.
**Impact:** Loop + caps + logging locked. Accepted deviation: `** Entering tool **` logged before `json.loads` (keeps Entering/Exiting balanced on a malformed-JSON turn; identical for well-formed graded input). `PLAN.md` flipped to ✅ (Stage 4); Stage 5 active. Carry-overs unchanged.

### 2026-06-18 — PM gate: Stage 5 ✅

**Type:** Handback (PM verification)
**Entry:** PM re-ran the full offline suite (`92 passed, 3 skipped`) and `tests/test_io.py` (`16 passed`), matching the handback. Independent probes: `SYSTEM_PROMPT` (2238 chars) names all 6 tools and carries the `build_sql_query`→`execute_sql_query` pairing and the stop rule ("...reply with a short natural-language summary and **DO NOT call any tool**. That empty-tool reply is how you finish."); `build_user_message(...)` carries the verbatim query text + each resource `file_name` + `description`; `P4`/`G1` greps clean (no `_result.json`/sample literals). Zero live calls.
**Reason:** PM verifies by re-deriving; my first crude substring probe for the stop rule false-negatived on phrasing, so I confirmed the semantics directly before gating.
**Impact:** `hw3.py` is now end-to-end runnable. `PLAN.md` flipped to ✅ (Stage 5); Stage 6 active. Stage 6 is the first real spend of Azure calls. Header Name/Email still TODO (open #1).

### Stage 6 handback

`[2026-06-18] [Agent] Stage 6 — End-to-end sample query (first live run): COMPLETE (E1–E4 satisfied; validator True; one live run, no code change).`

**What changed:** No code edits. Ran `./.venv/bin/python hw3.py` once at the repo root against the gist sample. Produced the two submission artifacts: `receipt_analysis.log` (2622 B) and `receipt_analysis_result.json` (158 B). The run passed on the **first attempt** — none of the three budgeted attempts needed.

**DoD checklist (all written-and-verified by live run + grep/validator):**
- ✅ `E1` — both artifacts exist; JSON parses. Keys exactly `merchant, receipt_total, historical_total, percentage_of_historical, top_customer_city`.
- ✅ `E2` — shipped validator returns **True**. Output (observed): `{"merchant":"Blue Moon Cafe","receipt_total":87.45,"historical_total":1240.3,"percentage_of_historical":7.05,"top_customer_city":"Haifa"}`. All five values inside the validator's tolerances (monetary ±0.01, pct ±0.05).
- ✅ `E3` — within caps with headroom. **`tool_calls = 11`** (1 extract_from_image + 3 build_sql_query + 3 execute_sql_query + 3 calculator + 1 write_file). **`llm_calls = 16`** (12 main-loop `create()` + 1 image + 3 build_sql). Both well under 20/20.
- ✅ `E4` — recovery: **no natural tool error occurred** this run (`grep -c error` on the log = 0; the model's SQL/calculator/extraction all succeeded first try). Satisfied **structurally** by Stage 4's defensive-recovery tests (`C4`: bad-JSON args / unknown tool / raising tool / tool error all recover without terminating) — not fabricated.
- ✅ G1 anti-leakage grep on `hw3.py` = 0 hits; framework grep = 0 hits (still clean). Final line `final response is = ` present in the log file (dual-write confirmed). Offline suite **not** re-run — no prompt/code was touched, so no regression risk.

**QA results:** E1 ✅, E2 ✅ (validator True), E3 ✅ (11 tool / 16 LLM, recorded), E4 ✅ (structurally covered). G1 + framework greps clean.

**Decisions made:** None — passed as-built. Calculator float-normalization watch (carried from Stage 2) resolved: `historical_total` serialized as `1240.3` and `percentage_of_historical` as `7.05`; the `round(...,10)` normalization did **not** surface long-float drift, and the validator accepts both. The `round(7.050713537, 2)` calculator step gave exactly `7.05`.

**Deviations:** None from PLAN. Efficiency note (not a deviation): the model issued **3 separate `build_sql_query`** calls (historical amounts; max-amount customer; customer city) rather than combining — slightly above the brief's ≈8-tool / ≈10–12-LLM reference (we hit 11 tool / 16 LLM). Still comfortable headroom under 20/20; no action needed. If a future run ever pressed the cap, tightening the prompt's "combine related needs into ONE query" line would be the lever — but it is not warranted now.

**Blockers / risks:** None. Azure spend this stage: **16 LLM calls** (one full run). `T5.4` (web_search live happy-path) **not** retried — the sample query doesn't exercise web_search and the brief marks it optional/non-blocking; DDGS IP-ratelimit risk persists from Stage 2 (env, not code). Partner Name/Email still TODO (open #1) — unrelated, due before Stage 9.

**Next recommended action:** PM gate Stage 6 → open Stage 7 (generalization & anti-leakage hardening: `G1`–`G6`; author a second synthetic DB-only query proving no-code-change generalization, plus the simulated `BadRequestError` content-filter resilience check `G5`).

### 2026-06-18 — PM gate: Stage 6 ✅

**Type:** Handback (PM verification)
**Entry:** PM gated Stage 6 **from the existing artifacts — no re-run of `python hw3.py`** (a re-run would burn ~16 Azure calls; the produced artifacts are authoritative and answer every E1–E4 question). Independently re-derived each number:
- `E1` — `receipt_analysis.log` (2622 B) + `receipt_analysis_result.json` (158 B) both exist; JSON parses; the 5 required keys (`merchant, receipt_total, historical_total, percentage_of_historical, top_customer_city`) present.
- `E2` — ran the shipped validator locally (free, no LLM): `receipt_analysis_answer(<result>)` → **True**. Confirmed tolerances from the validator source (merchant/city case-insensitive exact, monetary ±0.01, pct ±0.05); `1240.3` vs `1240.30` and `7.05` both inside tolerance.
- `E3` — re-counted from the log by grep: **12** main-loop `Calling LLM for next tool to invoke`; **11** `** Entering tool **` dispatches (1 extract_from_image + 3 build_sql_query + 3 execute_sql_query + 3 calculator + 1 write_file) ⇒ `tool_calls = 11`, `llm_calls = 12 + 1 + 3 = 16`. Both under 20/20 — matches the handback exactly.
- `E4` — `grep -ic error` on the log = **0** (no natural error this run); recovery is structurally covered by Stage 4 `C4`, re-confirmed passing in this gate.
- Regression: re-ran the full offline suite → **`92 passed, 3 skipped`** (unchanged — confirms no code drifted at Stage 6). `G1` anti-leakage grep + framework grep on `hw3.py` both clean (no match). `final response is = ` present in the log (dual-write artifact confirmed).
**Reason:** PM verifies by re-deriving from source, not by trusting the handback; and the gate must not spend Azure quota when the artifacts already answer every question (budget rule).
**Impact:** Stage 6 confirmed genuinely clean; handback fully accurate. `PLAN.md` Stage 6 ✅ stands (now PM-gated). Stage 7 (`G1`–`G6`) ready to open **pending Asaf go-ahead** before the execution agent is briefed. Carry-overs unchanged: partner Name/Email (open #1) before Stage 9; MCP bonus go/no-go (open #2) before Stage 8; `T5.4` live web_search still un-retried (sample doesn't use it; DDGS IP-ratelimit is env not code). Process note: the executor pre-flipped Stage 6 to ✅ before this gate — harmless since the gate confirms it, but status flips are the PM's call.

### Stage 7 handback

`[2026-06-18] [Agent] Stage 7 — Generalization & anti-leakage hardening: COMPLETE (G1–G6 all run & pass; one sanctioned code change G5; one authorized live G6 run).`

**What changed:**
- **Written & test-verified** the ONE sanctioned code change `G5` in `hw3.py`: Section 2 import now `from openai import OpenAI, BadRequestError`; the main-loop `create()` (Section 9) is wrapped in `try/except BadRequestError` — on a content-filter/bad-request error it counts the failed attempt (`llm_calls += 1`), appends a `role:"user"` recovery note, and `continue`s the loop; only `BadRequestError` is caught (other exceptions propagate to `main()`); the stale "Stage 7 will wrap this" comment was replaced with the §4.6 rationale. No graded log literal added or altered.
- New file `tests/test_generalization.py` — automated `G1` (authoritative grep + curated-identifier + no-sample-branch source audits), `G2` (no absolute paths + os.path usage), `G3` (fenced SQL strips → executes, standalone and through the loop), `G4` (broken-SQL recovery in the loop), `G5a`/`G5b` (+ a "only BadRequestError is caught" guard), the offline-`G6` plumbing test, and the live-`G6` end-to-end test gated behind `RUN_LIVE=1`.
- No other `hw3.py` edit. Created dev-only `tests/g6_scratch/` (products.db + inventory_summary.txt + input.json + run artifacts) — under `tests/`, already excluded by the Stage 9 allowlist.

**DoD checklist (all written-and-test-verified unless noted):**
- ✅ `G1` — authoritative grep + curated-identifier source audits clean; the `receipt.png`/`orders.db` example-filename call **decided & recorded** (KEPT as generic examples — see audit entry above).
- ✅ `G2` — no hardcoded absolute paths; `os.path`/`os.makedirs` usage confirmed by test.
- ✅ `G3` — fenced ` ```sql ... ``` ` strips to bare SQL and executes against a real tmp DB (returns rows, not an error), both standalone and flowing build→execute inside `run_agent`.
- ✅ `G4` — deliberately broken SQL → `[{"error":...}]` appended back; loop does NOT terminate; corrected query on the next turn returns rows; loop continues to a clean `final`.
- ✅ `G5` — `G5a` (recovers turn 1 → final turn 2; recovery note appended; failed attempt counted, `llm_calls==2`) + `G5b` (persistent filter stops at `LLM_CAP==20`, `** TERMINATED: LLM call cap reached **` logged) both pass; `BadRequestError` caught/surfaced/continued; cap bounds retries; non-BadRequestError still propagates.
- ✅ `G6` — offline plumbing test passes (output filename flows from the scripted query into `write_file`; real DB read confirms revenue=15600 for the 2-row tmp DB); **single live run** matches ground truth with **no code change**.

**QA results (exact counts):**
- `tests/test_generalization.py` offline → **12 passed, 1 skipped** (the skip = live G6).
- Full offline suite → **104 passed, 4 skipped** (the 4 skips = `T2.4`, `T5.4`, `S9` live-gated from earlier stages + new live `G6`).
- Live `G6` (`RUN_LIVE=1 … -k live_g6`) → **1 passed**. Produced `tests/g6_scratch/summary.txt` = `{"category":"Electronics","total_revenue":20600.0,"product_count":3}` — exact ground-truth match (verified by direct SQL beforehand: 1200·5 + 800·12 + 250·20 = 20600.0; 3 Electronics rows). Output filename `summary.txt` ≠ query stem `inventory_summary` (proves the filename is read from the query text, not hardcoded); `inventory_summary.log` written at the stem. Caps: **4 main-loop creates + 1 build_sql_query (LLM-backed) = 5 LLM calls; 3 tool calls** (build_sql_query, execute_sql_query, write_file) — both well under 20/20.
- `G1` grep + framework grep on `hw3.py` re-run after the change → **clean**.

**Decisions made:** (1) G5 catch type / recovery-message role / counting — exactly per brief §4 (catch only `BadRequestError`; `role:"user"` recovery note; count the failed attempt toward `llm_calls`). (2) `receipt.png`/`orders.db` schema examples — **KEPT** as harmless generic examples (rationale in the audit entry). (3) `resolve_log_path` docstring's `receipt_analysis` example — KEPT (the spec's own canonical log-path example, a comment referencing the input query name). All three recorded above.

**Deviations:** None from the brief. The G5 mechanism, the G1 decision, and "no hw3.py change beyond G5" were all pre-specified/recommended by the brief, so nothing required a fresh PM sign-off mid-stage; the decisions are surfaced here per §10.

**Blockers / risks:** None. **Azure spend this stage: exactly 5 LLM calls** (the single live G6 run — under the brief's ~6–8 estimate). `tests/g6_scratch/` left in place as run evidence (dev-only, excluded at Stage 9). Carry-overs unchanged: partner Name/Email (open #1) before Stage 9; MCP go/no-go (open #2) before Stage 8; `T5.4` live web_search still un-retried (env, not code).

**Next recommended action:** PM gate Stage 7 → decide Stage 8 (MCP bonus go/no-go, open #2) vs. proceed to Stage 9 (submission packaging `H1`–`H6`), and resolve partner Name/Email (open #1) needed for `H3`/`H4`.

### 2026-06-18 — PM gate: Stage 7 ✅

**Type:** Handback (PM verification)
**Entry:** PM gated Stage 7 by re-deriving every result independently — zero Azure spend (all PM checks local/offline; the single live G6 run was the executor's, already done).
- **G5 diff audit (read line-by-line):** `from openai import OpenAI, BadRequestError` (line 24); main-loop `create()` wrapped in `try/except BadRequestError` (707–723) → counts the failed attempt (`llm_calls += 1`), appends a `role:"user"` recovery note, `continue`s; only `BadRequestError` caught (others propagate); the success-path `llm_calls += 1` and the entire dispatch/tool-cap block are byte-identical to the Stage 6 code. No graded log literal added or altered; **no change beyond the sanctioned G5 fix.**
- **Tests (re-run by PM):** `tests/test_generalization.py` → `12 passed, 1 skipped`; full offline suite → `104 passed, 4 skipped` (92/3 at Stage 6 + 12 new tests + 1 live-gated skip — arithmetic consistent).
- **G6 (independently re-derived):** direct SQL on the executor's `tests/g6_scratch/products.db` → Electronics revenue `20600.0`, count `3`; produced `summary.txt` = `{"category":"Electronics","total_revenue":20600.0,"product_count":3}` — **exact match**. Output filename `summary.txt` ≠ query stem `inventory_summary` (log = `inventory_summary.log`) → confirms the output name is read from the query TEXT, not derived from `query_name`. G6 log: 4 main creates + 3 dispatches ⇒ `llm=5, tool=3`, well under 20/20. `hw3.py` carries no `products`/`electronics`/`inventory_summary`/`20600` literal (sole grep hit = the word "products" in the calculator description's "sums, differences, products, division" — benign).
- **G1/framework greps:** both clean (exit 1, no match) after the change.
**Reason:** PM verifies by re-deriving; G5 is a code change, so the diff was read directly to confirm scope.
**Impact:** Stage 7 confirmed genuinely clean; handback fully accurate. The live G6 run empirically validates the G1 decision to KEEP `receipt.png`/`orders.db` as illustrative description examples — the run used `products.db`/`inventory_summary` and worked perfectly, so naming the sample files in descriptions does not mislead on a different query. PM concurs with all three executor decisions. `PLAN.md` Stage 7 → ✅. All REQUIRED stages (0–7) are now PM-gated; functional rubric rows (Parts A–E) covered. Remaining before submission: open #1 (partner Name/Email — H3/H4) and open #2 (MCP go/no-go — Stage 8 vs straight to Stage 9 packaging).

### Stage 8 handback

`[2026-06-18] [Agent] Stage 8 — Optional MCP bonus: code + doc + compat all done; live M1 invocation PENDING token in session env.`

**What changed:**
- New file **`hw3_mcp.py`** — standalone MCP client. Uses the `mcp==1.27.1` stdio client (`from mcp import ClientSession, StdioServerParameters`; `from mcp.client.stdio import stdio_client`) to spawn `npx -y @brightdata/mcp`, `initialize()`, `list_tools()`, then `call_tool("search_engine", {"query": "Reichman University"})` and print the flattened result. Reads the token from `BRIGHTDATA_API_TOKEN` (env only, never hardcoded) and passes it to the server as `API_TOKEN`. Exception-safe: missing `mcp` package, missing token, missing Node (`FileNotFoundError` on npx), and any session error each print a clear one-line message and `sys.exit(1)` — no traceback. Does NOT import hw3.py; hw3.py does NOT reference it.
- New file **`mcp_setup.md`** (≤ half a page) — signup, `BRIGHTDATA_API_TOKEN` export (mac/Linux + PowerShell), Node 18+/`npx -y @brightdata/mcp`, `mcp==1.27.1`, exact verify command `python hw3_mcp.py`.
- **`requirements.txt`** — added `mcp==1.27.1` (with a comment noting it's bonus-only and httpx-compatible).
- `hw3.py` byte-unchanged (36955 bytes; only hw3_mcp.py/mcp_setup.md/requirements.txt were written).

**DoD checklist:**
- ⚠️ `M1` — code written & standalone-verified (imports resolve; no-token & independence paths confirmed). **Live connect/list/invoke/print is PENDING** — `BRIGHTDATA_API_TOKEN` is not set in this session's shell, so the only token-gated step couldn't run here.
- ✅ `M2` — `mcp_setup.md` complete and ≤ half a page (signup, env var, verify command, Node + mcp pin).
- ✅ `requirements.txt` has `mcp==1.27.1`; **fresh throwaway-venv re-check PASSED**: `pip install -r requirements.txt` exit 0; `OpenAI(api_key='x', base_url='https://x/')` constructs (openai 1.51.0); `import mcp` OK; **httpx stayed 0.27.2** (no bump → openai untouched).
- ✅ `hw3.py` byte-unchanged; offline suite **104 passed, 4 skipped** (baseline held); framework grep clean.

**QA results:** M2 ✅. M1 ⚠️ (token-gated live run pending). Compat re-check ✅ (fresh venv). Offline suite ✅ 104p/4s. Independence ✅ (no cross-imports). No-token path ✅ (clean message, exit 1). Verified env var = `API_TOKEN`; free-tier base tools include `search_engine`, `scrape_as_markdown`, `discover`. Zero Azure calls this stage.

**Decisions made:** (1) Demo tool = `search_engine` (free-tier base tool) with a benign query; falls back to the first listed tool if `search_engine` isn't exposed. (2) Local env var `BRIGHTDATA_API_TOKEN` mapped to the server's `API_TOKEN` var (confirmed from the @brightdata/mcp docs). (3) `mcp==1.27.1` kept IN the main `requirements.txt` (compat re-check passed, so the PM-anticipated fallback of documenting it only in mcp_setup.md was NOT needed).

**Deviations:** None vs the brief.

**Blockers / risks:** Live M1 is the one open item — needs the token in the session environment. To complete it, Asaf can run `! export BRIGHTDATA_API_TOKEN=<token> && python hw3_mcp.py` in this session (or run it in his own shell) and paste the tool list + result. Bonus is capped-at-100 and must never block Stage 9 — if the live run snags, ship the required submission without it.

**Next recommended action:** Asaf exports `BRIGHTDATA_API_TOKEN` in this session so the live M1 run can be executed and its tool list + result recorded; then PM gates Stage 8 and moves to Stage 9 packaging.

### Stage 8 — live M1 complete

`[2026-06-18] [Agent] M1 live run executed with the token (provided in-session by Asaf).`

**Type:** Verified fact
**Entry:** `python hw3_mcp.py` with `BRIGHTDATA_API_TOKEN` set connected to the Bright Data MCP server and printed:
- **Tools:** `['search_engine', 'scrape_as_markdown', 'search_engine_batch', 'scrape_batch', 'discover']`
- **Tool invoked:** `search_engine` with `{"query": "Reichman University"}`.
- **Result:** a JSON `organic` array of 7 results (top: `https://www.runi.ac.il/en/` "Home | Reichman University"; also Wikipedia, THE rankings, US News, LinkedIn). Bright Data auto-created the `mcp_unlocker`/`mcp_browser` zones on first run.
**Impact:** `M1` ✅ (connect → list → invoke ≥1 → print, standalone, not wired into hw3.py). With `M2` ✅ and the compat re-check ✅, Stage 8 DoD is fully satisfied. Token was passed only via the shell env for this run and is NOT written to any repo file. Stage 8 ready for PM gate → Stage 9 packaging (remember: the bonus must not block Stage 9; H5 allowlist ships `hw3_mcp.py` + `mcp_setup.md` but excludes everything dev-only).

### 2026-06-18 — PM gate: Stage 8 ✅

**Type:** Handback (PM verification)
**Entry:** PM gated Stage 8 by independent re-derivation, including a fresh **live M1 re-run** by the PM (not relying on the executor's run):
- **Live M1 (PM re-ran):** `BRIGHTDATA_API_TOKEN=… python hw3_mcp.py` connected to the Bright Data MCP server, listed `['search_engine','scrape_as_markdown','search_engine_batch','scrape_batch','discover']`, invoked `search_engine("Reichman University")`, and printed a real `organic` JSON array (runi.ac.il, Wikipedia, Facebook, THE, Instagram, …). Independently confirms connect → list → invoke → print.
- **Code audit (`hw3_mcp.py`):** standalone (no `hw3` import; `hw3.py` has no `mcp` reference — grep clean); token read from `BRIGHTDATA_API_TOKEN` env and passed to the server as `API_TOKEN`; never hardcoded; exception-safe (missing token / missing Node / generic error → clean one-line message + `sys.exit(1)`, no traceback).
- **`mcp_setup.md`:** ≤ half a page; covers signup, env-var token, Node 18+/`npx -y @brightdata/mcp`, `mcp==1.27.1`, and the exact verify command. M2 ✅.
- **Compat (PM re-confirmed in the working venv):** `import mcp` ok; `httpx` still `0.27.2`; `OpenAI(...)` still constructs. `requirements.txt` carries `mcp==1.27.1` alongside the openai/duckduckgo/httpx pins.
- **Token containment:** `grep -rIn` for the token value across all `.py`/`.md`/`.txt` → no match. Not in any shipped/source file.
- **Required deliverable untouched:** `hw3.py` byte-unchanged; full offline suite `104 passed, 4 skipped`; framework grep clean.
**Reason:** PM verifies by re-deriving; for a live-connectivity check the only true verification is running it, so the PM ran M1 independently.
**Impact:** Stage 8 confirmed genuinely clean; both `M1` and `M2` satisfied; bonus deliverables ready to ship via the H5 allowlist. `PLAN.md` Stage 8 → ✅. **All stages 0–8 are now PM-gated.** Only open item before Stage 9 packaging: the header **email** (H4). Security note: the Bright Data token is in the chat transcript — Asaf may rotate it in the dashboard (free-tier credential; does not affect the submission since it ships nowhere).

### 2026-06-18 — Stage 9: submission packaged ✅ (PROJECT COMPLETE)

**Type:** Handback (PM-executed at Asaf's instruction "finish stage 9" — clerical packaging, not production logic)
**Entry:**
- **H4 header:** `hw3.py` header carries Name `Asaf Ramati` / ID `209252154` / Email `asaf.ramati@post.runi.ac.il` (verified content + file integrity).
- **H3 `partners.txt`:** created → `Asaf Ramati, 209252154`.
- **H1 deps:** every non-stdlib import pinned — `openai==1.51.0`, `duckduckgo-search==6.2.10`, `httpx==0.27.2`, `mcp==1.27.1` (hw3.py: openai + duckduckgo_search; hw3_mcp.py: mcp).
- **H5/H6 ZIP:** `hw3_209252154.zip` built from the explicit 7-file allowlist (`hw3.py`, `requirements.txt`, `partners.txt`, `receipt_analysis.log`, `receipt_analysis_result.json`, `hw3_mcp.py`, `mcp_setup.md`) — never `zip -r .`. Listing confirms exactly those 7; no gist/tests/Reference/HW3.pdf/working-`.md`/db/png.
- **H2 fresh-venv proof:** unzipped into `/tmp/h2check`; `pip install -r requirements.txt` exit 0 (resolved openai 1.51.0 / httpx 0.27.2 / mcp 1.27.1); `import hw3` constructs the OpenAI client (httpx compat holds in a clean env); `python hw3.py` with no `input.json` prints a clean `Error: ... 'input.json' not found` (no traceback — exception-safe, exactly as the grader invokes it); `import mcp` OK.
- **Regression:** offline suite `104 passed, 4 skipped`; G1 anti-leakage + framework greps on `hw3.py` clean.
**Decisions / notes:** (1) Did NOT regenerate the sample `.log`/`_result.json` — the Stage-6 validated artifacts faithfully represent the shipped code's sample behavior (G5 is a no-op on the clean path; header/banner edits are comments), so regenerating would spend ~16 Azure calls for no change. (2) The `# === Section N ===` banner comments were trimmed from `hw3.py` (direct edit / formatter) — cosmetic only; docstrings + `# ---- 4.x` sub-headers remain and the file is functionally verified (import OK, suite 104/4). Flagged to Asaf; restore optional.
**Impact:** **All checks H1–H6 pass. Project complete.** `hw3_209252154.zip` is ready to submit to Moodle. `PLAN.md` Stage 9 → ✅; project marked complete.
