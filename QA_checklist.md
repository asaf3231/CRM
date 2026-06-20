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

### Policy 3 — ~~Premium Pricing / Risk Tier Loop~~  — **REMOVED** (Asaf, 2026-06-19)
- Premium pricing is no longer part of the system. `apply_premium`, the `PREMIUM_MULTIPLIER`/`INCIDENT_PREMIUM_THRESHOLD` constants, the `gtm_policies.txt` Policy 3 block, and the **`PR1`–`PR4` tests are retired** (deliberate deviation from the assignment spec, accepted by Asaf — see `CLAUDE.md` §5 Policy 3 and `NOTES.md`).
- `secured_calculator` (tool 8) **stays** as a general AST-walled arithmetic tool (the calculator security rule is independent of premium pricing).

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

## §10. Phase 2 — SLED 6-layer parity (L1 ICP Builder + L5 mini-CRM + L6 Outreach)

> Re-skin of the SLED 6-layer GTM engine onto our crisis-narrative / brand-safety domain (Asaf,
> 2026-06-19). All external transports (grounded search, Apollo, Resend/email, PhantomBuster) are
> **mocked with injectable clients**; live smokes stay SKIPPED without keys (OQ-7). Every existing
> governance contract (auth gate, ≤3 ceiling, Policy-6 fallback, Tool Gateway) is preserved.

### Layer 1 — ICP Builder (`build_icp_document`)  — Stage 10
- `ICPB1` Returns the structured ICP shape: `{vertical, want_signals[], avoid_signals[], geo, size_band, icp_tags[], anchor_companies[]}` (types correct; JSON-serializable).
- `ICPB2` Anchor/example leads are capped at `ICP_ANCHOR_COUNT` (=5); never more.
- `ICPB3` Import-safety holds (`ENV4` re-proven post-edit; no client/model built at import).
- `ICPB4` Anti-leakage (`G2`): no real catalog literals in the shipped tool or its prompt; anchors drawn at runtime, not hardcoded.
- `ICPB5` Policy 2 unchanged: `evaluate_icp_tags` `_ICP_TAGS` vocabulary + the ≥3 gate are untouched; the ICP doc does not replace the qualification gate.
- `ICPB6` Generalizes (`G5`-style): a second, different seed produces a correctly-shaped doc with no code change; under a mocked Claude client the shape is deterministic.

### Layer 5a — mini-CRM lead workspace (`crm_store.py`)  — Stage 11
- `CRM1` Lazy singleton: `crm_store` collection builds on **first use**, not at import (`ENV4` — all lazy singletons `None` after `import crm_store`).
- `CRM2` Lead record shape keyed on brand `Uniq_Id`: `{uniq_id, domain, status, stage, profile, contact_ids[], win_prob, outreach_state, notes, updated_at}`.
- `CRM3` `upsert_lead`/`get_lead`/`update_lead_stage` round-trip; upsert is **idempotent** (same `uniq_id` updates, never duplicates).
- `CRM4` Writes that expose/modify private contact fields go through the **Policy-4 auth gate** (`lead_store.authenticate_and_get_contact`); no/invalid key leaks **no** field (mirrors `AG1`–`AG6`).
- `CRM5` `opt_out_status == True` contacts are suppressed from the workspace's outbound-eligible set.
- `CRM6` `compute_win_prob` is **deterministic** and sourced **only** from catalog/record signals (tier, incidents, ICP count, pixels) — Policy 1 (no parametric invention); boundary-tested.
- `CRM7` No secret / `corporate_access_key` value in any returned payload, log, or tracked file (`G4`).
- `CRM8` `write_qualified_leads` upserts CRM records; `qualified_leads.json` remains a ≤3-capped export view (Policy 5 / `CL*` cross-check).

