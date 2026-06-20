# FINDINGS — SLED.ai 6-Layer GTM Engine vs. our ReactFirst pipeline

> **Author:** PM review session, 2026-06-19.
> **Audience:** a fresh PM agent (no memory of the originating conversation) whose job is to edit `PLAN.md` and dispatch `swe-executer` subagents.
> **Scope:** This is a **findings / gap-analysis brief only — logic, not UI.** It contains **no build plan and no implementation.** Every claim below carries a *validation pointer* so you can verify it yourself before acting. Do **not** treat any "gap" here as an approved work item — Asaf has not chosen a direction yet (see §7 Open Questions).

---

## 0. How to use this document

1. Read this top-to-bottom, then independently re-run the validation commands in §8 — do not trust the line numbers blindly; the code shifts as it's edited.
2. The per-layer table in §5 is the core deliverable. Each row says **Have / Partial / Missing** and tells you exactly where to confirm it (a `file:line`, a slide, or a KB section).
3. Before writing anything into `PLAN.md`, resolve the two Open Questions in §7 with Asaf — they decide *what* the next stages even are.

---

## 1. Source material (provenance)

Three sources, all in the repo:

- **`GTM_Engine_KB_SLED_AI.md`** — a translated/structured summary of the Hebrew talk *"How we built a 6 layers GTM Engine"* by **Idan Benaun (SLED AI)**, LangTalks 2026 (YouTube `FwqlNpB5nRo`). This is the primary text source. It describes SLED's **internal GTM system (v3)** — not their product.
- **`Images/Screenshot 2026-06-19 at *.png`** — 9 screenshots of the talk's architecture slides + product UI. Most useful for validation:
  - `...9.03.19.png` — the 6-layer overview slide ("One pipeline. Six layers.").
  - `...9.03.48.png` — **Layer 2 "Search & Explore"** architecture (Query Generator → 3-way fanout → Lead Extractor → Unified Scorer). **This slide is near-identical to our `execute_3way_fanout`.**
  - `...9.04.17.png` — **Layers 3+4+5** ("Leads Swarm" + "Leads Dashboard") boxes: Company Analyzer / Tag Evaluator / Solicitation Matcher / Profile Expander, then Lead Workspace / SLED Deck+Win-Prob / Export Engine.
  - `...9.03.26.png` — **Layer 1 "ICP Builder"** 4 stages (Seed Selection → Vertical Research → ICP Synthesis → Example Leads).
  - `...9.07.01.png` — **Layer 6 "Outreach Engine"** (Scheduler/cron, Vixen v2, Personas, Resend email, PhantomBuster LinkedIn).
  - `...9.07.17.png` — **Layer 6 "Outreach Center"** analytics (cohorts, variants, reply-rate dashboard).
  - `...9.03.36 / 9.03.43 / 9.04.11.png` — ICP Builder + Lead Discovery product UI (UI-only; ignore for logic).

> **Critical framing:** SLED's domain is **US government tenders (SLED procurement)**. Our codebase ("ReactFirst") is a **crisis-narrative / brand-safety outreach** engine. Our project (per `Assigment.md` and `CLAUDE.md`) is a **re-skin of SLED's 6-layer architecture onto a different domain.** The tool *names and mechanics* line up almost 1:1; the *subject matter* (tenders ↔ crisis angles; Apollo contacts ↔ a fixed mongomock CRM) differs. Keep that mapping in mind for every row below.

---

## 2. Decisions already applied this session (validate before relying on them)

These landed in the working tree on 2026-06-19 and are reflected in the code/tests:

1. **Premium pricing (Policy 3) was removed.** `apply_premium`, the `PREMIUM_MULTIPLIER`/`INCIDENT_PREMIUM_THRESHOLD` constants, the `Policy 3` block in `gtm_policies.txt`, the premium framing in tool schemas, and the `PR1`–`PR4` tests are all gone. This is a **deliberate deviation from `Assigment.md`** (which defines Policy 3 + a Q1 query that exercises it) — accepted by Asaf.
   - *Validate:* `grep -rniE "apply_premium|premium_multiplier|policy 3" main.py gtm_policies.txt` → should be empty. See `CLAUDE.md` §5 Policy 3 (marked REMOVED).
2. **The "no framework" ban was lifted.** LangChain / LangGraph / `create_react_agent` / `AgentExecutor` are now **permitted** (the ban was self-imposed in `CLAUDE.md`, never in `Assigment.md`). The **`eval`/`exec` ban stays** — but only for `secured_calculator`, because that one *is* an assignment requirement.
   - *Validate:* `CLAUDE.md` §6.7 and §10 rule 2 (both updated 2026-06-19); `grep -ic "langchain\|langgraph" Assigment.md` → `0`.

