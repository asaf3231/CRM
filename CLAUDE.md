# CLAUDE.md — Project Standards & Conventions

Project: **Autonomous Agentic GTM Engine & Value-Hook Pipeline**
Target system: **ReactFirst AI Proactive Outbound Engine**
Deliverable: a modular, production-grade pipeline centered on `main.py` and its surrounding execution layout (`lead_store.py`, `rag_engine.py`, data + artifact dirs)
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

Do not silently continue into the next stage. Do **not** change a tool signature, a JSON schema, the loop contract, a policy constant, or a graded log/output literal without surfacing the decision to Asaf first.

If `PLAN.md`, `QA_checklist.md`, or `NOTES.md` is missing, do **not** proceed with implementation. Draft the missing file in chat first and wait for Asaf to approve or create it.

### 0.1 Autonomous PM ↔ executer mode (`ORCHESTRATION.md`)

When run under `ORCHESTRATION.md`, the **PM agent** (the persistent main session) performs
the stage-boundary review and **may auto-advance clean stages** by spawning a fresh
`swe-executer` subagent per stage. In this mode the human gate (Asaf) narrows to three
triggers: (1) a required decision / open-question / secret; (2) a request to change a tool
signature, JSON schema, policy constant, the loop contract, or a graded literal; (3) a second
consecutive QA failure on a stage. Everything else proceeds without Asaf in the loop. The
per-stage "stop and report" of §0 above still binds the **executer** — it never crosses its
stage boundary or changes a contract; it surfaces those as `DECISION-NEEDED`, which the PM
converts into a halt. The shared memory is the repo files (`PLAN.md`/`NOTES.md` ledger +
`briefs/`/`handbacks/` mailbox).

---

## 1. Environment

The pipeline must run in a clean environment with no manual fixups.

- **Python:** 3.10 or higher.
- **OS-agnostic:** must run on Windows / macOS / Linux. No hardcoded absolute paths. Build every path with `os.path.join` / `pathlib` and resolve everything relative to the current working directory.
- **Entry point:** the agent answers a **conversational business query** through `answer_question(query, ...)` (PRD §5.3). `python main.py` runs the loop; the three data files (`brands_catalog.csv`, `contacts.json`, `gtm_policies.txt`) are present in the cwd. There is **no `input.json`** — the query is the input.
- **Import-safe (non-negotiable):** `import main`, `import lead_store`, and `import rag_engine` must succeed with **zero side effects** — no network calls, no model downloads, no API authentication, no vector-store build, no file writes at import time. All clients, embedding models, the ChromaDB collection, and the mongomock store are constructed **lazily** (first use) or inside `main()`. The PRD's `get_lead_data_collection()` lazy-singleton in `lead_store.py` is the canonical pattern. See §3.4. Enforced by check `ENV4`.

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

### 1.1 Pinned dependencies (non-negotiable)

`requirements.txt` must pin **at least** these, and a fresh venv must be able to run `pip install -r requirements.txt`:

```text
anthropic           # ⚠ pin exact ==version at Stage 1 install — the LLM provider for the whole pipeline (Claude)
chromadb==0.5.5
sentence-transformers==3.0.1
mongomock==4.1.2
pandas==2.2.2
firecrawl-py        # ⚠ pin exact ==version at Stage 1 install (OQ-2)
```

- `os`, `sys`, `json`, `ast`, `re`, `csv`, `math`, `base64`, `concurrent.futures`, `importlib.util`, `dataclasses`, `pathlib`, `time` are **standard library** — do not list them.
- **LLM provider decision (Asaf, 2026-06-18):** the pipeline uses **Claude** for *all* LLM work via the official `anthropic` SDK — replacing the PRD's OpenAI (`gpt-4o-mini`, `gpt-5-mini`) and Gemini (`gemini-flash-latest`, `gemini-3.1-flash-lite`). This is a deliberate deviation from PRD §3, recorded in `NOTES.md`. `openai==1.51.0` and `google-genai` are therefore **removed** from the pin set.
- **Every other non-stdlib import must be pinned with `==`.** The remaining external services are **not LLMs** and stay: `google-search-results` (SerpAPI/Maps, Vector B), `tavily-python` (Vector C), `firecrawl-py` (crawler). Pin each at Stage 1 install. Check `ENV2` fails if any imported module is unpinned.
- A missing/unpinned transitive that breaks the fresh-venv install is a Stage 1 blocker, not a Stage 9 surprise.

### 1.2 LLM / model clients

**Single LLM provider — Claude via the `anthropic` SDK.** One lazily-constructed client (`_get_client()`), used everywhere an LLM is needed. Model tiers (named constants in Configuration, §9):