### Layer 5b — Profile Expander / contact discovery (`discover_contacts`)  — Stage 12
- `DISC1` Returns the contact-candidate shape: `{brand_id, contacts: [{first_name, last_name, role, email, linkedin_url}], count}` (JSON-serializable).
- `DISC2` Injectable `client` (mocked Apollo + grounded search); under the mock the output is deterministic; no live egress at test time.
- `DISC3` Does **not bypass** the Policy-4 gate: discovery performs **no privileged read** of the auth-gated `lead_store` contacts collection and exposes **no stored private contact field** — it surfaces only freshly-discovered candidate data and attaches candidate refs to the CRM lead's `contact_ids` (workspace metadata). The Policy-4 gate remains the single, un-bypassed path to existing private records; auth + `opt_out_status` for actual outbound are enforced downstream at L6 dispatch.
- `DISC4` Anti-leakage (`G2`/`G4`): no hardcoded contacts/secrets; tool count is now **10** (three-way identity assert passes).
- `DISC5` Import-safety holds (`ENV4`).

### Layer 6 — Outreach Engine (deterministic post-loop engine)  — Stages 13–14
- `OUT1` `schedule_outreach_cohort` batches leads into cohorts of **≤ `DAILY_SEND_CAP` (=50)**; the previously-dead constant is now wired and enforced.
- `OUT2` `dispatch_outreach` egress is isolated to `OUTREACH_SUBDOMAIN` only (`INT1` extension); no other host is contacted for sends.
- `OUT3` `opt_out_status == True` ⇒ **never dispatched**, regardless of fit.
- `OUT4` Dispatch passes the **Policy-4 auth gate** and **`gateway_validate`** before leaving the process; an invalid payload aborts the send (structured rejection, no raise).
- `OUT5` No secret (Slack webhook, email/Apollo/PhantomBuster keys) appears in logs, errors, returns, or tracked files.
- `OUT6` A new **escalation path** handles unanswered borderline (Slack-gated) approvals — a sibling `escalate_prospect(...)` (mocked escalator: escalation message + calendar booking). `route_prospect`'s existing TG1/TG2 keys/behaviour stay **byte-stable** (untouched — escalation is additive/separate).
- `OUT7` `outreach_status_brief` returns a morning-brief/heartbeat rollup (cohort counts, sends, replies) with A/B variant tags — deterministic under mocks.
- `OUT8` End-to-end wiring: a discovery query flows L1 ICP doc → L5 CRM records → L6 cohorts → mocked dispatch → status brief, all under the 15-call cap; a no-match seed still yields byte-exact `FALLBACK_MESSAGE`.
- `OUT9` Idempotent re-run: deterministic cohorts/brief; no duplicate sends on replay.
- `OUT10` Packaging refreshed: `crm_store.py` in `MANIFEST.txt`; `ENV4` holds on the final tree; full regression green.

---

## §11. Phase 3 — Integration Layer (FastAPI server; FE↔BE wiring)

> New, **additive** HTTP layer (`api_server.py` + `api_adapters.py` + `api_seed.py`) exposing the
> backend to the React frontend. v1 is **offline-deterministic** (a `crm_store` seed; no API keys).
> The graded backend is untouched — the API only READS. Plan: `~/.claude/plans/sprightly-tinkering-hennessy.md`.
> All transports offline; `import main`/`import api_server` stay side-effect-free (ENV4 preserved).

- `INTG0` **Dep-lock gate:** exact `==` pins for `fastapi`, `uvicorn`, `httpx`, `jsonschema` (+ `anyio`
  if needed) added to `requirements.txt`; the **full pre-existing suite still passes (684 passed,
  1 skipped, 0 failed)** in `.venv` after install. No wildcards (CLAUDE.md §1.1).
- `INTG1` **Import-safety:** `python -c "import api_server"` from an empty dir with **no
  `ANTHROPIC_API_KEY`** exits 0 with zero side effects (seed fires only on ASGI `lifespan` startup,
  never on import); `import main, lead_store, rag_engine, crm_store` still clean; `main` never imports
  `api_server`.
- `INTG2` **Test isolation:** `tests/conftest.py` autouse fixture resets `crm_store._leads_collection`
  and `lead_store._collection_instance` to `None` between tests; the startup seed does not leak into
  `CRM*`/`DISC*`/`ENV4` tests (full regression stays green).