---

## 3. Current build state (as of this brief)

- **Full test suite:** `471 passed, 1 skipped, 0 failed` (the skip is `S10`, gated on a missing `ANTHROPIC_API_KEY`).
  - *Validate:* `.venv/bin/python -m pytest tests/ -q`
- **Stages 1–8** were PM-verified previously; **Stage 9** (integration tests + packaging) was the last in flight.
- **⚠️ Caveat — concurrent external edits this morning:** `tests/test_integration.py` was modified at **08:52 on 2026-06-19** and `qualified_leads.json` / `reactfirst_run.log` were regenerated at **08:32**, *during* the review session, by a process this session did not launch (likely a `pm-run`/orchestration loop or a scheduled run). That external edit fixed 3 Stage-9 test failures (rewrote the `INT1b` subdomain check to skip docstrings; taught `H1` that `rag_engine` is local and `serpapi`→`google_search_results`). **Before you dispatch any executer, confirm with Asaf whether another orchestration loop is running** — concurrent writers will collide.

---

## 4. The system we actually have (one-paragraph orientation)

`main.py` is a raw Anthropic tool-calling loop (`answer_question`, [main.py:2184](main.py:2184)) over **8 tools**, with `lead_store.py` (mongomock CRM + auth gate) and `rag_engine.py` (Chroma + BM25 + RRF). It takes a conversational query, optionally discovers/qualifies brands, matches an outreach *angle*, produces a single PDF asset, and writes `qualified_leads.json`. Governance: Policy 1/2/4/5/6 + Trust-Gate (Slack) + a Tool Gateway. **The pipeline terminates at "qualified leads + a PDF" — it never actually performs outreach.**

---

## 5. Layer-by-layer cross-reference (the core finding)

Legend: ✅ Have · ⚠️ Partial · ❌ Missing.

### Pre-Layer 0 — Category / Market Arbitrage Mapping — ❌ Missing
- **SLED:** find verticals with many tenders / few bidders (the "23% of tenders close with no winner" arbitrage) *before* prospecting. → *KB §"Pre-Layer 0"; slide `9.03.19.png`.*
- **Us:** none. The pipeline receives `vertical_seed` as a given input; there is no category-discovery or arbitrage-scoring step.
- **Validate:** `generate_search_queries(vertical_seed,...)` at [main.py:302](main.py:302) — its input *is* the seed; nothing produces the seed. `grep -niE "arbitrage|category.*discover" main.py` → empty.

### Layer 1 — ICP Builder — ⚠️ Partial
- **SLED:** seed company OR free-text → LLM vertical research (grounded) → **structured ICP document (v3 schema)** with want/don't-want, location, headcount → **5 sample "anchor" companies** for operator sanity-check. → *KB §"Layer 1"; slides `9.03.26.png`, `9.03.36.png`.*
- **Us:** `generate_search_queries` turns a seed into 10–20 search-query variations (LIGHT model). That's it. **No** structured ICP-document synthesis, **no** constraints object (location/headcount/want-list), **no** anchor-company preview. Our "ICP" only exists *downstream* as the ≥3-tag boolean gate.
- **Validate:** `generate_search_queries` [main.py:302](main.py:302) (query gen ✅); `evaluate_icp_tags` [main.py:873](main.py:873) (the ≥3-tag gate is our only "ICP", `ICP_TAG_THRESHOLD` at [main.py:49](main.py:49)). No ICP-doc builder exists → `grep -niE "icp_document|synthesi|anchor|sample_compan" main.py` → empty.

### Layer 2 — Search & Explore (lead search & scoring at scale) — ✅ Have (strongest match)
- **SLED:** Query Gen → **3-way fanout** (Gemini Discovery ∥ SerpAPI+Maps ∥ **Tavily recovery when < 2 results**) → Lead Extractor (domain dedup) → Unified Scorer; **looped to a numeric target** ("find 150"). → *KB §"Layer 2"; slide `9.03.48.png` — this slide is essentially our architecture.*
- **Us:** near-identical. `generate_search_queries` = Query Gen; `execute_3way_fanout` = Vector A (Claude `web_search`, replacing Gemini) ∥ Vector B (SerpAPI+Maps) ∥ Vector C (Tavily, fires **iff A∪B < 2** — same rule); `extract_and_score_pool` = Lead Extractor (dedup by normalized domain + catalog map).
- **⚠️ Gaps:** we do a **single pass**, not a loop-to-N-target; no durable/serverless long-run (SLED uses Vercel agent workflows); our per-URL "scoring" is lighter than their Unified Scorer.
- **Validate:** `execute_3way_fanout` [main.py:466](main.py:466); the `< 2` recovery rule at [main.py:520](main.py:520) and `FANOUT_RECOVERY_THRESHOLD=2` [main.py:52](main.py:52); `extract_and_score_pool` [main.py:564](main.py:564). No target-count loop → the loop cap is the global `TOOL_CALL_CAP=15`, not a lead-count loop.