| Role | Model | Constant |
|---|---|---|
| Main agentic reasoning loop (`answer_question`) | **claude-opus-4-8** | `REASONING_MODEL` |
| `analyze_company_chunk` reasoning (tool 4) | **claude-sonnet-4-6** | `ANALYZER_MODEL` |
| `generate_search_queries` (tool 1) + `extract_and_score_pool` (tool 3) | **claude-haiku-4-5** | `LIGHT_MODEL` |

- Use **adaptive thinking** on Opus 4.8 (`thinking={"type":"adaptive"}`) for the reasoning loop; tune `output_config={"effort": ...}` per workload. Do **not** use `budget_tokens` or `temperature`/`top_p` (removed on 4.7+ — they 400).
- **Embeddings stay local.** Claude has no embeddings API; tool 6 uses `all-MiniLM-L6-v2` via `sentence-transformers` (unchanged). This is why the local vector store is the right call.
- **Vector A discovery** (was Gemini + web grounding) uses Claude with the server-side **`web_search` / `web_fetch`** tools inside `execute_3way_fanout`.
- **Non-LLM services stay:** `firecrawl-py` (crawl + pixels, tool 4), SerpAPI+Maps (Vector B), Tavily (Vector C). These are not models — the provider switch doesn't touch them.

API key from `os.environ["ANTHROPIC_API_KEY"]` (never hardcoded; OQ-7). Use exact model id strings above — do not append date suffixes.

API keys come from environment variables (`os.environ`), never hardcoded and never committed. The exact env-var names are recorded in `NOTES.md` once confirmed. No key, token, or `corporate_access_key` value may appear in any tracked file.

---

## 2. Source-of-truth files

Expected project layout. **Layout decision (locked 2026-06-18):** `main.py` is the orchestrator and entry point; the stateful / heavy-dependency concerns live in their own modules beside it so the pipeline stays reviewable and each tool tests in isolation.

```text
CRM/                                  # working dir == runtime cwd
│  # --- code ---
├── main.py                            # orchestrator: config, the 8 tools, schemas, dispatch, agentic loop, policy wiring, main()
├── lead_store.py                     # mongomock-backed CRM store + Policy 4 corporate_access_key auth gate
├── rag_engine.py                     # ChromaDB (all-MiniLM-L6-v2) + BM25 + RRF tiering — the lazy local vector store
├── requirements.txt                  # pinned deps
│  # --- runtime data: the three bounded inputs (single source of truth — PRD §2; NOT business logic) ---
├── brands_catalog.csv                # the 9-column Brands Data Catalog (schema in §4)
├── contacts.json                     # CRM contact records, loaded into mongomock by lead_store.py (schema in §4.1)
├── gtm_policies.txt                  # the GTM operational policy matrix parsed before any outbound state
│  # --- runtime artifacts (produced by a run) ---
├── reactfirst_run.log                # the agentic run log (literals — §7)
├── assets/                           # saved ReactFirst Narrative-Analysis PDFs (request_reactfirst_pdf output)
├── .chroma/                          # local Chroma persistence (lazy-built; gitignored; never shipped)
│  # --- dev-only management files ---
├── CLAUDE.md                         # permanent project rules (this file)
├── PLAN.md                           # stage tracker and active plan
├── QA_checklist.md                   # TDD blueprint; every stage DoD references it
├── NOTES.md                          # decisions, verified facts, handbacks, open questions
├── Architecture Specification & Product Requirements Document (PRD).pdf
├── Reference/                        # quality benchmark from a prior project (never shipped)
└── tests/                            # dev-only TDD suite (never shipped)
```

Source-of-truth rules:

- `CLAUDE.md` defines **how** work must be done; `PLAN.md` defines **what** the current stage is; `QA_checklist.md` defines **how** each stage is verified; `NOTES.md` records **why**.
- `brands_catalog.csv`, `contacts.json`, and `gtm_policies.txt` are the **three bounded runtime inputs** and the single source of truth (PRD §2). Their values must never be hardcoded into a tool or a prompt (see §5 anti-leakage, and Policy 1). The catalog is read via pandas through the loader in `main.py`; columns are accessed by the names in §4, never by positional index. Contacts are reached **only** through `lead_store.get_lead_data_collection()` behind the Policy 4 gate.
- `.chroma/` and `assets/` are generated, machine-local, and excluded from any submission/commit.
- Do not duplicate long plans or decisions across files. Put each thing in the right place.

---

## 3. System objective & runtime contract

`main.py` runs an **autonomous agentic GTM pipeline**: from a vertical seed it discovers candidate brands, qualifies them against an ICP, scores an outreach angle, and produces value-hook assets — all through a raw tool-calling loop, under hard governance policies.

### 3.1 Pipeline shape (the happy path)