- `INTG3` **Health + scaffold:** `GET /api/health` returns 200; FastAPI `app` constructs with no backend
  side effects; CORS `allow_origins` is localhost-only (recorded in NOTES).
- `INTG4` **Leads endpoints:** `GET /api/leads` → `Lead[]`, `GET /api/leads/stats` →
  `LeadDiscoveryStats`, `POST /api/leads/find-more` (body `{existing_domains[],target}`) → deduped
  `Lead[]`; bodies validate against `schemas/*.json`.
- `INTG5` **Adapter contract + thresholds:** `crm_lead_to_ui` emits camelCase, strips `contact_ids`,
  never emits `corporate_access_key`; GovBand (`≥3`/`1–2`/`0`) + FitGrade (`≥4`/`2–3`/`≤1`) + LeadKind
  rules are exact and unit-tested.
- `INTG6` **ICP endpoints (offline seed):** `GET /api/icp` → `IcpDocument` from the seed dict (NOT a
  live `build_icp_document` call), `GET /api/icp/suggestions` → `string[]`; field map per the plan.
- `INTG7` **Outreach stats/cohorts:** `GET /api/outreach/stats` → `OutreachStats` (from the full
  `run_outreach_pipeline` return), `GET /api/outreach/cohorts` → `Cohort[]` (synthesized name/enrolledAt/
  variants); deterministic under the seed.
- `INTG8` **Enrollments + mock split:** `GET /api/outreach/enrollments` → `EnrollmentEvent[]` derived
  from real cohort data; `getReachSeries`/`getAgentEvents`/`runDiscovery`/`getSwarmStages` stay FE-mock
  (no backend route in v1) — the network tab shows only real-data `/api/...` calls.
- `INTG9` **FE wiring:** the 8 wired `api.ts` methods call `fetch(BASE_URL+…)` via the vite `/api`
  proxy with zero component changes; `findMoreLeads` gains a `catch`/error state; `tsc --noEmit` clean.
- `INTG10` **Contract parity + live proof:** committed `schemas/*.json` (generated from `types/index.ts`)
  validate every wired response in `test_api.py`; two-server Preview-MCP check shows each wired screen
  rendering backend data (real `GET /api/...` 200s in the network tab); kill-backend → UI error state.

---

## §12. Phase 4 — Durable Persistence Layer (MongoDB via `pymongo`; core stores)

> A real database replaces the in-memory `mongomock` stores. A shared lazy `db.py` returns a
> `pymongo.MongoClient(MONGO_URI)` when `MONGO_URI` is set, else **falls back to `mongomock`** — so the
> offline suite, ENV4 import-safety, and the Policy-4 auth gate are untouched and a real DB is opt-in via
> env. Scope = the **`contacts`** (`lead_store.py`) + **`leads`** (`crm_store.py`) collections; the brands
> catalog stays a CSV input. Decisions: `NOTES.md` (2026-06-20). Plan: `~/.claude/plans/moonlit-herding-moon.md`.
> All offline checks run with **no `MONGO_URI`**; live persistence checks are `skipif`-gated like `S10`.

- `DB0` **Dep-lock gate:** exact `==` pin for `pymongo` (captured from the actual `.venv` install, not
  guessed) added to `requirements.txt`; `mongomock==4.1.2` retained as the fallback/test driver; no
  wildcards (CLAUDE.md §1.1); the **full pre-existing suite still passes (754 passed, 1 skipped, 0 failed)**
  with `MONGO_URI` unset.
- `DB1` **No secrets:** no real connection string / credential in any tracked file; `.env` is gitignored;
  `.env.example` carries only a placeholder `MONGO_URI` (G4 grep clean).
- `DB2` **Import-safety (ENV4 extended):** `python -c "import db"` from an empty dir with no `MONGO_URI`
  exits 0 with zero side effects; `db._client` stays `None` until the first `get_mongo_client()` call; no
  connection/network at import; `import main, lead_store, crm_store, rag_engine, api_server` still clean.
