# QA_checklist.md — Test-Driven-Development Blueprint

Project: **Autonomous Agentic GTM Engine & Value-Hook Pipeline** (ReactFirst AI Proactive Outbound Engine)
Maintained by: Asaf

> This file is the verification contract for the project. `CLAUDE.md` defines the rules, `PLAN.md` tracks the stages, `NOTES.md` records decisions. **Every stage in `PLAN.md` lists the check IDs below as its Definition of Done.** A stage is not "done" until its referenced checks pass — *run, not inspected*.
>
> Checks are written **before** the matching code (test-first). Each check has a stable ID (e.g. `T4`, `AG2`, `RS3`) so `PLAN.md` can reference it without ambiguity.

---

## §0. Test harness, environment & fixtures

How the suite runs and what it depends on.

| ID | Check | Method | Pass condition |
|---|---|---|---|
| `ENV1` | Fresh-venv install | `python -m venv .venv && pip install -r requirements.txt` | Exit 0; pins resolve (`anthropic`, `chromadb==0.5.5`, `sentence-transformers==3.0.1`, `mongomock==4.1.2`, `pandas==2.2.2`, `firecrawl-py`, `google-search-results`, `tavily-python`) |
| `ENV2` | Every import is pinned | grep each non-stdlib import against `requirements.txt`; assert each has a `==` | No imported module is unpinned (anthropic + firecrawl + serpapi + tavily pinned at Stage 1 install). No `openai`/`google-genai` import present (provider is Claude) |
| `ENV3` | Clients reachable (gated, sparing) | One minimal `anthropic` `messages.create` + one call per configured external service | Each configured client returns a response; missing-key services explicitly SKIPPED, not failed |
| `ENV4` | **Import-safety** | `python -c "import main, lead_store, rag_engine"` with **no** network and **none** of the three input files present | Exit 0; **zero** side effects (no client built, no model download, no Chroma build, no `get_lead_data_collection()` execution, no file write). The single most important environment check |

**Harness conventions**

- Tests live in `tests/` (`tests/test_tools.py`, `tests/test_loop.py`, `tests/test_policies.py`, `tests/test_rag.py`, `tests/test_lead_store.py`); dev-only, never shipped.
- `pytest` if available; otherwise plain `assert` scripts.
- **No live LLM / network / crawl calls in unit tests by default.** Use the fakes below. Live calls are isolated, marked, and run sparingly.

**Shared fixtures**

- `tmp_catalog_csv` — a small, schema-valid `brands_catalog.csv` with the 9 columns, a mix of `Tier 1`/non-Tier-1 rows, incident counts straddling 5 (Policy 3), and at least one `Blacklisted` row.
- `tmp_contacts_json` — a small `contacts.json` matching the PRD §2.2 schema, with at least one record carrying a known `corporate_access_key` and one with `opt_out_status=True`.
- `tmp_policies_txt` — a `gtm_policies.txt` containing the six numbered policies.
- `FakeReasoningClient` — stand-in for the `anthropic` client; `.messages.create(...)` returns scripted `Message`-shaped responses (content with/without `tool_use` blocks; `stop_reason` ∈ `end_turn`/`tool_use`/`refusal`) from a queue; can be set to raise `anthropic.BadRequestError` or return `stop_reason="refusal"` on a chosen turn (for `RS1`).
- `MockVectorA` (Claude `web_search`/`web_fetch`), `MockSerp`, `MockTavily`, `MockFirecrawl`, `MockReactFirst`, `MockSlack` — patched into the fan-out / crawler / PDF / webhook paths to return canned payloads with no network.
- `tmp_chroma` — a throwaway Chroma persist dir seeded with a tiny known crisis-case-study corpus (for RRF tests).
- `seeded_lead_store` — `get_lead_data_collection()` pointed at `tmp_contacts_json`, with a known good/bad `corporate_access_key`.

---

## §1. Tool unit tests (each tool graded in isolation)

Negative cases matter as much as happy paths.