```text
vertical_seed
   → generate_search_queries (variation matrix, target_count=15)
   → execute_3way_fanout      (Vector A ∥ B, Vector C recovery if A+B < 2 domains)
   → extract_and_score_pool   (de-dup + map against brands_catalog.csv)
   → analyze_company_chunk    (≤100 domains / 800s; TikTok + Meta Pixel detection via Firecrawl)
   → evaluate_icp_tags        (Boolean JSON classifier; qualify iff ≥3 tags match)
   → match_solicitation_angle (ChromaDB + BM25 → RRF → priority Tier 1..4)
   → request_reactfirst_pdf   (save the value-hook asset to assets/)
   → qualified_leads.json     (≤3 angles total — Policy 5)
```

`secured_calculator` is an auxiliary tool the agent may call at any step (e.g. pricing math under Policy 3) and **must never** use `eval`/`exec`.

### 3.2 Runtime I/O

1. Receive a **conversational business query** (the Q1–Q6 patterns in PRD §4) at `answer_question(query, ...)`.
2. Load + validate `brands_catalog.csv` (§4) and parse `gtm_policies.txt`; lazily init the contacts store. A malformed input is a clean startup error, not a mid-run crash.
3. Run the agentic loop (§6) under the global anti-loop cap of **15 tool calls** (§6.5); on cap exhaustion, fall back to a **safe error state** (PRD §5.3).
4. Route every outbound payload through the Tool Gateway (§5). Save any produced PDF under `assets/`; write `reactfirst_run.log`.
5. On any zero-match / validation-failure terminal condition, emit the Policy 6 string **exactly** and nothing else (§5, Policy 6).

The query class determines the path: an auth/lookup query (Q1) → authenticate → `get_lead_data_collection`; a catalog comparison (Q2) → pandas over the CSV; a discovery query (Q4/Q6) → `generate_search_queries` → `execute_3way_fanout` → `analyze_company_chunk`; an angle query (Q3) → CSV filter → `match_solicitation_angle`; a "top N" query (Q5) → Policy 5 ceiling.

### 3.3 Governing policies (summary — full rules in §5; parsed from `gtm_policies.txt`)

| Policy | Name | One-line rule |
|---|---|---|
| 1 | Authoritative Context Bound | Any claim about a prospect's market position / tier / competitor derives **solely** from `brands_catalog.csv` — never from the model's parametric knowledge |
| 2 | ICP Validation Threshold | A brand qualifies **iff** it ticks **≥3** strict ICP parameters during deep scraping |
| 3 | ~~Premium Pricing / Risk Tier Loop~~ | **REMOVED (Asaf, 2026-06-19).** Premium pricing / the 15% Tier-1 risk multiplier is no longer part of the system. `secured_calculator` stays for general arithmetic. |
| 4 | Data Protection & Auth Gate | `corporate_access_key` must verify via the auth tool before extracting/modifying any private contact record **or logging interaction counts** |
| 5 | Output Suggestions Ceiling | **≤3** distinct angles/capabilities; if a query requests a specific subset ≤3 (e.g. "top 2"), output **exactly** that count; a request for >3 (e.g. "top 5") is capped to 3 |
| 6 | Explicit Zero-Match Boundary | zero matches / failed validation ⇒ output EXACTLY the fallback string; bypass all generative prose |

### 3.4 Import-safety contract (restated — it is graded)

No module-level work beyond defining constants, functions, classes, and schemas. Specifically forbidden at import time: constructing the Anthropic/Firecrawl/SerpAPI/Tavily clients, loading the SentenceTransformer model, opening/building the Chroma collection, running `get_lead_data_collection()` (mongomock + `contacts.json` load), reading any of the three input files, or writing any file. Use lazy singletons (`_get_client()`, `_get_embedder()`, `_get_collection()`, `_get_store()`). Verified by `ENV4`.

---

## 4. The 9-column Brands Data Catalog — operational compliance (non-negotiable)

`brands_catalog.csv` has **exactly these 9 immutable columns** (PRD §2.1):

```text
Uniq_Id, Brand_Name, Primary_Domain, Core_Category,
Estimated_Ad_Spend_Tier, Current_Status, Historical_Social_Incidents,
Main_Competitor_Id, Gtin_Prefix
```

Column meanings that drive logic:
- `Uniq_Id` — UUID primary key. `Main_Competitor_Id` is a **foreign key to another row's `Uniq_Id`**.
- `Core_Category` — multi-tier path, e.g. `Apparel > Athleisure > Sustainable` (this is the `category_path` fed to `match_solicitation_angle`).
- `Estimated_Ad_Spend_Tier` ∈ {`Tier 1` = $5M+, `Tier 2` = $1M–$5M, `Tier 3` = <$1M}.
- `Current_Status` ∈ {`Active_Client`, `Open_Opportunity`, `Unreached_Prospect`, `Blacklisted`} — **`Blacklisted` brands are excluded from outreach.**
- `Historical_Social_Incidents` — integer count of past viral/PR crises (Policy 3 compares `> 5`).