- `DB3` **Env-driven fallback:** `get_mongo_client()` returns a `pymongo.MongoClient` when `MONGO_URI` is
  set and a `mongomock.MongoClient` when unset — both branches unit-tested via monkeypatched env, no real
  network; `get_database()` returns `client[DB_NAME]` (default `gtm_db`).
- `DB4` **Stores routed through `db.py`:** `lead_store.get_lead_data_collection()` and
  `crm_store.get_crm_collection()` obtain their collection via `db.get_database()`; the Policy-4 auth gate
  remains the single chokepoint (signature + denial semantics byte-stable); the CRM record shape is unchanged.
- `DB5` **Idempotent contacts seed:** `get_lead_data_collection()` loads `contacts.json` **only when the
  collection is empty** (no unconditional `insert_many`); a 2nd call against a persistent client does NOT
  duplicate; `tests/conftest.py` also resets `db._client`; full regression stays **754/1** on the mongomock path.
- `DB6` **Indexes:** unique index on `leads.uniq_id` and `contacts.email` (+ index on
  `contacts.target_brand_id`), created idempotently inside the getters and guarded so they do not error
  under mongomock; uniqueness enforced under real Mongo.
- `DB7` **Restart durability (live, `skipif` no `MONGO_URI`):** upsert a lead → reset the `db`/store
  singletons → reconnect → the lead is still present; same gating pattern as `S10` so the offline suite
  stays deterministic.
- `DB8` **Idempotent seed script:** `scripts/seed_db.py` loads `contacts.json` into Mongo **seed-if-empty**;
  running it twice yields no duplicate contact documents.
- `DB9` **Packaging + docs:** `db.py` + `pymongo` listed in `MANIFEST.txt`; `CLAUDE.md` (§1.1 pins, §2
  layout, §3.4 import-safety) and `NOTES.md` updated (persistence decision, rejected SQLite/Postgres, index
  choices); ENV4 holds for all modules incl. `db.py`; **754/1 + the new `DB*` tests** green.

---

## §13. Phase 5 (proposed) — DB ↔ backend wiring

> Connecting the Phase-4 persistent DB into the API/pipeline. Full plan: `backend_connection_plan.md`
> (stages C0–C5). Only **C0** is executed so far; the rest stay plan-only pending Asaf approval.

- `CONN0` **No demo clobber:** with a persisted, non-empty `leads` collection (`MONGO_URI` set), an API
  startup does **not** modify or overwrite existing records — `api_seed.seed_demo()` is seed-if-empty (skips
  when the workspace is non-empty) and honours a `SEED_DEMO` opt-out. Import-safety preserved (seed still
  fires only on ASGI `lifespan`, never at import).
- `CONN1` **Offline dev unchanged:** on the mongomock path (`MONGO_URI` unset, workspace always empty at
  boot) the 16 demo leads still seed, so the FE dev experience is identical; full offline suite stays green.
- `CONN2` **DB-aware `/api/health` (C1):** when `MONGO_URI` is set the probe pings Mongo and reports
  `{status, db: "up"|"down"}`; when unset it reports `db: "mock"`; a down/unreachable Mongo returns a
  graceful `status:"degraded"` body, never a 500/hang. No client built at import (ENV4).
- `CONN3` **Computed stats from the workspace (C2):** `GET /api/leads/stats` derives the funnel from the
  persisted `leads` (via `api_adapters.compute_stats_from_leads`), not the static `SEED_STATS` —
  add/modify a lead → the response changes (`discovered`/`retained`/`aboveFloor`/`strong`/`review` reflect
  the real records).
- `CONN4` **No leak on stats:** the `/api/leads/stats` body never carries `corporate_access_key` or
  `contact_ids` (it emits only aggregate counts).
