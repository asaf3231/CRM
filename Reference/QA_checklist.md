# QA_checklist.md — Test-Driven-Development Blueprint

Project: **HW3 — Tool-Calling Agent**
Maintained by: Asaf

> This file is the verification contract for the project. `CLAUDE.md` defines the rules, `PLAN.md` tracks the stages, `NOTES.md` records decisions. **Every stage in `PLAN.md` lists the check IDs below as its Definition of Done.** A stage is not "done" until its referenced checks pass.
>
> Checks are written **before** the matching `hw3.py` section (test-first). Each check has a stable ID (e.g. `T1`, `C3`, `D2`) so `PLAN.md` can reference it without ambiguity.

---

## §1. Test harness, environment & fixtures

How the suite runs and what it depends on.

| ID | Check | Method | Pass condition |
|---|---|---|---|
| `E0` | Gist files present | Run `python prepare_dataset.py` once at the repo root | Confirmation that all 8 required files were found |
| `ENV1` | Pinned deps install in a fresh venv | `python -m venv .venv && pip install -r requirements.txt` | Exit 0; `openai==1.51.0` and `duckduckgo-search==6.2.10` resolved |
| `ENV2` | Imports resolve | `python -c "import openai, duckduckgo_search, sqlite3, ast, base64, json"` | No ImportError; `from duckduckgo_search import DDGS` works |
| `ENV3` | Client connectivity smoke test | One minimal `client.chat.completions.create` (tiny prompt, no tools) | Returns a message; confirms key/endpoint/deployment are live |

**Harness conventions**

- Tests live in `tests/` (e.g. `tests/test_tools.py`, `tests/test_loop.py`); dev-only, never shipped.
- `pytest` is the runner if available; otherwise plain `assert` scripts. Either is acceptable.
- **No live LLM/network calls in unit tests by default.** Use the fakes below. Live calls are isolated, marked, and run sparingly to protect the shared Azure quota.

**Shared fixtures**

- `tmp_orders_db` — a temp SQLite file with a small known `orders` table, built in-test (not the gist db) so assertions are independent of sample data.
- `tmp_image` — a tiny PNG written to a temp path for `extract_from_image` byte/mime tests.
- `FakeLLMClient` — a stand-in `client` whose `.chat.completions.create(...)` returns scripted responses (with/without `tool_calls`) from a queue. Used for loop, cap, and logging tests.
- `MockToolLLM` — a callable patched into `extract_from_image` / `build_sql_query` to return canned text without a network call.

---

## §2. Tool unit tests (graded in isolation — Part A, 18 pts)

Each tool is tested standalone. Negative cases matter as much as happy paths.

### `T1` — calculator (safe eval)
- `T1.1` Arithmetic: `calculator("(45.20 + 12.50) / 100")` → `"0.577"` (value correct as a string).
- `T1.2` Functions: `sqrt`, `log`, `abs`, `round`, `min`, `max`, and `**` all evaluate (e.g. `round(sqrt(2300), 4)`).
- `T1.3` **No raw eval:** `__import__('os')`, `open('x')`, `os.system('...')`, attribute access, and bare names are **rejected** (raise/return error), never executed. This is the rule from `CLAUDE.md` §4.5.
- `T1.4` Whitelist walker: only `ast.Expression`/`BinOp`/`UnaryOp`/`Call`(whitelisted names)/numeric constants pass; subscripts, comprehensions, lambdas rejected.
- `T1.5` Result type is always `str`.

### `T2` — extract_from_image
- `T2.1` (mocked) Given a fake vision response of the documented JSON, returns a dict with keys `merchant`, `date`, `total`, `items` (list of `{name, price}`).
- `T2.2` Base64 + mime: reads bytes from the path and encodes them; mime derived from extension (`.png`/`.jpg`/`.jpeg`).
- `T2.3` Robust parse: if the model wraps JSON in prose or fences, parsing still yields the dict (or a clean error), never an uncaught exception.
- `T2.4` (live, guarded) One real call on `receipt.png` (at the repo root) returns `merchant ≈ "Blue Moon Cafe"`, `total ≈ 87.45` — sanity only, not shipped logic.
- `T2.5` Accounting hook: the function is on the "+1 LLM" list (verified in `C3`).