### Layer 3 — Company Profiling — ⚠️ Partial (mechanics match, output shallow)
- **SLED:** Company Analyzer (Firecrawl, **100 leads/chunk**) → deep profile: market, competitors, headcount, offices, products, expertise. → *KB §"Layer 3"; slide `9.04.17.png` (left box).*
- **Us:** `analyze_company_chunk` matches the **mechanics exactly** — Sonnet + Firecrawl, **≤100 domains/chunk**, **800s budget**, partial results on timeout. But the **output is narrow**: it extracts **pixel flags (TikTok / Meta / GTM)** + some text patterns — not a market/competitor/headcount profile. Competitor data exists only as the catalog FK `Main_Competitor_Id`, never researched.
- **Validate:** `analyze_company_chunk` [main.py:805](main.py:805); `CHUNK_MAX_DOMAINS=100` [main.py:50](main.py:50); pixel-only output is visible in the function's return dict (`tiktok_pixel`/`meta_pixel`/`gtm`). `grep -niE "headcount|competitor|offices|market" main.py` → essentially absent in tool 4.

### Layer 4 — Agentic RAG Matching — ⚠️ Partial (same mechanic, different corpus & output)
- **SLED:** agentic RAG over **~2 million live tenders** → match opportunities to a company → gate at **3–4+ matches** → output matched tenders **+ rough $ value** (worked example: 18 tenders / ~$5.5M). → *KB §"Layer 4"; slide `9.04.17.png` ("Solicitation Matcher — RRF fusion · vector + BM25 · 4-tier grade").*
- **Us:** `match_solicitation_angle` is hybrid RAG — Chroma semantic + BM25 → **RRF → Tier 1–4** — which **matches their slide's mechanic exactly**. But the corpus is **`angle_corpus.json` = 12 crisis-PR case-study "angles"**, not a live opportunity index; it returns **one best angle**, not N opportunities + dollar values. (Our ≥3-tag ICP gate is the analog of their 3–4 match gate.)
- **Validate:** `match_solicitation_angle` [main.py:935](main.py:935); fusion in `rag_engine.py` — `rrf_fuse` [rag_engine.py:372](rag_engine.py:372), `score_to_tier` [rag_engine.py:438](rag_engine.py:438); corpus = `angle_corpus.json` (12 entries — `python -c "import json;print(len(json.load(open('angle_corpus.json'))))"`). No dollar-value or multi-match output.

### Layer 5 — Leads Dashboard / mini-CRM — ⚠️ Minimal
- **SLED:** workspace + **contact discovery (Apollo emails + LLM grounded web search)** + Fathom call-summary ingestion + **pre/post-meeting briefs** + **in-house deck generation** (was Gamma) + Export (PDF/HTML) + look-alike + win-probability. → *KB §"Layer 5"; slide `9.04.17.png` (right boxes: Lead Workspace / SLED Deck+Win-Prob / Export Engine).*
- **Us:** a **static** CRM store (`lead_store.py`, mongomock from `contacts.json`) behind the Policy-4 auth gate ✅, plus **one** Export-Engine output: `request_reactfirst_pdf` (single PDF) ✅. `qualified_leads.json` ≈ their "saved_lists". **No** contact *discovery* (no Apollo/grounded search — contacts are a fixed file), no decks, no briefs/recaps, no Fathom, no win-prob, no look-alike, no Notion sync.
- **Validate:** `lead_store.get_lead_data_collection` [lead_store.py:24](lead_store.py:24), `authenticate_and_get_contact` [lead_store.py:50](lead_store.py:50); `request_reactfirst_pdf` [main.py:1061](main.py:1061); `write_qualified_leads` [main.py:2546](main.py:2546). `grep -niE "apollo|fathom|deck|win.?prob|notion|look.?alike" main.py` → empty.