Compliance rules (enforced by checks `CAT1`–`CAT5`):

- **Validate on load.** Assert the header is exactly these 9 names (order-tolerant, name-exact). A missing/renamed/extra column is a clean, explicit startup error — never a silent `KeyError` later. **The CSV header is the final arbiter of spelling** (see the `_Id` note below).
- **Access by name, never by index.** No `row[4]`. Use pandas + `row["Estimated_Ad_Spend_Tier"]`.
- **Typed reads.** `Historical_Social_Incidents` coerced to `int`; tier/status compared exactly to the enums above. Coercion failures are surfaced, not swallowed.
- **`Main_Competitor_Id` spelling.** The PRD spells it `Main_Competitor_Id`; an earlier brief had `Main_Competitor_ld` (OCR-style typo). Use whatever the **real `brands_catalog.csv` header** says — `CAT1` validates against the actual file and is the tiebreaker. Recorded in `NOTES.md`; do not silently "fix" the header in code.
- **No catalog values in code.** Brand names, domains, GTIN prefixes, competitor ids, status/tier strings are read at runtime; none may be hardcoded into a tool or a prompt (anti-leakage §5; Policy 1).

### 4.1 CRM contact records (`contacts.json` → `lead_store.py`, mongomock)

`lead_store.py` follows the PRD's exact lazy-singleton pattern: `get_lead_data_collection()` builds a `mongomock.MongoClient()`, db `gtm_db`, collection `contacts`, and `insert_many` from `contacts.json` **on first call** (import-safe). Each record (PRD §2.2):

```text
first_name, last_name, email (email format), corporate_access_key,
role, linkedin_url (uri), interaction_history_count (int),
opt_out_status (bool), target_brand_id
required: first_name, last_name, email, corporate_access_key, role, target_brand_id
```

- `corporate_access_key` is a **field on each record**. Policy 4 authenticates a **caller-supplied key** (e.g. Q1 "My access key is Access99") against the target record's `corporate_access_key` via the auth tool before exposing/modifying the record or reading `interaction_history_count`.
- `target_brand_id` links a contact to a brand (`Uniq_Id`) in the catalog.
- `opt_out_status == True` ⇒ the contact is suppressed from outbound regardless of fit.

---

## 5. Governance policies — exact rules

These are behavioral contracts parsed from `gtm_policies.txt`. Each has a dedicated QA section.

### Policy 1 — Authoritative Context Bound  (QA: `G2`, `CAT5`, `POL1`)
- Any claim about a prospect's market position, ad-spend tier, competitor layout, or history must derive **solely** from `brands_catalog.csv` — never from the model's pre-trained parametric knowledge. The agent must not invent brand realities, tiers, or pricing baselines.
- In practice: catalog facts are retrieved and quoted, not generated; the system prompt forbids fabricating catalog values; anti-leakage (§5/`G2`) keeps real catalog data out of the code.

### Policy 2 — ICP Validation Threshold  (QA: `T5.2`, `POL2`)
- A prospect qualifies for automated outreach **iff** it explicitly ticks **≥3** strict ICP qualification parameters during deep scraping (`ICP_TAG_THRESHOLD = 3`). This is the single qualification gate; `evaluate_icp_tags` owns it. See also Trust-Gated Autonomy (§5.x) for the borderline-3 case.