- `CONN9` **ICP durable substrate (C6):** `/api/icp` + `/api/icp/suggestions` are served from a persisted
  `icp_documents` collection (`api_seed.get_icp_document`), not the in-memory `SEED_ICP` constant. The doc is
  **seed-if-empty** on lifespan startup, **independent of `SEED_DEMO`** (the ICP is baseline config, not demo
  data — Railway sets `SEED_DEMO=0`); editing the stored doc changes the response; an empty collection falls
  back to `SEED_ICP` so the endpoint never 500s/returns empty; the offline mongomock path seeds at boot so FE
  dev is unchanged; the body carries no `corporate_access_key`/`_id`/`icp_id`. Import-safety preserved
  (collection accessed lazily; seed only on ASGI lifespan; `_icp_collection` reset in `conftest.py`).
- `CONN10` **ICP restart durability (live, `skipif` no `MONGO_URI`, like `DB7`):** an edited ICP doc survives
  a simulated restart (reset `db`/store singletons → reconnect → the edit persists); `seed_icp_if_empty()` is
  idempotent (no duplicate/clobber). Self-cleaning (drops `icp_documents` in a `finally`).
- `CONN7` **Live discovery job lifecycle (C4):** `pipeline_runner.run_discovery` chains the real graded tools
  (mocked at the network boundary) → a job moves through stages to `done`; catalog matches that clear the ICP
  gate (`>= ICP_TAG_THRESHOLD` live signals) **persist** to `crm_store`; net-new brands are reported but **NOT
  saved** (Policy 1); below-threshold brands don't qualify; a tool error is recorded on the job, never raised.
- `CONN11` **ICP wiring (C4):** the search seed is composed from `api_seed.get_icp_document()`
  `vertical`+`want_signals` (override wins if supplied); `avoid_signals` drop matching candidates; `icp_fit` =
  `|crawl signals ∩ icp_tags|`. The graded `evaluate_icp_tags`/`_ICP_TAGS`/threshold are UNCHANGED (ICPB5).
- `CONN12` **Discovery endpoint gating (C4):** `POST /api/pipeline/discover` → 403 without `ENABLE_LIVE`, 401
  on a missing/invalid `DISCOVERY_TOKEN`, 409 while a run holds the single-job lock; 404 on an unknown job id;
  no `corporate_access_key` in any job body. Import-safety preserved (`pipeline_runner` lazy; ENV4).

> **Phase 6 — Real ICP: authoring + ICP-driven discovery (C7–C10, 2026-06-20).** Make the ICP an
> operator-authored, persistent document that demonstrably drives the search/scoring — everything
> EXCEPT the 4 live vars (`ANTHROPIC_API_KEY`/`FIRECRAWL_API_KEY`/`ENABLE_LIVE`/`DISCOVERY_TOKEN`).
> All offline/deterministic; the graded gate stays byte-stable.

- `CONN13` **ICP write/persist (C7):** `PUT /api/icp` maps the UI IcpDocument → storage shape
  (`api_adapters.ui_to_icp_doc`) and merge-persists via `api_seed.upsert_icp_document` (unsent fields
  preserved); a follow-up `GET /api/icp` reflects the edit; `sizeBand`/`icpTags` + `"Avoid: "` criteria
  round-trip. Survives a restart (live `skipif`-gated).
- `CONN14` **ICP write validation (C7):** a malformed body → structured 4xx (never 500); no
  `corporate_access_key` in the response; `api_seed._icp_collection` stays lazy (ENV4).
- `CONN15` **ICP drives queries (C8):** `pipeline_runner.compose_icp_query_terms` folds the FULL ICP
  (vertical + want_signals + icp_tags + size_band + geo) into the discovery seed; changing any field
  changes the seed; empty ICP → safe fallback.
- `CONN16` **ICP drives scoring (C8):** `canonicalize_icp_tags` aligns ICP tags → canonical `_ICP_TAGS`
  keys so `icp_fit` overlaps the live crawl signals (was always 0); `icp_score` rewards overlap, penalizes
  avoid matches, bounded [0,1]; `run_discovery` ranks `qualified`/`saved` by it.