### `T3` — build_sql_query
- `T3.1` (mocked) Returns a bare SQL string.
- `T3.2` **Fence stripping:** mocked output ` ```sql\nSELECT ...\n``` ` and ` ```\nSELECT...\n``` ` both return the inner SQL with no fences/backticks (`CLAUDE.md` §4.5).
- `T3.3` Returns SQL only — no execution, no DB access inside this tool.
- `T3.4` Prompt contains the "ONLY the SQL query, no markdown, no explanation" instruction.

### `T4` — execute_sql_query (read-only)
- `T4.1` `SELECT` against `tmp_orders_db` returns `list[dict]` keyed by column name.
- `T4.2` **Read-only:** an `INSERT`/`UPDATE`/`CREATE`/`DELETE` returns `[{"error": ...}]` (write blocked by `?mode=ro`), and the db file is unchanged on disk.
- `T4.3` Invalid SQL (`SELECT * FROM nope`) returns `[{"error": ...}]`, does not raise.
- `T4.4` Connection uses exactly `sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)`.
- `T4.5` No LLM call (verified in `C3`).

### `T5` — web_search
- `T5.1` (mocked DDGS) Returns a `list[dict]` of length ≤ 3, each with exactly `title`, `snippet`, `url`.
- `T5.2` Field mapping: the library's native fields are mapped to those three keys.
- `T5.3` Failure handling: a DDGS exception/timeout returns a defined shape (record the chosen shape in `NOTES.md`), never an uncaught exception.
- `T5.4` (live, guarded) One real query returns ≤ 3 well-formed results.

### `T6` — write_file
- `T6.1` Writes `file_content` to `file_name`; file exists with exact content.
- `T6.2` Creates missing parent directories (`subdir/deep/out.json`).
- `T6.3` Returns exactly `"Wrote N bytes to <file_name>"` with `N == len(file_content.encode("utf-8"))`.
- `T6.4` No LLM call.

---

## §3. Tool-schema checks (Part B, 8 pts)

| ID | Check | Pass condition |
|---|---|---|
| `S0` | Exactly 6 schemas | `len(TOOL_SCHEMAS) == 6`; names == the 6 function names == `TOOL_DISPATCH` keys |
| `S1`–`S6` | Per-tool schema well-formed | Each is `{"type":"function","function":{name, description, parameters}}`; `parameters` lists `properties` with `type`, and a correct `required` array |
| `S7` | Required fields correct | `calculator.expression`, `extract_from_image.image_path`, `build_sql_query.{natural_language,schema_description}`, `execute_sql_query.{sql,db_path}`, `web_search.query`, `write_file.{file_content,file_name}` all required |
| `S8` | Descriptions steer the model | Each `description` states *when to use* the tool; `build_sql_query` says "pair with execute_sql_query, does NOT run"; `web_search` says "only for facts not in the resources"; no vague "does math" text |
| `S9` | Schemas accepted by the API | `create(..., tools=TOOL_SCHEMAS)` does not 400 on a smoke call |

---

## §4. Loop & dispatch checks (Part A, 8 pts)

Driven by `FakeLLMClient`.

| ID | Check | Pass condition |
|---|---|---|
| `L1` | Raw API shape | Loop calls `create(..., tools=..., tool_choice="auto")` and reads `response.choices[0].message.tool_calls` — no framework wrapper |
| `L2` | Dispatch by name | A scripted `tool_calls` request routes to the right `TOOL_DISPATCH` entry with `json.loads(arguments)` unpacked as kwargs |
| `L3` | tool_call_id plumbing | Each tool reply is `{"role":"tool","tool_call_id": tc.id, "content": json.dumps(result, default=str)}`; ids match 1:1 |
| `L4` | Message ordering invariant | Every assistant `tool_call` gets exactly one tool reply before the next `create`; multi-tool-call turns handled |
| `L5` | No-framework grep | `grep -Ei "langgraph|langchain|create_react_agent|AgentExecutor|bind_tools"` over `hw3.py` returns nothing (`CLAUDE.md` §4.1) |