### Policy 3 — ~~Premium Pricing / Risk Tier Loop~~  — **REMOVED (Asaf, 2026-06-19)**
- Premium pricing is **no longer part of the system.** The `apply_premium` helper, the `PREMIUM_MULTIPLIER`/`INCIDENT_PREMIUM_THRESHOLD` constants, the `gtm_policies.txt` Policy 3 block, and the `PR1`–`PR4` tests have been removed.
- This is a deliberate deviation from the assignment spec (which defines Policy 3 and a Q1 query that exercises it) — accepted by Asaf. Q1-style "what is our premium estimation tier" queries will no longer return a premium tier.
- `secured_calculator` (tool 8) **stays** as a general safe-arithmetic tool (still AST-walled, no `eval`/`exec` — the assignment's calculator security rule is independent of premium pricing).

### Policy 4 — Data Protection & Authentication Gate  (QA: `AG1`–`AG6`)
- Extracting/modifying any contact record, **or logging its `interaction_history_count`**, requires a valid `corporate_access_key` verified through the **authentication tool first**.
- The caller-supplied key is matched against the target record's `corporate_access_key` field. A missing/invalid key returns a structured denial (`{"error": "unauthorized", ...}`) and **never** leaks any record field (no partial PII, no interaction count).
- The denial is generic — it must not distinguish "wrong key" from "no key" in a way that leaks record existence beyond what is public.
- Verification is the single chokepoint in `lead_store.py`; no tool reaches the contacts collection around it. The key value never appears in logs, errors, tracked files, or returned payloads.

### Policy 5 — Output Suggestions Ceiling  (QA: `CL1`–`CL4`)
- The pipeline emits **at most 3** distinct target angles / product capabilities (`MAX_ANGLES = 3`).
- If the query requests a **specific subset ≤3** (e.g. "top 2 items"), output **exactly that count** — no padding to 3.
- If the query requests **more than 3** (e.g. Q5 "top 5"), **cap to exactly 3**, override the user's count, and record that the override occurred — do not error, do not return >3.
- Net rule: `output_count = min(requested_count or 3, 3)`. Enforced at the **output boundary** (Tool Gateway, §6.7), so no code path can exceed 3.

### Policy 6 — Explicit Zero-Match Boundary (Strict String Fallback)  (QA: `FB1`–`FB4`)
- If the pipeline produces **zero qualifying matches**, or any stage fails hard validation, the engine outputs this string **byte-exactly** and **nothing else** (no LLM prose, no JSON wrapper, no trailing punctuation/whitespace):

  ```text
  We have no product available today that fits your request
  ```

- This is a module-level constant `FALLBACK_MESSAGE` so it cannot drift. The generative path is **bypassed entirely** — the fallback is never produced by asking a model to apologize.
- Verified by integration tests that drive a no-match seed and a validation-failure seed end to end (`FB3`, `FB4`).

### Tool Gateway Validation Pattern  (QA: `GW1`–`GW5`)
- Every outbound payload (anything heading to `outreach.reactfirst.ai`, the PDF request, or the final output file) passes through a single **gateway validator** before it leaves the process. The gateway:
  - rejects **null/None objects** and empty required fields,
  - enforces **string-format regexes** (domain shape, angle-key shape, tier label) — recorded in `NOTES.md`,
  - verifies **PDF header / structural health** for any saved asset (`%PDF-` magic header, non-zero length, EOF marker),
  - enforces the Policy 5 ceiling as a last line of defense.
- A gateway rejection is structured data fed back to the loop, never an uncaught exception. An invalid payload **aborts the outbound step and raises a recovery path** (PRD §5.1), it does not silently send.

### Trust-Gated Autonomy (human-in-the-loop)  (QA: `TG1`–`TG2`)
- A prospect that clears `evaluate_icp_tags` only **borderline** — meets **exactly 3** criteria but scores low on traffic/secondary indicators — is **barred from immediate automated email**.
- Instead it is routed to a **Slack channel via webhook** for a human growth operator to approve/discard. Clear-cut (≥4 tags, or 3 with strong indicators) proceeds autonomously.
- The Slack webhook URL is an environment secret; routing is logged (without secrets). The borderline rule and its indicator thresholds are recorded in `NOTES.md`.

### Operational envelopes (PRD §5.3, §6.3)
- **Network isolation:** outbound campaigns use the dedicated subdomain `outreach.reactfirst.ai` only — kept separate from the corporate email domain. Only `request_reactfirst_pdf` egresses there (`INT1`).
- **Rate/volume:** outbound email is throttled to **≤50 messages/day per active outbound inbox**.
- **Latency target (metrology):** signal→campaign latency `L = T_delivery − T_discovery` with a target boundary `L ≤ 900s`. This is a measured SLO, not a hard abort; the per-chunk **800s** budget (§6) is the hard one. Metrology formulas are in `NOTES.md`.

---

## 6. The 8 tools — exact contract

Exactly **8 tools**. Each needs a Python function **and** a JSON schema (§ schema rules below). Adding tools earns no credit and dilutes the schemas.

| # | Signature | Model / env | Returns | Notes |
|---|---|---|---|---|
| 1 | `generate_search_queries(vertical_seed: str, target_count: int = 15)` | claude-haiku-4-5 | `list[str]`, **10–20** variations | A **variation matrix** of distinct, non-overlapping queries; `target_count` default 15 |
| 2 | `execute_3way_fanout(queries: list[str])` | concurrent pool | pooled domain results | **Concurrent**: Vector A (Claude + `web_search`/`web_fetch`) ∥ Vector B (SerpAPI + Maps). Vector C (Tavily recovery) fires **iff** A+B yield `< 2` domains *for a query line* |
| 3 | `extract_and_score_pool(...)` | claude-haiku-4-5 | de-duplicated, scored candidate pool | De-dup (domain) layer; maps candidates against `brands_catalog.csv` (by `Primary_Domain`) |
| 4 | `analyze_company_chunk(domains: list[str])` | claude-sonnet-4-6 + Firecrawl | per-domain profile incl. pixel flags | Micro-batch, **≤100 domains**, **800s budget**; detects **TikTok Pixel, Meta Pixel, and Google Tag Manager**; partial results on timeout |
| 5 | `evaluate_icp_tags(company_profile_data: str)` | structural rule engine | `{"qualified": bool, "tags": [...], "count": int}` | **Boolean classifier**; qualifies **iff ≥3** tags (`ICP_TAG_THRESHOLD = 3`). Param is the raw crawl text/metadata **string** |
| 6 | `match_solicitation_angle(scraped_narrative_context: str, category_path: str)` | ChromaDB + all-MiniLM-L6-v2 + RRF | `{"angle_key", "tier", "scores"}` | **Hybrid RAG** over past crisis case studies: semantic + exact BM25 fused via **RRF** → priority **Tier 1..4** |
| 7 | `request_reactfirst_pdf(target_domain: str, validated_angle_key: str, calculated_risk_score: float)` | ReactFirst backend API | `{"path": "assets/...pdf", "ok": bool}` | Calls the ReactFirst backend; saves the Narrative-Analysis PDF to `assets/`; PDF health-checked at the gateway; only egress to `outreach.reactfirst.ai` |
| 8 | `secured_calculator(expression: str)` | AST isolated-walk | numeric result as `str` | Safe general arithmetic (risk/pricing math derived from catalog values); **raw `eval()`/`exec()` strictly prohibited** |

Behavioral specifics the unit tests pin down:

- **Tool 1** — produces a *matrix* of variations (not N copies); output length ≤ `target_count` after de-dup; deterministic shape under a mocked Claude client.
- **Tool 2** — A and B run **in parallel** (`concurrent.futures`); the **recovery rule is exact**: Vector C is triggered **only** when the union of A and B contains fewer than 2 distinct domains; each vector's failure is isolated (one vector down ≠ whole tool down).
- **Tool 3** — de-dup is by normalized `Primary_Domain`; catalog mapping attaches the 9-column context where a domain matches; non-catalog candidates are retained but flagged.
- **Tool 4** — hard ceilings: never crawl >100 domains in one chunk; respect the 800s wall-clock budget and return **partial** results (with a `timed_out` flag) rather than raising; pixel detection returns explicit booleans `tiktok_pixel` / `meta_pixel` / `gtm` (Google Tag Manager). Also extracts text patterns for operational scale.
- **Tool 5** — pure structural function (no network); the `>=3` rule is the single qualification gate; returns the matched tag list for auditability.
- **Tool 6** — semantic + BM25 lists fused by **Reciprocal Rank Fusion**; the fused score maps to a tier via the documented thresholds in `NOTES.md`; **Tier 4 = No Match** routes to the Policy 6 fallback at the output boundary.
- **Tool 7** — the PDF is saved under `assets/`; the saved file passes the gateway PDF-health check; the call is the only tool permitted to reach the outbound subdomain.
- **Tool 8** — follow the PRD reference `SafeCalculator`: `ast.parse(expr, mode="eval")` + a recursive `_walk` over a **whitelist of exactly these operators**: `Add, Sub, Mult, Div, USub` (i.e. `+ - * /` and unary minus), plus numeric constants and parenthesized grouping. **No `**`/Pow, no function calls, no names/attributes/subscripts/comprehensions/lambdas** — any other node raises `ValueError("Unauthorized mathematical syntax block: ...")`. SOP smoke: `(1700 + 450) * 1.15` evaluates correctly. (Use `ast.Constant`, not the deprecated `ast.Num`, for Py≥3.12 — the PRD snippet uses `ast.Num`; we modernize without widening the whitelist.) No raw `eval`/`exec` anywhere (grep-enforced, `G1`).

### 6.5 Anti-loop safeguard (global cap)

- A **single global counter** caps any path entering `answer_question` at **15 iterative tool calls** (`TOOL_CALL_CAP = 15`, PRD §5.3). On the 16th attempted dispatch the loop stops and **falls back to a safe error state** — it does **not** make the 16th dispatch.
- The cap is **hard**. Call-logging metrics (per-tool counts, total) are tracked and written to the log and the result.

### 6.6 Resiliency boundaries  (QA: `RS1`–`RS5`)

- **Two distinct Claude refusal/error paths, both handled:**
  - `anthropic.BadRequestError` (HTTP 400 — malformed request, oversized input): catch it, surface the message back so the next turn can change approach, continue the loop. The cap still applies.
  - `stop_reason == "refusal"` (HTTP 200 — safety classifier declined): **check `stop_reason` before reading `response.content`** (a refused response may have empty content). Treat as a recoverable signal: surface it, let the loop adjust, count it against the cap. (This replaces the brief's "Azure content-filter `BadRequestError`" with Claude's actual mechanism.)
- Vector/crawler/API failures inside tools become structured `{"error": ...}` results fed back to the loop — they never crash it.
- An **uncaught Python exception anywhere zeros the run.** The loop and `main()` are exception-safe end to end; tool-level failures are data, not crashes.

### 6.7 Loop contract

- The current loop uses the raw Anthropic Messages API: `client.messages.create(model=REASONING_MODEL, max_tokens=..., tools=TOOL_SCHEMAS, messages=...)`, iterate `response.content` for `tool_use` blocks, dispatch by name via `TOOL_DISPATCH`, append the assistant turn (full `response.content`) then a user turn of `{"type":"tool_result","tool_use_id":<id>,"content":...}` blocks — one per `tool_use`, ids 1:1 — and loop.
- **Frameworks are PERMITTED (Asaf, 2026-06-19).** LangChain / LangGraph / `create_react_agent` / `AgentExecutor` / the SDK tool-runner abstraction may be used and imported. The earlier "no framework" prohibition was self-imposed and is **lifted** — the reference architecture (Idan Benaun / SLED AI 6-layer GTM engine) uses LangGraph. Raw tool-calling remains acceptable; it is no longer mandatory. The old `L5` grep ban is retired.
- Each tool schema is Anthropic-shaped: `{"name", "description", "input_schema": {...}}` (not the OpenAI `{"type":"function","function":{...}}` wrapper).
- **Every outbound payload passes the Tool Gateway (§5) before leaving the process.**
- Termination precedence: (1) tool-call cap hit → safe error state, exit; (2) `stop_reason == "end_turn"` (no `tool_use`) → final answer / output; (3) zero-match or validation failure anywhere → Policy 6 fallback, exit; (4) tool error or `stop_reason == "refusal"` → feed back, continue.

---

## 7. Logging & output literals

**The one byte-exact, spec-mandated string** (PRD Policy 6 / SOP) — written to the result alone, no wrapper, no extra punctuation/whitespace/prose:

```text
We have no product available today that fits your request
```

It is the module constant `FALLBACK_MESSAGE`. Integration tests assert it byte-for-byte (`FB1`–`FB4`).

**Run logging is our own observability convention** (the PRD does not mandate log literals — it only requires the 15-call cap, the safe error state, and call-logging metrics). We adopt a single dual-write logger to both stdout and `reactfirst_run.log`, with a stable, self-consistent format the loop tests pin (`RS4`):

```text
Calling LLM for next tool to invoke
** Entering tool <tool_name> **
Parameter <p> = <first 50 chars of value, then "..." if longer>
** Exiting tool <tool_name> **
final response is = <final answer>          # normal stop
** TERMINATED: tool call cap reached **      # safe error state at the 15-call cap
```

These log strings are a project convention (not graded literals); keep them stable as constants so tests don't drift. Only `FALLBACK_MESSAGE` is contractually byte-exact.

---

## 8. Modular Script-Authoring Workflow

The deliverable spans a few modules, but each must read like a well-factored unit. Organize `main.py` top-to-bottom, one responsibility per section:

```text
1.  Header block             # author / project identity
2.  Imports                  # stdlib first, then third-party, grouped
3.  Configuration            # clients (lazy), constants, caps, FALLBACK_MESSAGE, regexes — no magic numbers inline
4.  Catalog loader           # brands_catalog.csv read + 9-column validation
5.  Tool implementations     # the 8 functions, one logical block each
6.  Tool schemas             # TOOL_SCHEMAS (names == function names)
7.  Dispatch table           # TOOL_DISPATCH = {name: fn}
8.  Gateway + policies        # gateway validator, Policy 3/5/6 enforcement helpers
9.  Logging helpers           # dual-write logger, truncation helper, call-metrics
10. Agentic loop              # answer_question(query, ...) with the 15-call cap + resiliency + termination precedence
11. I/O + main()              # load the 3 inputs, take the query, run answer_question, write artifacts, guard with try/except
```

`lead_store.py` owns the mongomock store + Policy 4 gate. `rag_engine.py` owns the Chroma + BM25 + RRF stack behind `match_solicitation_angle`.

Authoring rules:

- **TDD first.** For each section/tool, the matching `QA_checklist.md` check is known and written before the implementation, and must pass before the section is "done".
- **One responsibility per section.** No business logic in the logger; no policy logic buried inside a tool — policies live in §8 helpers and the gateway.
- **No magic values inline.** `TOOL_CALL_CAP=15`, `MAX_ANGLES=3`, `ICP_TAG_THRESHOLD=3`, `CHUNK_MAX_DOMAINS=100`, `CHUNK_TIME_BUDGET_S=800`, `FANOUT_RECOVERY_THRESHOLD=2`, `DEFAULT_QUERY_COUNT=15`, `EMBED_MODEL="all-MiniLM-L6-v2"`, and `FALLBACK_MESSAGE` are named constants in Configuration.
- **Default authoring mode:** for a non-trivial change, draft the section as a labelled, copy-pasteable block (e.g. `main.py — Section 5, tool 6 match_solicitation_angle`) for review before it lands. State clearly whether a block was **drafted only** or **written and test-verified**.

---

## 9. Stable names & conventions

```python
TOOL_CALL_CAP        = 15
MAX_ANGLES           = 3
ICP_TAG_THRESHOLD    = 3
CHUNK_MAX_DOMAINS    = 100
CHUNK_TIME_BUDGET_S  = 800
FANOUT_RECOVERY_THRESHOLD = 2
DEFAULT_QUERY_COUNT  = 15
DAILY_SEND_CAP       = 50          # outbound messages/day/inbox
LATENCY_TARGET_S     = 900         # signal→campaign SLO (soft)
EMBED_MODEL          = "all-MiniLM-L6-v2"
REASONING_MODEL      = "claude-opus-4-8"     # main agentic loop
ANALYZER_MODEL       = "claude-sonnet-4-6"   # analyze_company_chunk
LIGHT_MODEL          = "claude-haiku-4-5"    # query-gen + extract/score
FALLBACK_MESSAGE     = "We have no product available today that fits your request"

# Validate against the real brands_catalog.csv header on load (CAT1 is the tiebreaker for the _Id/_ld spelling).
CATALOG_COLUMNS = [
    "Uniq_Id", "Brand_Name", "Primary_Domain", "Core_Category",
    "Estimated_Ad_Spend_Tier", "Current_Status", "Historical_Social_Incidents",
    "Main_Competitor_Id", "Gtin_Prefix",
]

TOOL_SCHEMAS  = [...]        # the 8 JSON schemas
TOOL_DISPATCH = {"generate_search_queries": generate_search_queries, ...}
```

- Tool function name == schema name == dispatch key. A mismatch breaks dispatch correctness — guard it with an import-time `assert`.
- Avoid vague names (`tmp`, `res2`, `do_thing`). Helpers say what they do (`gateway_validate`, `apply_premium`, `cap_angles`, `dual_log`, `truncate_for_log`).

---

## 10. Non-negotiable quality rules (the short list)

1. **Import-safe.** No side effects at import (§3.4, `ENV4`).
2. **Frameworks permitted.** LangChain/LangGraph allowed (Asaf, 2026-06-19); raw tool-calling also fine. The old no-framework ban is lifted.
3. **No raw `eval`/`exec`.** `secured_calculator` is an AST walker; grep-clean (`G1`). *(This is the assignment's calculator security rule and stays.)*
4. **Catalog by name, validated on load.** Never positional, never hardcoded (§4).
5. **Policies are enforced at the boundary, not hoped for.** Auth gate, ≤3 ceiling, fallback string — each has a single chokepoint (§5).
6. **Byte-exact fallback.** `FALLBACK_MESSAGE` (Policy 6) is the one contractually exact string; log lines are a stable project convention (§7).
7. **Hard caps.** 15 tool calls, ≤100 domains/chunk, 800s budget — enforced, not advisory.
8. **Fail loudly in tools, never crash the loop.** Tool errors are data; uncaught exceptions are forbidden (§6.6).
9. **No secrets in tracked files.** Keys and `corporate_access_key` live only in the environment.
10. **TDD.** A stage is done only when its referenced `QA_checklist.md` checks are *run and pass*, not inspected.

---

## 11. Completion checklist (per stage)

- [ ] The section(s)/module(s) for this stage run without errors.
- [ ] The `QA_checklist.md` checks referenced by this stage's DoD all **pass** (run, not inspected).
- [ ] Import-safety holds (`import main` clean) (§3.4).
- [ ] No forbidden framework / no raw `eval`/`exec` (grep clean).
- [ ] Catalog accessed by name; no hardcoded catalog/sample values.
- [ ] Relevant policy chokepoints enforced and tested.
- [ ] Caps and budgets enforced per §6.5 / §6.
- [ ] Log + fallback literals byte-exact, dual-written.
- [ ] `NOTES.md` updated with decisions, verified facts, and a handback.
- [ ] `PLAN.md` status ready for PM review.

---

## 12. Claude Code handback format

When a stage is complete, report back with:

1. **What changed** — modules/sections drafted vs written; new tests; files touched.
2. **DoD checklist** — each referenced QA ID ✅ / ⚠️; separate *drafted only* from *written and test-verified*.
3. **QA results** — which check IDs were run and their pass/fail.
4. **Decisions made** — anything not explicitly specified (record in `NOTES.md`).
5. **Deviations** — anything different from `PLAN.md`, with reason.
6. **Blockers / risks** — unpinned deps, missing keys, flaky vectors, framework temptation, ambiguous PRD detail.
7. **Next recommended action** — one concrete next step only.

Do not silently advance to the next stage.