### `T1` — generate_search_queries(vertical_seed, target_count=15)
- `T1.1` (mocked Claude / `LIGHT_MODEL`) Returns a `list[str]`; **10–20** entries by default; all non-empty, unique after de-dup.
- `T1.2` Variation **matrix**, not repetition: the output spans more than one intent/modifier axis (distinct, non-overlapping stems), not N near-copies of the seed.
- `T1.3` `target_count` honored (default `DEFAULT_QUERY_COUNT = 15`); `required: ["vertical_seed"]`.
- `T1.4` Robust parse: model output wrapped in prose/fences/JSON still yields a clean list (or a clean error), never an uncaught exception.

### `T2` — execute_3way_fanout(queries)
- `T2.1` (mocked A+B) Vectors A and B run **concurrently** (`concurrent.futures`); both contribute to the pooled result.
- `T2.2` **Recovery rule (exact):** when A∪B yields `< FANOUT_RECOVERY_THRESHOLD (=2)` distinct domains, Vector C (Tavily) **is** invoked; when A∪B yields `≥ 2`, Vector C is **not** invoked. Both branches asserted with a call-spy.
- `T2.3` Vector isolation: if Vector A raises, B (and C if triggered) still return; the tool returns partial results with a per-vector status, never crashes.
- `T2.4` Output shape: a dict with the pooled domains + provenance (which vector found each); domains normalized (lowercase, scheme/`www` stripped).
- `T2.5` (live, guarded) One real fan-out for a benign seed returns ≥1 domain — sanity only.

### `T3` — extract_and_score_pool()
- `T3.1` De-dup: duplicate domains across vectors collapse to one entry (normalized `Primary_Domain`).
- `T3.2` Catalog mapping: a candidate whose domain matches `brands_catalog.csv` is annotated with its 9-column context (by name, not index).
- `T3.3` Non-catalog candidates are retained and flagged `in_catalog=False` (not dropped).
- `T3.4` Scoring is deterministic for a fixed input pool (no hidden randomness); ordering stable.

### `T4` — analyze_company_chunk(domains)
- `T4.1` (mocked Firecrawl) Returns one profile per input domain with explicit `tiktok_pixel: bool`, `meta_pixel: bool`, **and `gtm: bool`** (Google Tag Manager).
- `T4.2` **Size ceiling:** given >100 domains, the tool processes **at most 100** in the chunk (excess deferred/rejected, documented behavior) — never silently crawls all.
- `T4.3` **Time budget:** with a mocked slow crawler exceeding 800s wall-clock, the tool returns **partial** results flagged `timed_out=True` and does **not** raise.
- `T4.4` Pixel/tag detection: a page whose markup contains the TikTok / Meta / GTM signatures (recorded in `NOTES.md`) sets the respective boolean; absence sets it `False`.
- `T4.5` A single domain's crawl failure is isolated to that domain's record (`{"error": ...}`), not the whole chunk.

### `T5` — evaluate_icp_tags(company_profile_data: str)
- `T5.1` Pure / no network: deterministic for a fixed profile **string** (raw crawl text + technical metadata).
- `T5.2` **Qualification rule (exact):** `qualified == True` **iff** matched-tag count `>= ICP_TAG_THRESHOLD (=3)`. Tested at 2 (fail), 3 (pass), 4 (pass).
- `T5.3` Returns the matched tag list and the integer count for auditability.
- `T5.4` Malformed/empty profile → `qualified=False` with a clean reason, never an exception.

### `T6` — match_solicitation_angle(scraped_narrative_context, category_path)  → see also §5
- `T6.1` (seeded Chroma) Returns `{"angle_key", "tier", "scores"}`; `tier ∈ {1,2,3,4}`.
- `T6.2` **Hybrid:** both a semantic (Chroma / all-MiniLM-L6-v2) ranked list and a BM25 ranked list are produced and **fused via RRF** (not one or the other).
- `T6.3` RRF correctness: for a hand-constructed pair of ranked lists, the fused order matches the hand-computed RRF scores (`1/(k+rank)` summed; `k` recorded in `NOTES.md`).
- `T6.4` Tier mapping: fused top score maps to the documented tier thresholds (Tier 1 Critical Fit … Tier 4 No Match) — boundary values tested.
- `T6.5` **Tier 4 = No Match** routes to the Policy 6 fallback at the output boundary (cross-check with `FB2`).