---

## §5. Cap-accounting & termination simulation (Part A, 6 pts)

The "20-call cap" strategy. Use `FakeLLMClient` to script deterministic sequences.

| ID | Check | Method | Pass condition |
|---|---|---|---|
| `C1` | LLM cap fires | Fake client that **always** returns a tool call (never stops) | Loop exits after 20 LLM calls; logs `** TERMINATED: LLM call cap reached **`; counters stop at the cap |
| `C2` | Tool cap fires | Fake client returning many tool calls per turn so `tool_calls` reaches 20 first | Loop exits; logs `** TERMINATED: tool call cap reached **`; stops mid-turn at call 21 (no 21st dispatch) |
| `C3` | Tool-internal LLM increment | Script a self-consistent `FakeLLMClient` sequence dispatching `extract_from_image` and/or `build_sql_query` plus non-LLM tools, ending in a final no-tool turn | Counters equal the hand-computed expectation: **+1 LLM per main `create()`**, **+1 extra LLM** for each `extract_from_image`/`build_sql_query` dispatched, **+1 tool per dispatch**, +0 LLM for the other four tools. (The PDF's `8 + 1 + 2 ⇒ llm=11, tool=3` in `CLAUDE.md` §4.3 is illustrative formula arithmetic, not a single runnable trace — a tool-less turn ends the loop, so 8 creates can't coexist with only 3 dispatches.) |
| `C4` | Termination precedence | Construct cases where a cap and a final message could both apply | Cap checked **before** the no-tool-call exit; tool errors never terminate; order matches `CLAUDE.md` §8 |
| `C5` | Clean stop | Fake client returns no `tool_calls` | Loop logs `final response is = <content>` and exits without hitting a cap |

---

## §6. Logging-compliance checks (Part D, 6 pts)

Capture stdout and read the log file; assert byte-exact literals.

| ID | Check | Pass condition |
|---|---|---|
| `D1` | Exact literals | `Calling LLM for next tool to invoke`, `** Entering tool <name> **`, `** Exiting tool <name> **`, and exactly one of the three terminal lines appear verbatim (case + whitespace) |
| `D2` | Dual write | Every required line appears in **both** stdout and the `.log` file (both flushed) |
| `D3` | Parameter truncation | `Parameter <p> = <≤50 chars>`; values >50 chars are cut to 50 + `...`; values ≤50 chars have no trailing `...` |
| `D4` | Log path / stem / subdir | Log file is `os.path.splitext(query_name)[0] + ".log"`; subdir preserved (`query1/x.txt → query1/x.log`); parent dir created |

---

## §7. Prompt & I/O checks (Part B + Part D)

| ID | Check | Pass condition |
|---|---|---|
| `P1` | System prompt quality | Establishes role, the 6 tools, which tool to prefer per sub-problem, and the "write the output file then stop with no tool call" rule (Part B, 4 pts) |
| `P2` | User-message construction | Initial user message includes **both** the query text **and** the resource list (file names + descriptions) (Part B, 3 pts) |
| `P3` | input.json parsing | Reads `query_name` + `resources[]`; resolves `query_name` relative to cwd (incl. subdir); reads the query text from that file; clear error if `input.json` is malformed |
| `P4` | Output obeys the query | The output filename/shape is taken from the **query text** at runtime and produced via `write_file` — never hardcoded (ties to `G1`) |

---

## §8. End-to-end sample-query check (Part C signal)

Run `python hw3.py` against the gist sample (in a scratch dir, not the submission).

| ID | Check | Pass condition |
|---|---|---|
| `E1` | Artifacts produced | `receipt_analysis.log` and `receipt_analysis_result.json` both exist; the JSON parses |
| `E2` | Validator values match | Output equals `{"merchant":"Blue Moon Cafe","receipt_total":87.45,"historical_total":1240.30,"percentage_of_historical":7.05,"top_customer_city":"Haifa"}` within the validator's tolerances |
| `E3` | Within caps | The run stays under 20/20 with headroom (reference run ≈ 8 tool calls, ≈ 10–12 LLM calls) |
| `E4` | Recovery works | If a `build_sql_query` produces unusable SQL, the loop recovers by re-calling — it does not terminate on the tool error |