### Layer 6 — Outreach Agent "Vixen" — ❌ Largely absent (biggest gap; founder calls it the hardest/most valuable layer)
- **SLED:** autonomous multi-channel outreach — scheduler/cron, **multi-domain email (Resend)**, **LinkedIn (PhantomBuster)**, **form-submission bot**, cohorts of 100 (3–5/week), **morning brief**, **hourly heartbeat**, deliverability validation, A/B testing, **human-in-the-loop approval with auto-escalation** (email + calendar invite), analytics dashboard. → *KB §"Layer 6"; slides `9.07.01.png`, `9.07.17.png`.*
- **Us:** only *shadows* of this exist — nothing actually sends:
  - `route_prospect` ([main.py:1986](main.py:1986)) routes borderline (exactly-3-tag) leads to a **Slack webhook** for human approval (Trust-Gate). This ≈ their human-in-the-loop, but there is **no escalation, no calendar, no cohorts**.
  - `OUTREACH_SUBDOMAIN="outreach.reactfirst.ai"` ([main.py:94](main.py:94)) is a **routing constraint** (only `request_reactfirst_pdf` may egress there), not a sender.
  - `DAILY_SEND_CAP=50` ([main.py:54](main.py:54)) is **defined but never used** (dead constant).
  - **No** email/LinkedIn/form sending, **no** scheduler/cron, **no** heartbeat, **no** morning brief, **no** A/B test, **no** deliverability check, **no** personas, **no** analytics.
- **Validate:** `grep -rinE "apollo|phantombuster|resend|linkedin|form.?bot|cohort|heartbeat|morning brief|escalat|scheduler|cron|send_email|deliverab" main.py lead_store.py rag_engine.py` (exclude `linkedin_url`) → only the Slack/route_prospect shadows appear; `grep -rn "DAILY_SEND_CAP" main.py` → single defining line only.

---

## 6. Scorecard

| Layer | Verdict | One-line reason |
|---|---|---|
| 0 — Category Arbitrage | ❌ Missing | seed is an input, not discovered |
| 1 — ICP Builder | ⚠️ Partial | query-gen yes; ICP doc + anchors no |
| 2 — Search & Explore | ✅ Have | 3-way fanout + `<2` recovery is faithful |
| 3 — Company Profiling | ⚠️ Partial | right ceilings (100/800s); pixel-only output |
| 4 — Agentic RAG Matching | ⚠️ Partial | RRF+4-tier mechanic ✅; tiny angle corpus, 1 match, no $ |
| 5 — Dashboard / mini-CRM | ⚠️ Minimal | static CRM + 1 PDF; no discovery/decks/briefs |
| 6 — Outreach Agent (Vixen) | ❌ Missing | nothing sends; only Slack/route shadows |

**Net:** ~2 layers genuinely present (2, and the mechanic of 4), ~3 partial (1, 3, 5), ~2 missing (0, 6). The two weakest areas — **Pre-Layer 0 (arbitrage)** and **Layer 6 (outreach)** — are the ones the founder frames as highest-leverage. We also have **governance** (auth gate, ≤3 ceiling, Policy-6 fallback, Tool Gateway) that SLED's talk does not emphasize — that's *ours*, keep it.

---

## 7. Open questions for the new PM (resolve with Asaf BEFORE editing PLAN.md)

1. **Domain:** stay in our crisis-narrative / brand-safety domain (re-skin), or pivot toward SLED's actual tender domain? This changes what Layers 3–5 should profile/match and whether the 12-entry angle corpus stays.
2. **Priority / scope:** which gaps (if any) become new stages? The obvious high-value target is **Layer 6 (outreach agent)**, enabled upstream by a **real Layer 1 (ICP builder)** — but **no direction has been approved.** Do not assume a build.

> Asaf explicitly declined a build plan in the session that produced this brief. This document is **findings only.** Turning any row above into a `PLAN.md` stage requires Asaf's go-ahead and a Definition-of-Done with `QA_checklist.md` IDs, per the existing methodology.

---

## 8. Validation commands (run these to confirm everything above)

```bash
cd /Users/asaframati/Documents/CRM
# Test baseline
.venv/bin/python -m pytest tests/ -q

# Decisions applied this session
grep -rniE "apply_premium|premium_multiplier|policy 3" main.py gtm_policies.txt   # → empty
grep -ic "langchain\|langgraph" Assigment.md                                       # → 0

# Layer presence checks
grep -niE "arbitrage|category.*discover" main.py                                   # L0 → empty
grep -niE "icp_document|synthesi|anchor|sample_compan" main.py                     # L1 → empty
grep -n "FANOUT_RECOVERY_THRESHOLD\|execute_3way_fanout" main.py                   # L2 → present
grep -niE "headcount|competitor|offices" main.py                                   # L3 → ~absent in tool 4
python -c "import json;print(len(json.load(open('angle_corpus.json'))))"           # L4 → 12
grep -niE "apollo|fathom|deck|win.?prob|notion|look.?alike" main.py                # L5 → empty
grep -rinE "phantombuster|resend|cohort|heartbeat|scheduler|cron|send_email" main.py  # L6 → empty
grep -rn "DAILY_SEND_CAP" main.py                                                  # L6 → 1 line (dead)
```

Line numbers in §5 were accurate at authoring time (post premium-removal) but **re-grep** the function names rather than trusting the numbers — the file is edited frequently.