### `T7` — request_reactfirst_pdf(target_domain, validated_angle_key, calculated_risk_score)
- `T7.1` (mocked API) Saves a file under `assets/`; returns `{"path", "ok": True}`.
- `T7.2` The saved file passes the gateway PDF-health check (`%PDF-` header, non-zero length, EOF marker) — cross-check `GW4`.
- `T7.3` Inputs are gateway-validated first: a null domain / malformed `angle_key` / non-numeric risk score is rejected **before** any outbound call (cross-check `GW2`).
- `T7.4` This is the **only** tool that targets `outreach.reactfirst.ai` (cross-check `INT1`).
- `T7.5` API failure → `{"ok": False, "error": ...}`, no partial/corrupt file left in `assets/`, no raise.

### `T8` — secured_calculator(expression)
- `T8.1` SOP smoke (PRD §7): `secured_calculator("(1700 + 450) * 1.15")` evaluates correctly; result is a `str`.
- `T8.2` **Whitelist is exactly `Add, Sub, Mult, Div, USub`** + numeric constants + grouping. `**`/Pow, function calls, names, attributes, subscripts, comprehensions, lambdas are **rejected with `ValueError`** ("Unauthorized mathematical syntax block: ...").
- `T8.3` **No raw eval:** `__import__('os')`, `open('x')`, `os.system('...')`, attribute access, bare names all raise — never executed.
- `T8.4` Uses `ast.Constant` (not deprecated `ast.Num`) so it works on Py≥3.12; the whitelist is **not** widened in the process.
- `T8.5` Grep: no `eval(`/`exec(` token anywhere in the codebase (cross-check `G1`).

---

## §2. Catalog compliance (the 9-column schema)

| ID | Check | Pass condition |
|---|---|---|
| `CAT1` | Header validated on load | Exactly the 9 named columns; a missing/renamed/extra column → clean explicit startup error (not a later `KeyError`). **The real CSV header is authoritative.** |
| `CAT2` | Access by name (pandas) | grep shows no positional catalog access (`.iloc[:, <int>]` / `row[<int>]`) on catalog rows |
| `CAT3` | Typed reads + enums | `Historical_Social_Incidents` coerced to `int`; `Estimated_Ad_Spend_Tier`∈{Tier 1/2/3}; `Current_Status`∈{Active_Client/Open_Opportunity/Unreached_Prospect/Blacklisted}; coercion failure surfaced |
| `CAT4` | `Main_Competitor_Id` spelling matches the file | Code references the column exactly as the real header spells it (PRD: `Main_Competitor_Id`); not silently rewritten. `CAT1` is the tiebreaker for `_Id` vs `_ld` |
| `CAT5` | No catalog values hardcoded | grep: no brand name / domain / GTIN / competitor id / tier literal from a real catalog appears in code or a prompt (Policy 1) |
| `CAT6` | `Blacklisted` excluded | A `Blacklisted` brand is never surfaced as an outreach target |

---

## §3. Tool-schema & dispatch checks

| ID | Check | Pass condition |
|---|---|---|
| `S0` | Exactly 8 schemas | `len(TOOL_SCHEMAS) == 8`; names == the 8 function names == `TOOL_DISPATCH` keys (three-way match, import-time `assert`) |
| `S1`–`S8` | Per-tool schema well-formed (Anthropic shape) | Each is `{"name", "description", "input_schema": {...}}` (Anthropic tool format, **not** the OpenAI `{"type":"function",...}` wrapper); `input_schema` lists typed `properties` and a correct `required` array |
| `S9` | Descriptions steer the model | Each `description` states *when to use* the tool and its key constraint (e.g. tool 2 "Vector C only if A+B < 2 domains"; tool 8 "no eval"); no vague text |
| `S10` | Schemas accepted by the API | `client.messages.create(..., tools=TOOL_SCHEMAS, max_tokens=...)` does not 400 on a smoke call (gated) |