> `E1`/`E2` exercise the wiring, but they must be implemented **generically** — passing them must come from runtime reasoning, not from hardcoding (see `G1`).

---

## §9. Generalization & anti-leakage audit (the most important correctness gate)

| ID | Check | Method | Pass condition |
|---|---|---|---|
| `G1` | No hardcoded sample data | `grep -Ei "blue moon|87\.45|1240\.3|haifa|receipt_analysis_result|orders\(|customers\(" hw3.py` | No business hits; only generic tool/loop code (`CLAUDE.md` §4.2) |
| `G2` | OS-agnostic paths | grep for absolute paths / `C:\\` / leading `/Users`; check `os.path`/`pathlib` usage | No hardcoded absolute paths; everything relative to cwd |
| `G3` | SQL fence stripping (defensive) | Re-run `T3.2` in an integration context | Fenced SQL still executes after `build_sql_query` |
| `G4` | Tool-error recovery | Feed a deliberately broken SQL via the loop | `[{"error":...}]` is appended back, the LLM retries, loop continues |
| `G5` | Content-filter resilience | Simulate a `BadRequestError` from the client | Caught, message surfaced back to the LLM, loop continues; cap still applies |
| `G6` | Second synthetic query | Author a *different* query (e.g. DB-only lookup writing `summary.txt`) and run end-to-end | Correct output file produced with no code changes |

---

## §10. Submission-hygiene checks (Part E, 5 pts)

| ID | Check | Pass condition |
|---|---|---|
| `H1` | requirements pinned | Every non-stdlib import is in `requirements.txt` with `==`; includes `openai==1.51.0`, `duckduckgo-search==6.2.10` |
| `H2` | Fresh-venv run | `pip install -r requirements.txt && python hw3.py` succeeds in a clean venv (re-run of `ENV1` on the final tree) |
| `H3` | partners.txt | Present; one line per student `<Full Name>, <ID>` (required even solo) |
| `H4` | Header block | `hw3.py` top comment has each partner's `# Name`, `# ID`, `# Email` |
| `H5` | No gist files shipped | ZIP is built from an explicit allowlist and excludes `input.json`, the query/validator files, `receipt.png`, `*.db`, `prepare_dataset.py`, `README.md`, plus `tests/`, `Reference/`, `HW3.pdf`, and the PM/`.md` working files |
| `H6` | ZIP naming | `hw3_<ID>.zip` (solo) or `hw3_<ID1>_<ID2>.zip` (pair) |

---

## §11. Bonus — MCP showcase (+5, optional)

| ID | Check | Pass condition |
|---|---|---|
| `M1` | hw3_mcp.py runs standalone | Connects to a Bright Data MCP server, lists tools, invokes ≥1, prints the result; not wired into the main agent |
| `M2` | mcp_setup.md complete | ≤ half a page: free-tier signup, `BRIGHTDATA_API_TOKEN` placement, and the exact verify command; notes Node 18+/`npx -y @brightdata/mcp` and `mcp==1.27.1` |

---

## Check-to-rubric map (sanity)

| Rubric part | Points | Checks |
|---|---:|---|
| A — tools implemented | 18 | `T1`–`T6` |
| A — raw loop, no framework | 8 | `L1`, `L5` |
| A — cap enforcement | 6 | `C1`–`C5` |
| A — dispatch correctness | 8 | `L2`–`L4` |
| B — schemas | 8 | `S0`–`S9` |
| B — system prompt | 4 | `P1` |
| B — user message | 3 | `P2` |
| C — correctness | 30 | `E1`–`E4`, `G1`, `G6` |
| D — logging | 6 | `D1`–`D4` |
| D — output files | 4 | `E1`, `P4` |
| E — hygiene | 5 | `H1`–`H6` |
| Bonus — MCP | +5 | `M1`, `M2` |