- `CONN17` **Graded gate untouched (C8):** `_ICP_TAGS`/`evaluate_icp_tags`/`ICP_TAG_THRESHOLD` byte-stable
  (`main.py` 0-diff vs HEAD); every alias target ⊆ `_ICP_TAGS.keys()`; tool count 10; the ≥3 gate still
  passes ≥3 / fails <3.
- `CONN18` **Deterministic suggestions (C9):** `GET /api/icp/suggestions` returns additive, key-free
  phrases NOT already in the active ICP (no LLM); deterministic; reflects the persisted doc.
- `CONN19` **FE authoring round-trip (C10, Preview-MCP):** edit in `/icp` → Save → reload → the edit
  persists (served from the backend); `tsc --noEmit` clean.

> **Live data note (2026-06-20):** `brands_catalog.csv` was extended with a real athleisure brand universe
> (Alo Yoga, Vuori, Fabletics, … — 18 rows alongside the 12 synthetic) so live-crawled brands match the
> catalog and persist under Policy 1. `scripts/ingest_real_leads.py` runs the real pipeline tools
> (analyze → ICP gate ≥3 → win-prob → upsert) to persist qualified leads. 9 real athleisure leads were
> ingested into Atlas; the 16 demo seed rows were retired (`SEED_DEMO=0`). No graded contract changed.

---

## Check-to-stage map (sanity)

| Stage | Checks |
|---|---|
| 0 setup | meta (this file set) |
| 1 env + data + lazy store | `ENV1`–`ENV4`, `CAT1`–`CAT6`, `RAG1`, `AG1`–`AG6` (store scaffolding) |
| 2 tool layer | `T1`–`T8` |
| 3 schemas + dispatch | `S0`–`S10` |
| 4 loop + cap + resiliency | `L1`–`L5`, `RS1`–`RS5` |
| 5 policies + gateway | `POL1`, `POL2`, `CL1`–`CL4`, `TG1`–`TG2`, `FB1`–`FB4`, `GW1`–`GW5` *(`PR1`–`PR4` retired — Policy 3 removed)* |
| 6 hybrid RAG / RRF | `RAG1`–`RAG5`, `T6.*` |
| 7 single-vertical E2E | `E1`–`E4` |
| 8 generalization / anti-leakage | `G1`–`G5` |
| 9 multi-channel integration + packaging | `INT1`–`INT3`, `H1`–`H5` |
| **10 L1 ICP Builder** (Phase 2) | `ICPB1`–`ICPB6` |
| **11 L5a mini-CRM core** (Phase 2) | `CRM1`–`CRM8` |
| **12 L5b contact discovery** (Phase 2) | `DISC1`–`DISC5` |
| **13 L6a outreach core** (Phase 2) | `OUT1`–`OUT6` |
| **14 L6b outreach center + packaging** (Phase 2) | `OUT7`–`OUT10`, re-run `INT1`–`INT3`, `H1`–`H5` |
| **I0 dep-lock gate** (Phase 3) | `INTG0` |
| **I1 API scaffold + import-safety + conftest** (Phase 3) | `INTG1`–`INTG3` |
| **I2 leads + ICP endpoints + adapters + seed** (Phase 3) | `INTG4`–`INTG6` |
| **I3 outreach endpoints** (Phase 3) | `INTG7`–`INTG8` |
| **I4 FE wiring + contract tests + live verify** (Phase 3) | `INTG9`–`INTG10` |
| **I5 live-pipeline + deferred routes** (Phase 3, follow-on) | (deferred; OQ-7-gated) |
| **D0 dep-lock + infra gate** (Phase 4) | `DB0`–`DB1` |
| **D1 `db.py` connection layer** (Phase 4) | `DB2`–`DB3` |
| **D2 route stores through `db.py` + idempotent seed** (Phase 4) | `DB4`–`DB5` |
| **D3 durability + indexes + restart proof** (Phase 4) | `DB6`–`DB8` |
| **D4 packaging + docs** (Phase 4) | `DB9` |
| **C0 stop demo-seed clobber** (Phase 5) | `CONN0`–`CONN1` |