---

## §4. Agentic loop, anti-loop cap & resiliency

Driven by `FakeReasoningClient`.

| ID | Check | Method | Pass condition |
|---|---|---|---|
| `L1` | Raw API shape (Anthropic) | Scripted run | Loop calls `client.messages.create(..., tools=...)` and iterates `response.content` for `tool_use` blocks / reads `stop_reason`; no framework or SDK-tool-runner wrapper |
| `L2` | Dispatch by name | Scripted `tool_use` | Routes to the right `TOOL_DISPATCH` entry with the `tool_use.input` dict as kwargs |
| `L3` | tool_use_id plumbing | Scripted multi-tool turn | Assistant turn (full `content`) is appended, then a user turn of `{"type":"tool_result","tool_use_id":<id>,...}` blocks; ids 1:1; every `tool_use` answered before the next `create` |
| `L4` | Gateway on every outbound | Spy on the gateway | No outbound payload (PDF / output / subdomain) leaves without passing `gateway_validate` |
| `L5` | No-framework grep | `grep -Ei "langgraph\|langchain\|create_react_agent\|AgentExecutor\|tool_runner\|beta_tool"` over all `.py` | No hits (manual loop only) |
| `RS1` | Refusal / bad-request resilience | `FakeReasoningClient` raises `anthropic.BadRequestError` on one turn and returns `stop_reason="refusal"` on another | Both caught; `stop_reason` checked **before** reading `content`; message surfaced back; loop continues; cap still applies |
| `RS2` | **Anti-loop cap fires** | Fake client that **never** stops requesting tools | Loop exits after **15** tool calls into a **safe error state** (PRD §5.3); **no 16th dispatch**; the convention `** TERMINATED: tool call cap reached **` line is emitted |
| `RS3` | Tool error ≠ crash | A tool returns `{"error": ...}` | Appended back; loop continues; no termination on tool error |
| `RS4` | Call-logging metrics | Any run | Per-tool counts + total tracked; total never exceeds 15; metrics written to log + result |
| `RS5` | No uncaught exceptions | Inject a raising tool / bad args | `main()` and the loop never propagate an exception; clean structured failure instead |

---

## §5. Hybrid RAG / RRF angle engine (`rag_engine.py`)

| ID | Check | Pass condition |
|---|---|---|
| `RAG1` | Lazy local store | Chroma collection is built **on first use**, not at import; persists under `.chroma/` (`ENV4` cross-check) |
| `RAG2` | Embedding model | Uses `all-MiniLM-L6-v2` (`EMBED_MODEL`); vectors have the model's documented dimensionality |
| `RAG3` | BM25 exact path | The exact-string/BM25 ranker returns a ranked list independent of the semantic one |
| `RAG4` | RRF fusion math | For known input rankings, fused scores equal `Σ 1/(k+rank)`; the chosen `k` is recorded in `NOTES.md`; tie-breaking deterministic |
| `RAG5` | Tier classification | Fused result maps to Tier 1 Critical Fit / Tier 2 / Tier 3 / Tier 4 No Match per the `NOTES.md` thresholds; boundaries tested |

---

## §6. Policy enforcement (governance contracts)

### Policy 1 — Authoritative Context Bound
- `POL1` System prompt + design forbid asserting any brand market-position/tier/competitor fact not present in `brands_catalog.csv`; catalog facts are retrieved/quoted, not generated (cross-check `CAT5`, `G2`).

### Policy 2 — ICP Validation Threshold
- `POL2` The only qualification gate is `evaluate_icp_tags` returning `count >= 3` (cross-check `T5.2`); no other path can mark a brand qualified.

