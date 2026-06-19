# GTM Engine Knowledge Base — Idan Benaun (SLED AI), LangTalks 2026

> **Source:** Hebrew talk transcript "How we built a 6 layers GTM Engine" — https://www.youtube.com/watch?v=FwqlNpB5nRo
> **Audience for this doc:** a Claude Code PM/build agent (no access to the original video). Optimize for retrieval and reasoning.
> **Conventions:** Translated to English; non-LLM tool/service names preserved verbatim. **Specific LLM model names from the talk have been generalized to "an LLM"** so a builder can choose the model. `[unclear]` marks phonetic/ambiguous source audio. This describes the company's **internal GTM system (version 3)** — *not* its core product.

---

## System Overview

The company helps companies **win US government tenders/bids** ("מכרזים"). It targets the **US SLED segment** (State, Local, education — "state level and below"), explicitly **not Federal**. The market is ~**$2 trillion/year**, with ~**90,000 procuring entities**, each with its own portal (e.g., City of Tampa, FL → UC Berkeley).

The core problem: operating as a vendor here is painful — discovering relevant tenders, judging eligibility (threshold requirements buried in 50–150-page documents), and responding (a tender response is 40–100 pages, "like academic work"). The system below is the **internal GTM (go-to-market) engine** whose job is to **acquire customers by leveraging the company's strongest asset: its data**. Business model = **"revenue and service"**: clients onboard, typically next see the output when they *win* a tender, and the company shares in client wins.

**Traction cited:** 32 customers; hundreds of millions of dollars in tenders won for clients; outreach results (last 4 weeks) of 13 meetings booked and 2 clients closed.

---

## Architecture — The 6 Layers (+ a pre-layer)

> The talk has six slides; the pipeline is six stages plus one preceding stage. Layer boundaries are partly inferred from narration. Data flows strictly forward; each layer's output is gated before passing on.

### Pre-Layer 0 — Category / Market Arbitrage Mapping
- **Purpose:** Find verticals with **many tenders but few bidders** before any prospecting.
- **Key datum / heuristic:** **23% of tenders close with no winner** (no one bid). The system hunts this arbitrage and enters those categories.
- **Output:** A chosen category. **Worked example throughout: Marketing** (sub-segments: PR, SEO, branding, website building).
- **Feeds:** → Layer 1.

### Layer 1 — ICP Builder
- **Purpose:** Define the **Ideal Customer Profile** within the chosen category (who to target).
- **Inputs:** Either (a) a **seed selection** — an existing customer to find look-alikes of, optionally + a modifier (e.g., "similar company that *also* does PR"); or (b) a **free-text description** (example: "full service digital marketing company"). Plus explicit ICP constraints: want / don't-want, **location**, headcount, and other conditions.
- **Process:** Run **an LLM** over the seed/description to generate **keywords**. Return **sample companies** that would surface so the operator can sanity-check the ICP before scaling.
- **Output:** Structured ICP + keyword set + a numeric lead target (e.g., 300).
- **Feeds:** keywords → Layer 2.

### Layer 2 — Lead Search & Scoring (at scale)
- **Purpose:** Find leads matching the ICP. **A "lead" = a website link + a minimal profile of what the company does.**
- **Inputs:** ICP keywords; numeric target (e.g., 300/400/500; UI button "**find 150**").
- **Process (ordered):**
  1. **Query generator** turns ICP keywords into search queries via **an LLM**.
  2. Queries hit **Google Search via SERP API**.
  3. **Tavily** runs as a **backup/recovery search** — triggered when the lead target isn't reached (also surfaces newer/overlapping results).
  4. Run in a **loop** until the target (or near it) is reached.
  5. **Dedup** across all returned leads.
  6. **Score each lead/URL against the ICP**; only leads passing the score continue.
- **Infra:** Runs on **Vercel "agent workflows" / durable workflows** — agents run **long, stably, at serverless scale**.
- **Output:** Ranked, deduped, ICP-qualified lead list.
- **Feeds:** passing leads → Layer 3.

### Layer 3 — Company Profiling (deepen understanding)
- **Purpose:** For a qualified lead, build a deep profile.
- **Process:** Research what the company does in depth, its **market** and **competitors**; assemble a profile (attributes, headcount, offices, products, expertise, market, keywords).
- **Output:** Structured company profile.
- **Feeds:** profile + tender-search keywords → Layer 4.