### Policy 4 — Data Protection & Authentication Gate (`lead_store.py`)
- `AG1` Extracting a contact record (or reading its `interaction_history_count`) **without** a `corporate_access_key` returns a structured `{"error":"unauthorized"}` and **zero** record fields.
- `AG2` A **wrong** key is denied identically to **no** key (generic denial; no existence oracle).
- `AG3` The **valid** key (matched against the record's `corporate_access_key` field) returns the record.
- `AG4` Schema conformance (SOP): `get_lead_data_collection()` returns records whose keys map directly to the PRD §2.2 layout, original keys unaltered.
- `AG5` The `corporate_access_key` value never appears in any return value, log line, or error message.
- `AG6` The gate is the single chokepoint: no code path reaches the `contacts` collection around it (grep + design check). `opt_out_status=True` contacts are suppressed from outbound.

### Policy 3 — Premium Pricing / Risk Tier Loop  — **RESTORED** (Asaf, 2026-06-18)
- `PR1` Eligibility: a `Tier 1` brand is flagged enterprise-SLA / premium-eligible; a non-`Tier 1` brand is not (driven by `Estimated_Ad_Spend_Tier` from the CSV, never invented — `POL1` cross-check).
- `PR2` Multiplier trigger (exact, boundary-tested): `Historical_Social_Incidents > INCIDENT_PREMIUM_THRESHOLD (=5)` ⇒ the 15% premium applies; at `== 5` and `< 5` it does **not** (strictly greater than 5).
- `PR3` Computed via `secured_calculator` only: `base * PREMIUM_MULTIPLIER (=1.15)` evaluates correctly through the AST walker; **no raw `eval`/`exec`** on the pricing path (`T8.*`/`G1` cross-check).
- `PR4` (integration) A Q1-style query ("…ad spend tier is Tier 1… 6 incidents… premium estimation tier?") routes authenticate → `get_lead_data_collection` → `secured_calculator` and reports the premium tier; the tier/incident facts derive solely from the catalog/record (Policy 1).

### Policy 5 — Output Suggestions Ceiling
- `CL1` A run that could yield >3 angles emits **exactly 3** when no count is requested.
- `CL2` A request for "top 5" (or any N>3, e.g. Q5) is **capped to exactly 3**; the run does not error and does not return >3; an override flag is recorded.
- `CL3` A request for a **specific subset ≤3** (e.g. "top 2 items") returns **exactly that count** — no padding to 3.
- `CL4` Net rule `min(requested or 3, 3)` is enforced at the **output boundary** (gateway) so no upstream path can exceed 3 (`GW5` cross-check).

### Trust-Gated Autonomy (human-in-the-loop)
- `TG1` A **borderline** prospect (exactly 3 ICP tags + low secondary indicators) is **not** auto-emailed; it is routed to the Slack webhook (mocked) for human approval; clear-cut prospects proceed.
- `TG2` The Slack webhook URL is an env secret; routing is logged without leaking it.

### Policy 6 — Strict String Fallback
- `FB1` `FALLBACK_MESSAGE` is the byte-exact constant `We have no product available today that fits your request` (no trailing whitespace/punctuation).
- `FB2` Zero qualifying matches (all leads fail `evaluate_icp_tags`, or all map to Tier 4) ⇒ output is **exactly** the fallback string and **nothing else** — no JSON wrapper, no LLM prose.
- `FB3` (integration) A no-match seed driven end to end yields only the fallback string in the result.
- `FB4` (integration) A forced stage-validation failure yields only the fallback string — the generative path is **bypassed** (asserted by spying that the reasoning client is not asked to compose an apology).

### Tool Gateway Validation Pattern
- `GW1` Null/None object or empty required field in an outbound payload → structured rejection, no send.
- `GW2` String-format regexes enforced: domain shape, `angle_key` shape, tier label (patterns in `NOTES.md`); a malformed value is rejected (`T7.3` cross-check).
- `GW3` Rejections are structured data fed back to the loop, never an uncaught exception.
- `GW4` **PDF health:** a saved asset must have the `%PDF-` magic header, non-zero length, and an EOF marker; a truncated/empty PDF is rejected (`T7.2` cross-check).
- `GW5` The gateway re-enforces the Policy 5 ceiling as the last line of defense (`CL3` cross-check).

---

## §7. End-to-end & integration

| ID | Check | Method | Pass condition |
|---|---|---|---|
| `E1` | Single-vertical happy path | `python main.py` on a seed expected to qualify ≥1 brand (mocked services) | `qualified_leads.json` + `reactfirst_run.log` produced; ≤3 angles; ≥1 saved PDF passing `GW4` |
| `E2` | Within the cap | same run | Total tool calls ≤ 15 with headroom; metrics in the log |
| `E3` | Recovery path exercised | seed where A+B < 2 domains (mocked) | Vector C fires (`T2.2`); pipeline still completes |
| `E4` | Fallback path | no-match seed | Only `FALLBACK_MESSAGE` emitted (`FB3`) |
| `INT1` | Subdomain routing | Inspect outbound calls | Only `request_reactfirst_pdf` targets `outreach.reactfirst.ai`; routing constraints from `NOTES.md` honored |
| `INT2` | Multi-channel integration | Full mocked run touching catalog + store + RAG + crawler + PDF + gateway | All components interoperate; auth gate honored for any contact read; no secret leaked |
| `INT3` | Idempotent re-run | Run twice on the same input | Deterministic qualified set; no duplicate assets corrupting `assets/`; Chroma reused, not rebuilt blindly |

---

## §8. Generalization & anti-leakage audit (highest-leverage correctness gate)

| ID | Check | Method | Pass condition |
|---|---|---|---|
| `G1` | No raw eval / no framework | `grep -Ei "eval\(\|exec\(\|langgraph\|langchain\|create_react_agent\|AgentExecutor\|bind_tools"` over all `.py` | No hits (the only `ast` evaluation is the whitelist walker in `secured_calculator`) |
| `G2` | No hardcoded catalog/sample data | grep for brand/domain/GTIN/tier/seed literals | None; everything read from the three input files at runtime (`CAT5`, Policy 1) |
| `G3` | OS-agnostic paths | grep for absolute paths / `C:\\` / leading `/Users`; check `os.path`/`pathlib` | No hardcoded absolute paths |
| `G4` | No secrets in tracked files | grep for key/token patterns and the `corporate_access_key` value | None present; all secrets via `os.environ` (`AG5`) |
| `G5` | Generalizes to a new vertical | Run a **different** seed end to end (mocked) with no code change | Correct artifacts produced; behavior driven by inputs, not branches on a specific seed |

---

## §9. Submission / packaging hygiene

| ID | Check | Pass condition |
|---|---|---|
| `H1` | requirements pinned | Every non-stdlib import is in `requirements.txt` with `==` (incl. firecrawl + the resolved OQ-1/OQ-2 clients); `ENV2` passes |
| `H2` | Fresh-venv run | `pip install -r requirements.txt` then `import main` (clean) then `python main.py` with a sample input runs without traceback |
| `H3` | Import-safety holds on the final tree | re-run `ENV4` |
| `H4` | Header / identity block | `main.py` top comment carries author identity per project requirement |
| `H5` | Nothing dev-only or generated shipped | Build from an explicit allowlist; exclude `tests/`, `Reference/`, the PRD PDF, the working `.md` files, `.chroma/`, and any real `assets/` / secrets |

---

## Check-to-stage map (sanity)

| Stage | Checks |
|---|---|
| 0 setup | meta (this file set) |
| 1 env + data + lazy store | `ENV1`–`ENV4`, `CAT1`–`CAT6`, `RAG1`, `AG1`–`AG6` (store scaffolding) |
| 2 tool layer | `T1`–`T8` |
| 3 schemas + dispatch | `S0`–`S10` |
| 4 loop + cap + resiliency | `L1`–`L5`, `RS1`–`RS5` |
| 5 policies + gateway | `POL1`, `POL2`, `PR1`–`PR4`, `CL1`–`CL4`, `TG1`–`TG2`, `FB1`–`FB4`, `GW1`–`GW5` |
| 6 hybrid RAG / RRF | `RAG1`–`RAG5`, `T6.*` |
| 7 single-vertical E2E | `E1`–`E4` |
| 8 generalization / anti-leakage | `G1`–`G5` |
| 9 multi-channel integration + packaging | `INT1`–`INT3`, `H1`–`H5` |