### Layer 4 — Agentic RAG Tender Matching
- **Purpose:** ("Most important part") Match live tenders to the profiled company.
- **Inputs:** Company profile + tender-search keywords.
- **Process:** An **agentic RAG** searches across **~2 million live tenders** for matches to that specific company.
- **Gating rule:** Once **3–4+ matching tenders** are found (sometimes more, under certain conditions), the company is packaged forward.
- **Output:** Matched tenders with rough dollar value. **Worked example:** a creative agency → **18 tenders / ~$5.5M** total (rough estimate).
- **Feeds:** all accumulated data → Layer 5.

### Layer 5 — Leads Dashboard / Sales Workspace (mini-CRM)
- **Purpose:** Package everything into a **sales tool** the salesperson uses live in the meeting.
- **Contact-discovery sub-step (who to approach inside the company):** uses **Apollo** (emails) and **an LLM with grounded web search** (the presenter's strongest tool for "reaching the depths of the internet"). Also evaluated **Tavily** and **Nimble** ("excellent for other purposes").
- **Capabilities:** Mini-CRM; **Fathom** auto-ingests call summaries into the dashboard; record updates; **pre-meeting brief** and **post-meeting recap**; **look-alike / similar-tender search**; deck generation. Deck tool was initially **Gamma** (good API) but **replaced by an in-house generator** to fit their template — one-button summary deck. Decks present market, opportunities, business model, and **case studies** (e.g., a client taken from **zero government experience to $500K revenue in 6 months**, solely from government tenders).
- **Output:** A sales-ready workspace per lead.
- **Feeds:** → Layer 6 (which is what actually gets the prospect into the meeting).

### Layer 6 — Outreach Agent ("Vixen") — autonomous multi-channel
- **Purpose:** ("The hardest part") **Autonomously book a meeting** between the company's salesperson and a qualified prospect, **with no human involvement**.
- **Naming:** Two agents themed on Santa's reindeer (ties to "SLED"/sleigh): **Rudy** (a modest BizDev "opener," *not* part of this flow) and **Vixen** (manages outreach).
- **Inputs:** **3–5 cohorts ("courts") per week**, each = **100 leads**, with each company's email + the LinkedIn profiles of the people to approach.
- **Channels:** Email (sent across **multiple domain addresses** to avoid burning the primary domain), **LinkedIn**, and **"form farms"** (submitting contact forms on prospects' sites). Cadence example: LinkedIn request → form → email → another email after **3 days**.
- **Behavior:** **Morning brief**; **hourly heartbeat** ("how do I advance the mission?"); weekly mission = **reach ≥300 companies**. Validates email deliverability before sending. A/B-tests messaging. **Human-in-the-loop approvals**; if approval is not given, it **escalates** (sends email, books a calendar meeting with the manager) until answered.
- **Results (last 4 weeks):** **13 meetings booked**, **2 clients closed**, **reply rate 2.5%** ("not bad for this industry"). The **form bot** alone closed **3 deals** — nearly a mini-product: many marketing firms lack the product, so the relationship "flips" and the company sells to them.
- **Feeds:** logs/results (who replied, when, which A/B variant won) → an analytics dashboard (still being built). Current state: **4 active cohorts, 22 companies** in the full multi-touch flow.

**End-to-end data flow:** category arbitrage → ICP → scaled lead search + scoring → deep company profile → agentic-RAG tender match → sales-ready dashboard → autonomous multi-channel outreach → booked meeting → human salesperson closes.

---

## Features (discrete capabilities)

- Category arbitrage detection (high-tender / low-bidder verticals).
- Seed-based or description-based ICP definition with look-alike + modifier.
- Keyword generation from an ICP (LLM).
- Scaled lead discovery via SERP API (Google) with Tavily recovery.
- Looped search to a target count, with dedup and per-URL ICP scoring.
- Long-running serverless agent execution (Vercel agent/durable workflows).
- Deep company profiling (market, competitors, attributes).
- Agentic RAG over ~2M live tenders with a 3–4+ match gate.
- Contact discovery (Apollo + LLM-grounded web search).
- Mini-CRM lead workspace with Fathom call-summary ingestion.
- One-click pre-meeting brief, post-meeting recap, and in-house deck generation.
- Look-alike / similar-tender search.
- Multi-channel autonomous outreach: multi-domain email, LinkedIn (PhantomBuster), form-submission bot.
- Hourly heartbeat + morning brief + human-in-the-loop approval with auto-escalation.
- Email deliverability validation pre-send.
- A/B testing and outreach analytics dashboard.

---

## How to Build It (tooling, models, integrations, sequencing)

**LLM usage (model-agnostic — builder's choice):**
- An **LLM** for ICP keyword generation and search-query generation.
- An **LLM with grounded web search** for deep contact/web discovery (the presenter's strongest tool for this).
- **Agent SDK / framework:** built on an agent framework/SDK described as "very strong and easy to connect to Slack." (Phonetic, likely-garbled names from the audio: **Pi**, **OpenClaude**, **Hermes**, **Nanoclo**, **Pimono** — all `[unclear]`; treat the *capability* — a Slack-integrable agent SDK — as the requirement, not the specific name.) After a V1 failure they reverted to a simpler base and layered processes on top.

**Search / data services (non-LLM, kept verbatim):**
- **SERP API** (Google search via API) — primary lead search.
- **Tavily** — backup/recovery search.
- **Nimble** — evaluated ("excellent for other purposes").
- **Apollo** — contact emails.

**Infra / orchestration:**
- **Vercel** — hosting + **agent workflows / durable workflows** (long-running, stable, serverless-scale agents).
- **Slack** — where the Vixen agent "lives" and is managed (approvals, monitoring).
- **Memory: three layers** — `[unclear — possibly Supabase/Postgres]` + **MongoDB with a vector database** + a third store named ambiguously in the audio.

**Productivity / outreach integrations:**
- **Fathom** — meeting transcription → auto call summaries into the dashboard.
- **Gamma** — initial deck generation (good API), **later replaced by an in-house generator** (template fit).
- **PhantomBuster** (API) — LinkedIn automation (connections, messaging); given to Vixen as a "skill." (They tried building LinkedIn automation in-house — "a nightmare, don't do it.")

**Sequencing / dependencies:**
1. Map category arbitrage first.
2. Build the ICP (LLM) → keywords.
3. Query-gen → SERP API → (Tavily recovery) → loop → dedup → score.
4. Profile passing companies.
5. Agentic-RAG tender match (≥3–4 tenders to pass).
6. Assemble the dashboard (Apollo + LLM-grounded search for contacts; Fathom; decks).
7. Outreach via Vixen (cohorts of 100; 3–5/week) on the agent framework + durable workflows, with PhantomBuster, multi-domain email, and the form bot.

**Build history:** The GTM engine is on its **third version**. The Vixen outreach piece went to **production ~3 weeks ago** and was already **rebuilt as V2** because V1 didn't work.

---

## Key Explanations & Rationale

- **Why arbitrage first:** With 23% of tenders closing with no winner, targeting low-competition categories maximizes client win-rate — which directly drives the company's revenue-share model.
- **Why data-led outreach:** Approaching a prospect with concrete tender matches (named tenders, dollar value, deadlines — e.g., "you could earn $2M/year; this tender closes in 2 months") is far more compelling than generic outreach; the prospect immediately sees the upside.
- **Why the outreach agent is the hardest part:** Getting a prospect into a meeting is "the most fortified part" — simple on paper, very hard to make autonomous (hence the full V1 scrap-and-rebuild).
- **Why they reverted frameworks (V1 → V2):** The core failure was **"sharpness"** — hitting a relatively basic goal — undermined by **high verbosity** and **complex memory management**. Reverting to a simpler base and layering capabilities restored reliability.
- **Don't build LinkedIn automation yourself:** Use **PhantomBuster**; in-house attempts were "a nightmare."
- **Protect your sending domain:** Send across **multiple domain addresses** so mass email doesn't burn the primary domain.
- **Human-in-the-loop with teeth:** The agent requests approvals and **escalates** (email, calendar invite) when ignored — "an escalation that actually works."
- **Agent-as-employee framing:** Morning brief, hourly "how do I advance the mission," weekly quota of 300 companies. The goal is to place the salesperson in a meeting "without us involved."
- **Build vs. buy on decks:** Started with Gamma's API; switched to an in-house generator when it couldn't meet template requirements.

---

## Flagged Ambiguities (verify against the video)

- **Agent framework/SDK stack:** Pi / OpenClaude / Hermes / Nanoclo / Pimono — phonetic guesses; names likely garbled.
- **Third memory layer** ("Sa-markada") — possibly Supabase/Postgres.
- **ICP seed UI reference** ("the MotherDuck data" / "מעל המותק דאטה") — unclear.
- **"BizdoWin Floy"** (V1 reference) — likely "BizDev flow."
- **Tender-volume threshold** ("not 10 tenders/year, I want 10 tenders per ___") — `בריבון` likely means **"per quarter"**, but unclear.
- **Rudy "works 2008"** — unclear (possibly "runs on an older/different stack").
- **Outreach pitch phrase** ("wide global service" / "וייד גלב סרוויס") — possibly "wide gov service"; meaning is end-to-end ("A-to-Z") tender service.
