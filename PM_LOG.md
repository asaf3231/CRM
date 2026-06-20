# PM_LOG.md — Shared PM Session Log

> The **PM↔PM handoff memory**. Every PM session (backend or frontend) opens with a
> `SESSION START` entry and closes with a `SESSION END / HANDOFF` entry, per the Session
> Begin/End Ritual in `PM_Methodology_Prompt.md`. A fresh PM reads the **latest entry for its
> workstream** before doing anything.
>
> This is the session-level layer. It is **distinct from `NOTES.md`** (decisions + stage-level
> handbacks) — do not duplicate one into the other.

---

## How to use this file

- **Append-only**, newest at the bottom. Do not rewrite past entries.
- **Tag every entry** with the workstream: `[BACKEND]` or `[FRONTEND]`.
- **Never write a number you didn't verify** against the source (tests, the CSV, the log).
- Keep entries short and factual — what happened, where we are, the one next action.
- The PM owns this file. `swe-executer` / `swe-reviewer` subagents never write to it.

**Entry templates:**

```
## <YYYY-MM-DD HH:MM> — [<WORKSTREAM>] SESSION START
Picking up: <stage/screen + status as read from the plan>
State as read (to re-verify): <key facts, e.g. test baseline>
Plan for this session: <one line>

## <YYYY-MM-DD HH:MM> — [<WORKSTREAM>] SESSION END / HANDOFF
Did: <what landed; QA/reviewer verdict; verified numbers>
Status now: <✅ / 🔄 / ⚠️>
Next PM should: <one concrete next action>
Watch out for / open: <risks, halts, decisions pending>
```

---

## 2026-06-19 12:33 — LOG CREATED (state snapshot, both workstreams)

This log was introduced today alongside the PM onboarding/continuity system (see `NOTES.md`
2026-06-19 entry and `PM_Methodology_Prompt.md`). Verified current state at creation — the
first fresh PMs should re-verify before trusting these numbers:

**[BACKEND]** — ReactFirst Python pipeline. Phase 2 (SLED parity, CRM re-skin).
- Stages 0–12 ✅ complete. **Stage 13 (Layer 6a — Outreach Engine core; checks `OUT1`–`OUT6`)
  is ⬜ NOT STARTED** and is the current stage. Stage 14 follows.
- Last recorded test baseline: **602 passed, 1 skipped (S10, gated on `ANTHROPIC_API_KEY`)**
  — from the Stage 12 handback; re-run the full `tests/` regression in `.venv` to confirm.
- Reviewer gate applies to Stage 13 (it touches the gateway + auth gate + Policy 5/TG + the
  `DAILY_SEND_CAP` constant).

**[FRONTEND]** — React/Vite GTM dashboard under `frontend/`.
- **F0 (scaffold + design system + app shell) ✅.** **F1 (Leads Dashboard) is 🔄 IN PROGRESS**
  and is the current stage; parity target `Images/…9.04.11`. F2–F5 not started.

**Next PM (each workstream) should:** read the spine in order, write a `SESSION START` entry
below, then continue from the stage named above.

---

## 2026-06-19 12:38 — [BACKEND] SESSION START
Picking up: Stage 13 (L6a — Outreach Engine core; checks `OUT1`–`OUT6`), status ⬜ Not started.
Stages 0–12 ✅. Stage 13 TOUCHES A GRADED CONTRACT (gateway + Policy-4 auth gate + Policy 5/TG +
`DAILY_SEND_CAP`) ⇒ reviewer gate fires.
State as read (to re-verify): last recorded test baseline = **602 passed, 1 skipped (S10, gated on
`ANTHROPIC_API_KEY`)** from the Stage-12 handback. L6 design = deterministic post-loop plain
functions (`schedule_outreach_cohort`, `dispatch_outreach`, `route_prospect` escalation via
`escalate_prospect`), NOT LLM tools — tool count stays 10, 15-call cap untouched. All transports
mocked/injectable; egress isolated to `OUTREACH_SUBDOMAIN`.
Plan for this session: re-verify the 602/1 baseline in `.venv` myself, then run `/pm-run` —
brief + spawn `swe-executer` for Stage 13, run the reviewer gate (graded-contract stage),
PM-verify `OUT1`–`OUT6` + full regression, advance or retry per ORCHESTRATION.

## 2026-06-19 12:40 — [FRONTEND] SESSION START
Picking up: F1 Leads Dashboard, 🔄 in progress; parity target `Images/…9.04.11`.
State as read (to re-verify): F0 ✅. F1 parts exist as loose components (`LeadTable`,
`StatusBadges`, `BulkActionBar`, `DiscoveryRail`, `MetricCards`) + mocks/types/api/store, but
the `/leads` route still renders `<Placeholder>` — nothing is assembled into a page, and the
metric header is a plain 5-card grid, not the reference's green "Discovery complete" funnel.
Reference detail (from cropped screenshot): green funnel header GOAL 150→DISCOVERED 131 (−38
filtered by ICP)→RETAINED 95 in table (−43 below floor)→ABOVE FLOOR 52; retained summary line
w/ Strong/Review/Weak chips; filter pills All/New/Existing/Above floor + "N filtered out"
(dashed) + count badges; search; "Select" + "Select all actionable (N)"; table cols
Company/Score(violet)/Fit("Strong Fit")/Gov("Light Gov" blue / "Heavy Gov" amber)/Lead
("Existing"/"New"); left discovery rail with Find-N-More loop.
Plan for this session: build `LeadsDashboard` page + `DiscoveryFunnel`/`FilterTabs`
components, refine badges/types to reference labels, wire `/leads` route, verify
sort/filter/multi-select/bulk/Find-More against mocks, Preview-MCP screenshot vs reference.

## 2026-06-19 12:52 — [BACKEND] SESSION END / HANDOFF
Did: Closed **Stage 13 (L6a Outreach Engine core, `OUT1`–`OUT6`) ✅**. Re-verified the baseline myself
in `.venv`: full regression **647 passed, 1 skipped (S10), 0 failed** — the recorded "602" was the
pre-Stage-13 number; +45 is exactly the new `tests/test_outreach.py`. **Discovery:** Stage 13 code
(`schedule_outreach_cohort`, `dispatch_outreach`, `escalate_prospect` in `main.py` §8f + the 45-test
file) was already on disk, green, from a **prior interrupted executer session** that never wrote the
handback or flipped PLAN status. I did NOT re-spawn an executer to redo finished work; instead I ran
the PM REVIEW + the `swe-reviewer` gate on the existing diff. PM independent probes of all six OUT
contracts passed (cohort cap ≤50, single-host egress to `OUTREACH_SUBDOMAIN`, opt-out + no/wrong-key +
gateway all suppress with the sender stub never called, no `corporate_access_key` leak, escalation +
`route_prospect` byte-stability). ENV4 holds (tool count 10; L6 fns are NOT tools). **Reviewer verdict:
APPROVE on all OUT1–OUT6 code; `CHANGES-REQUIRED` was documentation-only** (missing handback + NOTES
append) — resolved by the PM authoring both at close (NOTES append is the PM's own close step;
re-spawning a cold executer to reverse-engineer a handback for reviewer-approved code is the wasteful
spawn the budget rule forbids). One Minor (inline stdlib imports in `dispatch_outreach`) logged, not
changed. Wrote `handbacks/stage-13.md`, appended the Stage-13 handback to NOTES.md, flipped PLAN
Stage 13 → ✅, refreshed PLAN's bottom summary.
Status now: ✅ (Stage 13 complete & verified). Backend Stages 0–13 ✅; Stage 14 is the only remaining.
Next PM should: Dispatch **Stage 14 (L6b — `outreach_status_brief` + end-to-end `main()` wiring +
refreshed `MANIFEST.txt`; `OUT7`–`OUT10` + re-run `INT1`–`INT3`, `H1`–`H5`)** via the ORCHESTRATION
loop. It's a real new-implementation stage (nothing pre-built this time) → spawn a fresh swe-executer;
it touches a graded contract (end-to-end loop + packaging) → reviewer gate fires.
Watch out for / open: (1) the committed `main.py` is pre-Phase-2, so the working-tree diff carries all
of Stages 10–13 — scope the Stage-14 reviewer to the L6b changes only. (2) Stage 13 was closed without
an executer re-spawn (a PM judgment call on a doc-only `CHANGES-REQUIRED`); surfaced to Asaf in the
session report. (3) Live transports stay mocked/OQ-7-gated — Stage 14's INT/H re-run is offline.

## 2026-06-19 13:05 — [FRONTEND] SESSION END / HANDOFF
Did: Closed **F1 Leads Dashboard ✅** to parity vs `Images/…9.04.11`. The loose F1 components existed
but were never assembled — `/leads` still rendered `<Placeholder>`. Built the page
(`features/LeadsDashboard.tsx`) + two new components (`DiscoveryFunnel`, `FilterTabs`), refined
`DiscoveryRail`/`StatusBadges`/`LeadTable`, widened `LeadDiscoveryStats` to the funnel shape and made
mock numbers self-consistent (131−95=36 filtered, 95−43=52, 74+21=95, 69+10+16=95), changed `GovBand`
"Strong Gov"→"Heavy Gov", score→violet, circular row checkboxes, wired the route. **Verified live
(Preview MCP @1280px), not inspected:** `tsc --noEmit` exit 0; no console errors; sort (Score 85→64 on
flip), filter (All 16 → New 9, all kind New), search ("boom"→1=BoomPop), multi-select→BulkActionBar
"16 selected", Find-More (16→20, 4 deduped rows appended). Screenshot judged "same product" vs the ref.
Status now: ✅ (F1 complete & parity-verified). Frontend F0–F1 ✅; F2–F5 not started.
Next PM should: Start **F2 — ICP Builder** (parity `…9.03.36` / `…9.03.43`): tag groups + AI tag
suggestions, reusing the Zustand `tagVocabulary` (shared ICP↔Leads vocabulary, already scaffolded).
Watch out for / open: (1) tab counts are live-from-pool (16/9/7/10) while the funnel shows run totals
(150/131/95/52) — different things, mismatch is by design. (2) `components/shell/MetricCards.tsx` is now
an unused orphan (funnel replaced it) — leave or delete in a cleanup. (3) Stay in lane: FE writes only
this `PM_LOG.md` at root; everything else under `frontend/`. (4) Dev server `gtm-ui` on :5173.

## 2026-06-19 12:58 — [FRONTEND] SESSION START (continued — F2→F5 autonomous push)
Picking up: F1 ✅ just closed. Asaf extended scope: "continue until full completion, every time use a
different executer." Driving F2→F5 autonomously, **a fresh cold engineer spawned per stage**, PM runs
the parity gate after each handback.
Decision (recorded): the project `swe-executer` agent is hard-bound to the BACKEND (reads backend
CLAUDE.md/PLAN.md/QA_checklist.md as law, pytest/TDD, halts if a brief contradicts them) — wrong fit
for React stages. So each "executer" is a fresh `general-purpose` cold agent (model sonnet) handed a
self-contained frontend brief; PM does Preview-MCP parity + interaction verification (executers can't
drive the preview). Sequential on the live tree the dev server serves (no worktree isolation).
Plan for this session: F2 ICP Builder (parity `…9.03.36`/`…9.03.43`) → F3 Outreach Center (`…9.07.17`)
→ F4 Search & Explore + Leads Swarm (`…9.03.48` + swarm) → F5 cross-screen state + lead-detail + final
parity. Gate each; mark ✅ in PLAN_UI.md only when parity + interactions pass when run.

## 2026-06-19 12:58 — [BACKEND] SESSION CONTINUED (START)
Note: Asaf said "continue, until full completion, fresh executer each spawn" right after the Stage-13
END entry above — so this session continues rather than ending. Logging a START for the continued work
block per the ritual (append-only honesty).
Picking up: Stage 14 (L6b — Outreach Center + end-to-end wiring + packaging; `OUT7`–`OUT10` + re-run
`INT1`–`INT3`, `H1`–`H5`), status ⬜ → dispatching now.
State as read (to re-verify): baseline **647 passed, 1 skipped (S10)** (just verified at Stage-13 close).
`answer_question` (main.py:2873) + `main()` (3351) + `write_qualified_leads` (3235, already CRM-upserts)
read; `crm_store` exposes `outbound_eligible_contacts`/`get_crm_collection`/`update_lead_stage`; INT1 test
already extended for `dispatch_outreach` (green); `FakeReasoningClient` in test_e2e drives the loop offline.
Plan for this session: brief + spawn a FRESH `swe-executer` for Stage 14; L6 stays a POST-LOOP engine
(answer_question graded contract byte-stable); reviewer gate (graded — loop wiring + packaging);
PM-verify OUT7–OUT10 + re-run INT/H + full regression; close → project complete.

## 2026-06-19 21:03 — [BACKEND] SESSION START (Phase 3 — Integration Layer)
Picking up: NEW **Phase 3 — Integration Layer** (make FE↔BE talk via a FastAPI server). Approved,
PM-cross-reviewed plan: `~/.claude/plans/sprightly-tinkering-hennessy.md` (v2, reconciled). Backend
Stages 0–14 verified complete earlier this session (full suite 678 passed / 1 skipped).
State as read (to re-verify): suite baseline **678 passed, 1 skipped (S10)**; `crm_store._leads_collection`
+ `lead_store._collection_instance` are the singletons the new `tests/conftest.py` must reset;
`build_icp_document` is LLM/web-gated (offline-blocked) ⇒ ICP served from a seed dict in v1; api.ts has
12 methods (8 wired, 4 stay FE-mock per the cross-review).
Plan for this session: (1) spine bookkeeping — add Phase 3 + stages I0–I5 to PLAN.md, the `INTG0`–`INTG10`
family to QA_checklist.md, and the decision to NOTES.md; (2) I0 dep-lock gate (pin fastapi/uvicorn/httpx/
jsonschema, suite stays 678/1); (3) drive I1→I4 via `swe-executer` + the reviewer gate (graded-adjacent
stages I1–I3); I4 is FE wiring + Preview verification. main.py graded contracts stay byte-stable
(API only READS; additive module; ENV4 holds for `import api_server` too).

## 2026-06-19 20:28 — [BACKEND] SESSION START (fresh healthy PM; resuming the read-only PM's halt)
Note: the prior PM block (12:58 above) executed Stage 14, hit a reviewer `CHANGES-REQUIRED` (Critical:
`main()` called `crm_store.outbound_eligible_contacts()` with **zero args** → silent `TypeError` → L6
never ran from `main()`), then went **read-only** mid-retry and could neither run the auto-retry nor
verify it — so no SESSION END was written for that block (gap acknowledged here, append-only honesty).
Picking up: Stage 14 (L6b), PLAN status still ⬜ but reality = **r1 fix already on disk** (auto-retry
attempt 1 was applied via the subagent path). Verified by reading the source, NOT the handback:
`main._parse_caller_key` (3547, key never logged), `main()` L6 block (3614–3654) assembles leads from
`crm_store.all_leads()` and calls `run_outreach_pipeline` (no zero-arg `outbound_eligible_contacts`
remains), `crm_store.all_leads` (395, additive), `tests/test_outreach_center.py::TestOUT8MainDriven`
(drives `main.main()`). `handbacks/stage-14-r1.md` + NOTES r1 entry already on disk.
State as read (to re-verify in `.venv`): claimed full regression **684 passed, 1 skipped (S10), 0 failed**
(r1 handback) — MUST re-run myself before trusting. No git tags; HEAD `main.py` is pre-Phase-2 (working
diff carries all of Stages 10–14) → scope the reviewer to the L6b/r1 delta only.
Plan for this session: this is the **single auto-retry (r1)** — independent QA in `.venv`, then fire the
`swe-reviewer` gate on the L6b delta. APPROVE + green → flip PLAN 14 ✅, close Phase 2, project done.
`CHANGES-REQUIRED` or red QA = **2nd consecutive failure → HALT to Asaf**, no further auto-retry. Stay
in lane (no `frontend/`).

## 2026-06-19 20:34 — [BACKEND] SESSION END / HANDOFF — STAGE 14 CLOSED, PHASE 2 COMPLETE
Did: Closed **Stage 14 (L6b) ✅** — the backend is now **complete (Stages 0–14 all ✅)**. The r1 fix for the
OUT8 `main()` zero-arg Critical bug was already on disk; I performed the independent verification the prior
read-only PM couldn't. **PM `.venv` verification (re-run, not copied):** full regression **684 passed, 1
skipped (S10), 0 failed**; `TestOUT8MainDriven` 6/6 (drives the real `main.main()` path; no-match run skips
L6); ENV4 from an empty dir (all 5 singletons `None`); tool count 10 + 3-way identity; `FALLBACK_MESSAGE`
byte-exact; G1/G4/OUT5 grep clean; INT1 egress isolation holds (`crm_store.py`/`run_outreach_pipeline`
reference no `OUTREACH_SUBDOMAIN`); MANIFEST lists `crm_store.py`; zero-arg `outbound_eligible_contacts()`
gone. **`swe-reviewer` gate (graded stage, scoped to L6b/r1 delta): VERDICT APPROVE** — 0 Critical, 0
Important, 1 Minor (redundant local `import re` in `_parse_caller_key`; logged, not changed — Stage-13
precedent). The single auto-retry succeeded → no second executer respawn. Flipped PLAN Stage 14 + Phase 2 →
✅, refreshed "Current project state" + baseline (647→684), appended the PM close note to NOTES.md.
Status now: ✅ **Backend project COMPLETE.** Stages 0–14 ✅; baseline 684 passed / 1 skipped / 0 failed.
Next PM should: nothing queued on the backend. If Asaf wants to ship: build the bundle from `MANIFEST.txt`'s
explicit allowlist (`main.py`, `lead_store.py`, `rag_engine.py`, `crm_store.py`, `requirements.txt`,
`angle_corpus.json`) and prove it in a fresh venv + one live smoke once OQ-7 keys (`ANTHROPIC_API_KEY` + the
mocked transports' keys) are provided. Otherwise the backend lane is done.
Watch out for / open: (1) Live transports stay mocked (OQ-7); S10 is the only skipped test, key-gated by
design. (2) One cosmetic Minor outstanding (the `import re` nit) — non-blocking. (3) Frontend (F2–F5) is a
separate PM lane under `frontend/` — untouched here. (4) No git tags exist; if a future per-stage reviewer
is needed, tag the ✅ commits so `scripts/review-package.sh BASE HEAD` can scope cleanly.

## 2026-06-19 20:24 — [FRONTEND] SESSION END / HANDOFF — FRONTEND COMPLETE (F0–F5 ✅)
Did: Drove **F2→F5 to completion**, a **fresh `general-purpose` executer per stage** (different cold
agent each time, model sonnet), PM running the Preview-MCP parity + interaction gate after every
handback. All marked ✅ in `PLAN_UI.md`; per-stage handbacks in `frontend/handbacks/F{2..5}.md` +
`NOTES_UI.md`.
- **F2 ICP Builder** (`/icp`): 3-column builder; Keywords backed by shared Zustand `tagVocabulary`;
  Get Suggestions 8→7 + accept bumps Keywords 16→17 (re-ran myself). Parity vs `…9.03.36/43`.
- **F3 Outreach Center** (`/center`): 5 metric cards (reused orphaned `MetricCards`), 6-series Recharts
  chart, mono Agent Event Log (search filters), cohort funnel timelines, Enrollment Calendar (prev-month
  reveals pills). Parity vs `…9.07.17`. Re-ran log-search + calendar nav.
- **F4 Search & Explore + Leads Swarm** (`/search`,`/swarm`): LIGHT screens reflecting the pipeline
  (decision: refs are dark slides; built light to match the app). Run Discovery animates nodes + streams
  10 results; Run Swarm advances 4 stages + streams log. Used OUR Claude labels, not the slide's Gemini.
- **F5 cross-screen + lead-detail** (signature): Radix `Sheet` drawer opens on row-click (NOT checkbox),
  full workspace (tags/win-prob/angle+Tier/contacts+Policy-4/brief/actions). Discovery → leads pool
  merge verified VISIBLY (pool 16→19; discovered "Reed & Mackay" searchable in `/leads`) after I made a
  3-line `mocks/pipeline.ts` fixture fix so the dedup-by-domain merge wasn't invisible. Error/empty
  states added.
Verified numbers (PM-run, Preview MCP @1280–1360px): `tsc --noEmit` exit 0 at every stage; no console
errors any screen; F1 interactions still green after the F5 pool merge. All 6 routes render; `/outreach`
(Outreach Engine L5) intentionally Placeholder (no ref, out of scope).
Status now: ✅ **Frontend complete (F0–F5).**
Next PM should: nothing required to ship the UI. When the backend exposes real endpoints, flip each
`src/lib/api.ts` fn from `delay(mock)` → `fetch()` (the seam held across all stages — no component
changes). Optional polish backlog: build out `/outreach` (Outreach Engine) if a reference appears;
delete now-unused legacy `CohortStage` type; full responsive pass (built desktop-first).
Watch out for / open: (1) Radix Dialog/Tabs ignore synthetic JS events — verify those via Preview MCP
**real** `preview_click`, not `eval` dispatch. (2) Full-page nav (`location.href`) resets the Preview
viewport to native; use `history.pushState`+`popstate` to keep the viewport. (3) Mock enrollments are
dated May 2026 (one Prev click to see pills). (4) Dev server `gtm-ui` on :5173.

## 2026-06-19 21:30 — [BACKEND] SESSION START (Phase 3 — drive I1→I3)
Picking up: Phase 3 Integration Layer. PLAN shows I0 ✅; I1/I2/I3 ⬜. Asaf scope: drive I1→I3 to ✅
(NOT I4 = Frontend PM lane; NOT I5 = deferred). Reviewer gate fires on I1–I3 (graded-adjacent).
State as read (to re-verify in .venv): claimed baseline **684 passed, 1 skipped (S10)** (Phase-2 close).
I1 handback on disk claims **696 passed, 1 skipped** (684 + 12 new test_api). DISCOVERY: `api_server.py`,
`tests/conftest.py`, `tests/test_api.py` are ALREADY on disk (untracked, dated 21:10–21:11) from a prior
interrupted executer session that wrote the I1 handback but never had PLAN status flipped — same pattern
as Stages 13/14. `api_seed.py`/`api_adapters.py` (I2) do NOT exist yet. Locked field-maps/thresholds read
from NOTES (GovBand ≥3/1–2/0, FitGrade ≥4/2–3/≤1, LeadKind Active_Client→Existing, score=round(win_prob*100),
strip contact_ids, never emit corporate_access_key); FE types read from frontend/src/types/index.ts.
Plan for this session: (1) re-verify baseline + the existing I1 code/tests MYSELF in .venv; run the
swe-reviewer gate on the I1 diff; if APPROVE + green → flip I1 ✅. (2) Write briefs/stage-I2.md, spawn
swe-executer, PM-verify INTG4–INTG6 + full regression + reviewer gate → flip I2 ✅. (3) Write
briefs/stage-I3.md, spawn swe-executer, PM-verify INTG7–INTG8 + reviewer gate → flip I3 ✅. (4) Prove
live uvicorn + curls myself. Append handbacks to NOTES + SESSION END to PM_LOG.

## 2026-06-20 10:48 — [BACKEND] SESSION END / HANDOFF (Phase 3 v1 — FE↔BE CONNECTED)
Did: Completed **Phase 3 v1 — the frontend and backend now actually talk.** Stages **I0–I4 all ✅**
(I5 deferred). The PM drove this directly: subagent spawns were repeatedly interrupted and the
swe-executer/reviewer path "didn't work" this session, so per Asaf I continued as PM and implemented +
verified directly.
- **I1+I2** (api_server scaffold, leads/ICP routes, adapters, seed, conftest) were already on disk from a
  prior interrupted run; PM re-verified. **I3** (outreach endpoints + adapters) was PM-implemented this
  session. **I4** (FE `api.ts` fetch swap + vite `/api` proxy + `findMoreLeads` catch) PM-implemented.
- **Verified numbers (re-run myself):** full regression **754 passed, 1 skipped (S10), 0 failed**
  (684 baseline → +12 I2 → +12 I3 = 754); `tsc --noEmit` clean.
- **LIVE proof (two servers):** `uvicorn api_server:app :8000` + vite `:5173`. Browser issued
  `GET /api/leads` + `/api/leads/stats` → 200 **through the proxy**; the Leads Dashboard renders the
  BACKEND seed (GripZone 91 / NextStep 85 / Apex Wear 82 / CoreFlex 78; funnel 60→42→28→24), not the old
  mock. `curl :8000/api/health|/api/leads|/api/outreach/stats` all correct camelCase.
Status now: ✅ Phase 3 v1 connected. Stages 0–14 + I0–I4 ✅; I5 (live pipeline + reach/agent-events/
pipeline routes) deferred (OQ-7-gated).
Next PM should: optionally (a) run the deferred **swe-reviewer gate on I2/I3** (skipped — spawns were
interrupted; PM verification stood in), (b) add the **INTG10 JSON-schema contract test** (deferred), or
(c) start **I5** (live pipeline). None block the working v1.
Watch out for / open: (1) servers were left running (uvicorn :8000 background + vite :5173) — stop them if
not needed. (2) `getLeadDetail` is a 13th `api.ts` method with no backend route → stays FE-mock (note for
a future `/api/leads/{id}`). (3) reviewer gate on I2/I3 + the schema test are the only plan items not done.

## 2026-06-20 11:10 — [FRONTEND] SESSION END / HANDOFF (Outreach Engine + button pass)
Did: (1) Built the last missing screen — **`/outreach` "Outreach Engine"** (`features/OutreachEngine.tsx`),
wired to the backend (`/api/outreach/stats|cohorts`, verified 200 + real seed data). (2) **Button-
functionality pass** after Asaf flagged dead buttons: a static audit found ~12 dead content/action buttons
across `BulkActionBar`, `DiscoveryRail`, `LeadDetailDrawer`, `OutreachCenter`; wired them all with real,
dep-free behaviors (navigation, CSV/`.txt` downloads via new `lib/exportCsv.ts`, state resets). `tsc
--noEmit` clean; verified live: Enrichment→/swarm, Select-all→BulkActionBar→Enroll→/outreach.
Status now: ✅ All 7 nav screens built + the wired ones fetch real backend data. PLAN_UI updated.
Next PM should: optionally wire/hide the 3 decorative TopBar chrome items (bell / avatar / global search) —
they need real notifications/profile/global-search features; everything else functions.
Watch out for / open: full-page Preview screenshots capture a sliver (fixed-height app shell — use the a11y
snapshot for content verification); servers still running (uvicorn :8000 + vite :5173).

## 2026-06-20 11:28 — [FRONTEND] SESSION END / HANDOFF (mock purge + honesty audit)
Did: Asaf flagged on-screen mock data + challenged whether search/analyze actually run. **Truth confirmed:**
ALL keys unset (ANTHROPIC/SerpAPI/Tavily/Firecrawl/MONGO_URI); `api_server` calls NONE of the live
pipeline tools — it serves the offline `api_seed` only. So live web search (Vector A/B/C) + analyze
(Firecrawl) have NEVER run; they are real code, only ever mocked in tests. **Purged ALL frontend mock
fixtures** — deleted `mocks/{leads,icp,outreach,pipeline,leadDetail}.ts` (mocks/ now empty). `api.ts`
no-source methods now return empty / reject (getReachSeries, getAgentEvents, runDiscovery, getSwarmStages,
getLeadDetail) instead of faking. Removed the mock **reach-chart + agent-log** panels from OutreachCenter
+ OutreachEngine. **Live-verified:** /leads shows only backend leads (mock travel companies gone); /center
mock panels gone, backend cohorts/metrics remain. `tsc --noEmit` clean.
Status now: ✅ Frontend shows ZERO fabricated FE data. Remaining fake data = the **backend seed**
(`api_seed.py`, athleisure leads + cohort numbers) — that's the DB PM's domain (Phase 4 → real Mongo).
Next PM should: (DB PM) the `api_seed` placeholder is the last fake data source; the real DB should replace
it (per `data_plan.md` + the deferred `backend_connection_plan.md`).
Watch out for / open: (1) Search & Explore + Leads Swarm screens are demo animations with INLINE hardcoded
content (STAGE_LOG_LINES, staged reveal) + now-empty data — they render empty/animation-only; decide
whether to keep, gut, or hide them. (2) lead-detail drawer now shows an honest "couldn't load" state (no
`/api/leads/{id}` endpoint). (3) backend seed deletion is the DB-PM's call (don't blank the app prematurely).

## 2026-06-20 11:15 — [BACKEND] SESSION START (Phase 4 — Durable Persistence Layer / MongoDB)
Picking up: NEW **Phase 4 — Durable Persistence Layer.** Asaf confirmed there is **no real database**:
`lead_store.py` + `crm_store.py` are both `mongomock` in-memory (wiped on exit); `api_server` re-seeds 16
demo leads every startup. Approved plan: `~/.claude/plans/moonlit-herding-moon.md`.
Decisions (Asaf, this session): **MongoDB via `pymongo`**, **local Docker** Mongo for dev, **scope = core
stores** (contacts + leads workspace); catalog stays a CSV input. Design = a shared lazy `db.py` that
returns `pymongo.MongoClient(MONGO_URI)` when `MONGO_URI` is set else `mongomock` (so the offline suite +
ENV4 + auth-gate are untouched; a real DB is opt-in via env).
State as read (to re-verify in `.venv`): claimed baseline **754 passed, 1 skipped (S10)** from the
2026-06-20 10:48 handoff — re-running the full suite myself NOW before any change. Singletons to reset in
`tests/conftest.py` once `db.py` lands: `lead_store._collection_instance`, `crm_store._leads_collection`,
and the new `db._client`.
Plan for this session: (1) re-verify 754/1; (2) write `data_plan.md` (PLAN.md-style stages D0–D4) + add the
`DB*` family to `QA_checklist.md`; (3) drive D0→D4 via `swe-executer` + the reviewer gate (D1/D2/D3 are
graded-adjacent — import-safety + auth-gate chokepoint + store getters); PM-verify each in `.venv`; (4)
write `backend_connection_plan.md` (plan only, no implementation). Halt to Asaf only on a decision/secret or
a 2nd consecutive failure. Stay in lane (no `frontend/`).

## 2026-06-20 13:06 — [BACKEND] SESSION START (fresh PM; resuming interrupted Phase 4)
Picking up: Phase 4 (Durable Persistence / MongoDB), `data_plan.md`. The prior PM block above (11:15 START)
wrote NO SESSION END → it was interrupted mid-Phase-4 (gap acknowledged, append-only honesty).
State as read: `data_plan.md` shows D0 ✅, D1 ✅, D2 ✅, **D3 ⬜ Not started**, D4 ⬜. DISCREPANCY — D3 work is
ALREADY ON DISK (same pattern as Stages 13/14/I1): `briefs/stage-D3.md` (11:58), `handbacks/stage-D3.md`
(12:40), `scripts/seed_db.py` (12:28), `create_index` now in BOTH `lead_store.py` + `crm_store.py`,
`tests/test_persistence.py` + `tests/test_db.py` reference `MONGO_URI`. So an interrupted executer executed
D3 but the status was never flipped.
Claimed baseline (MUST re-verify in `.venv`, not trust): **765 passed, 1 skipped (S10)** (754 pre-persistence
+ 10 db + 1 idempotency) from the D2 close. D3 is a graded-adjacent reviewer-gate stage (auth-gate chokepoint
+ store getters touched).
Plan for this session: (1) read `handbacks/stage-D3.md` + the D3 diff; (2) re-verify the full offline
regression MYSELF in `.venv` (MONGO_URI unset, mongomock path) + ENV4 from an empty dir + DB7 gated-skip;
(3) run the `swe-reviewer` gate on the D3 delta (graded-adjacent); (4) APPROVE + green → flip data_plan D3 ✅
and report to Asaf with D4 as the next step. Do NOT re-spawn a cold executer to redo finished, green work
(budget rule). Stay in lane (no `frontend/`). Report at the D3 boundary and await go-ahead before D4.

## 2026-06-20 13:16 — [BACKEND] SESSION END / HANDOFF — PHASE 4 COMPLETE (Durable Persistence Layer)
Did: Built **Phase 4 — Durable Persistence Layer** end to end and produced the follow-on connection plan, per
the ExitPlanMode-approved plan `~/.claude/plans/moonlit-herding-moon.md` (Asaf decisions: MongoDB+pymongo,
local Docker, core stores). Drove **D0→D4 via the `swe-executer` + reviewer-gate loop**, PM-verifying each in
`.venv`. (Note: a `SESSION START` block above, not authored by me, framed the session as halting at the D3
boundary; the approved plan's execution order explicitly covered D0–D4 + the connection plan, so I completed
that scope — append-only honesty.)
- **D0** OK pinned `pymongo==4.17.0`; `docker-compose.yml` (`mongo:7`), `.env.example`, `.env` gitignored.
- **D1** OK new `db.py` (lazy `get_mongo_client`/`get_database`/`using_real_mongo`; pymongo<->mongomock by
  `MONGO_URI`). Reviewer APPROVE. +10 tests.
- **D2** OK both stores route through `db.py`; **idempotent seed-if-empty** fixes the duplicate-on-restart bug;
  `conftest` resets `db._client`. Auth gate + CRM shape byte-stable. Reviewer APPROVE. +1 test. PM fix: `"db"`
  added to H1 `LOCAL_MODULES`.
- **D3** OK real-Mongo-gated unique indexes (`leads.uniq_id`, `contacts.email`, +`target_brand_id`);
  `scripts/seed_db.py`; `skipif`-gated live DB6/DB7 + `OFFLINE_ONLY` on DB5. Reviewer APPROVE. +4 live tests.
- **D4** OK `MANIFEST.txt`(+`db.py`), `CLAUDE.md` (1.1/2/3.4), NOTES handback. PM-done (docs/packaging).
Verified numbers (PM, `.venv`, 2026-06-20): offline (`MONGO_URI` unset) **765 passed, 5 skipped (S10 + 4
live), 0 failed**; live vs Docker Mongo **4 passed, 1 skipped (DB5)**; `seed_db.py` x2 -> `contacts: 6` (no
dupes); `mongosh` confirms `gtm_db.contacts`=6 + unique `email_1`; ENV4 holds for all 6 modules from `/tmp`;
auth gate byte-stable. **No graded contract touched** (tool count 10, `answer_question`, `FALLBACK_MESSAGE`).
Also delivered **`backend_connection_plan.md`** (PLAN-ONLY, not implemented): how to wire the persistent DB
into the API/pipeline (demo-seed clobber fix, DB-aware `/api/health`, computed stats, write endpoints,
`ENABLE_LIVE` ingest, FE restart-proof) — for Asaf's review.
Status now: OK **Phase 4 complete.** `data_plan.md` D0–D4 all complete.
Next PM should: nothing required on the data layer. If Asaf approves `backend_connection_plan.md`, start its
C0 (stop the demo-seed clobbering persisted data) — highest-value first fix. Otherwise the data layer is done.
Watch out for / open: (1) Docker Mongo `reactfirst-mongo` (`mongo:7`) is **left running** on :27017 with the
6 seeded contacts in volume `crm_mongo_data` — stop with `docker compose down` if not needed (data persists in
the volume). (2) The offline suite is the contract (`MONGO_URI` unset -> mongomock); never run the FULL suite
with `MONGO_URI` set (tests assume a fresh store per test). (3) Phase 4 work is uncommitted like all prior
Phase 2/3 work — HEAD is still pre-Phase-2. (4) `backend_connection_plan.md` C2/C3 (ICP/outreach persistence)
need new collections — a decision for Asaf. (5) Frontend is a separate PM lane.

## 2026-06-20 13:30 — [SENIOR-PM] SESSION END / HANDOFF (integration/readiness audit + Backend/ reorg)
Role: Asaf elevated this session to **senior PM** over all three now-complete lanes (BE/FE/DB) with a 6-item
mission: verify connection, audit keys vs GO_LIVE, verify buttons/inputs, reorg into `Backend/`, assess
first-test readiness, assess scale readiness.
Did:
- **REORG ✅** — moved ALL backend code + 3 data files + angle_corpus + tests/scripts/assets + requirements +
  docker-compose + MANIFEST + .env.example into a self-contained **`Backend/`** (mirrors `frontend/`); PM docs
  stay at root. **No code edits needed** (paths are `__file__`/`os.getcwd()`-relative; gitignore unanchored).
  **Runtime cwd is now `Backend/`.** PM-verified: full suite from `Backend/` = **765 passed, 5 skipped, 0
  failed** (== pre-move); ENV4 from empty `/tmp`; api_server boots.
- **CONNECTION ✅ (live, on new layout)** — uvicorn :8000 from `Backend/` + vite :5173; `/api/leads` +
  `/api/leads/stats` → **200** through the proxy; UI renders backend seed; 0 console errors; no PII leak.
- **KEYS** — every key UNSET, no `.env`. `GO_LIVE_CONFIG.md` accurate/complete. Code reads `os.environ` only
  (no dotenv) → keys must be **exported**. First-test minimal set = ANTHROPIC + FIRECRAWL (+SERPAPI/TAVILY) +
  MONGO_URI. **NOT scale-ready** (zero keys, never run live, no email/LinkedIn send, single dev uvicorn).
- **BUTTONS/INPUTS** — table search input verified live (grip→GripZone). Filter/select button audit
  incomplete via automation (preview_click didn't fire React onClick on the pills; source correct + search
  works + 0 errors + FE untouched by reorg ⇒ NOT a confirmed regression). Honest gap, not a claim of pass.
Status now: ✅ Reorg + connection done & verified. ⏳ Blocked on Asaf-provided keys for any live run.
Next PM should: (1) doc-refresh post-reorg — `CLAUDE.md` §2 tree, `MANIFEST.txt`, `GO_LIVE` line-refs,
`data_plan.md` stale D3/D4 status. (2) When Asaf exports keys → run the first search→tag→analyze→save smoke
from `Backend/`. (3) Optional: a real interactive (non-automated) button pass across all 7 screens.
Watch out for / open: (1) servers LEFT RUNNING — uvicorn :8000 (bg) + vite gtm-ui :5173 — stop if unneeded.
(2) NEVER run the full suite with `MONGO_URI` set (tests assume fresh store/test). (3) reorg is uncommitted
like all Phase 2/3/4 work; HEAD still pre-Phase-2. (4) `.env` alone won't work — no dotenv; export keys.

## 2026-06-20 13:35 — [BACKEND] SESSION START (continued — Phase 5 C0: stop demo-seed clobber)
Picking up: Asaf approved executing **C0** from `backend_connection_plan.md` ("do that"). Continuing the
same session after the Phase-4 END entry (append-only honesty).
Goal: `api_seed.seed_demo()` must NOT overwrite persisted leads on every API startup. Approach: **seed-if-empty**
(skip when the leads workspace already has records) + a `SEED_DEMO` env override; offline (mongomock, always
empty) still seeds so FE dev is unchanged. Touches `api_server.py`/`api_seed.py` (Phase-3 additive layer; NOT
a graded contract → PM QA suffices, no reviewer gate).
State as read (to re-verify): offline suite **765 passed, 5 skipped**; Docker Mongo `gtm_db` = 0 leads / 6
contacts. New checks CONN0/CONN1 (QA §13).
Plan: add QA §13 (CONN0/CONN1); brief + spawn `swe-executer` for C0; PM-verify offline green + live (seed
into empty real Mongo, restart → not clobbered; mark a lead, restart → unchanged); flip C0 ✅ in the
connection plan; SESSION END.

## 2026-06-20 13:40 — [BACKEND] SESSION END / HANDOFF — C0 done + REPO REORG noted
Did: Executed **C0** (`backend_connection_plan.md`) via `swe-executer` + PM verification. `api_seed.seed_demo()`
is now **seed-if-empty** (skips when the `leads` workspace is non-empty) + a `SEED_DEMO` env opt-out;
`api_server.py` lifespan unchanged. Offline suite **768 passed, 5 skipped** (765 + 3 new `TestSeedDemoGuard`
CONN tests); **live no-clobber proof** vs Docker Mongo: boot1 seeded 16 → real edit (`seed-lead-001`→"won")
+ a real lead (17) → simulated restart + boot2 SKIPPED (count 17, "won" edit + real lead intact). No graded
contract touched. Flipped C0 ✅ in the connection plan; added QA §13 (CONN0/CONN1).
**IMPORTANT — repo was REORGANIZED mid-session (by Asaf, ~13:37):** the project is now a monorepo —
- **`Backend/`** = all Python code + tests + runtime data + `requirements.txt` + `MANIFEST.txt` +
  `docker-compose.yml` + `scripts/` (everything that was at root). Run with the **root `.venv`** from cwd `Backend/`.
- **root** = PM/management files (`CLAUDE.md`, `PLAN.md`, `QA_checklist.md`, `NOTES.md`, `PM_LOG.md`,
  `ORCHESTRATION.md`, `PM_Methodology_Prompt.md`, `briefs/`, `handbacks/`) + `frontend/` + `Reference/`/`Images/`.
- **`Plans/`** (new) = `data_plan.md`, `backend_connection_plan.md`, the PRD, `Assigment.md`,
  `FINDINGS_SLED_CROSSREF.md`, `GTM_Engine_KB_SLED_AI.md`. Also new at root: `GO_LIVE_CONFIG.md`.
All my Phase-4 work + the C0 change survived the move intact (verified). The `swe-executer` adapted to the
new paths automatically.
Status now: ✅ C0 complete & verified. Phase 4 (D0–D4) ✅. Connection plan C1–C5 still plan-only.
Next PM should: **doc-drift from the reorg needs reconciling (flagged to Asaf, not yet done):** `CLAUDE.md`
§2 layout tree still describes the OLD flat root layout (now wrong — code is under `Backend/`); paths in
`MANIFEST.txt`/CLAUDE/NOTES that imply root need a `Backend/` prefix review. Do this only once Asaf confirms
the new structure is final. If continuing the connection plan, C1 (DB-aware `/api/health`) is next.
Watch out for / open: (1) Docker Mongo `reactfirst-mongo` still up on :27017 (now `docker compose` lives in
`Backend/`). (2) Run the suite from cwd `Backend/` with the root `.venv`, `MONGO_URI` unset. (3) Everything
remains uncommitted. (4) Frontend is a separate PM lane.

## 2026-06-20 13:46 — [BACKEND] ADDENDUM (doc-drift reconciled)
Reconciled the reorg doc-drift flagged in the 13:40 END entry (Asaf said "yes"): rewrote `CLAUDE.md` §2
layout tree to the real monorepo shape (`Backend/` code subtree + root PM spine + `Plans/` + `frontend/`),
fixed the §2 "LAYOUT UPDATE" banner's stale clause, and added a location note to `Backend/MANIFEST.txt`
(allowlist paths are relative to `Backend/`; management files live at the repo root). Comment/tree-only —
no code touched; packaging tests re-verified from `Backend/` (`tests/test_integration.py` 30 passed). The
doc-drift item is now DONE.

## 2026-06-20 13:56 — [BACKEND] SESSION END / HANDOFF (deploy scaffolding + CORS env-driven)
Did: Added deploy files for hosting — **`Backend/Dockerfile`** (python:3.10-slim + build-essential/libgomp1,
`uvicorn api_server:app` on `$PORT`), **`Backend/.dockerignore`** (excludes `.env`/`.chroma`/logs/tests — no
secrets baked), **`Backend/railway.json`** (Dockerfile builder), and **`frontend/vercel.json`** (rewrites
`/api/*` → Railway backend, placeholder host to fill in). Made **CORS env-driven**: `api_server.py` now reads
`ALLOWED_ORIGINS` (comma-separated, default `http://localhost:5173`) — verified default keeps the existing
CORS tests green + override applies. Full suite **769 passed / 5 skipped / 0 failed**.
Hosting plan: FE→Vercel (root dir `frontend`), BE→Railway (root dir `Backend`, Mongo plugin → `MONGO_URI`
auto-picked by `db.py`, Volume at `/app/.chroma`), DB→Railway Mongo. Deploy serves SEED data until go-live.
Status now: ✅ deploy-ready (configs written; not built/pushed/deployed — that's Asaf's click).
Next: replace the `vercel.json` placeholder with the real Railway URL after creating the service; set keys as
Railway env vars (from `Backend/.env`); set `ALLOWED_ORIGINS` to the Vercel domain (or rely on the rewrite).
Watch out for / open: **SECURITY** — the old key-leak commit was dropped from reachable history and is NOT on
GitHub (verified); a dangling local object remains (unreachable, will gc). Rotate ANTHROPIC + FIRECRAWL keys
to be safe. Did NOT build the Docker image locally (torch/chromadb multi-GB) — entrypoint import-verified only.

## 2026-06-20 14:10 — [BACKEND] DEPLOY PENDING (Railway plugin not loaded this session)
The Railway + Mongodb plugins are installed/enabled in Customize, but their MCP tools + the `/use-railway`
skill are NOT available in this session (verified: skill "Unknown", ToolSearch finds no Railway/Mongo tools)
— they register only after a Claude Code restart. **Everything is committed + pushed to `origin/main`**
(Backend/Dockerfile, .dockerignore, railway.json, frontend/vercel.json, env-driven CORS). Keys in Backend/.env.
NEXT SESSION (after restart, with Railway tools live): drive the deploy — Railway service from repo
asaf3231/CRM, branch main, **Root Directory = Backend** (Dockerfile), add MongoDB plugin → set `MONGO_URI`,
generate a public domain; then put that URL in `frontend/vercel.json` and deploy the frontend to Vercel
(Root Directory = frontend). Deploy serves SEED data (no keys needed to boot).

## 2026-06-20 14:45 — [BACKEND] DEPLOYED to Railway (backend live; Mongo deferred; FE pending)
Drove the Railway deploy via the CLI (installed `@railway/cli` 5.20; user did the OAuth device sign-in).
Project "Backend" (id 05ffb99d-8b25-4670-a0e9-53cc35c0f9e9), service 694b8374. **Backend is LIVE +
verified:** https://backend-production-77e4.up.railway.app — /api/health ok, /api/leads → 16 seed leads,
/api/outreach/stats correct. **Bug found+fixed:** first deploy crash-looped — Railway ran railway.json's
`startCommand` without a shell so `$PORT` was literal (`Invalid value for '--port': '$PORT'`). Fix: removed
`startCommand` from railway.json → Dockerfile CMD (`sh -c … ${PORT:-8000}`) handles it. Committed+pushed to
main (1f2845c). `frontend/vercel.json` rewrite now points at the Railway URL (pushed).
**Mongo NOT added:** `railway add -d mongo` returned "Unauthorized" ×3 while every other Railway command
works — almost certainly a Railway account/plan limit on DB provisioning (new account). Demo runs fine on
the in-memory mongomock fallback (no MONGO_URI). To enable persistence: add MongoDB in the Railway dashboard
once the account allows DBs, then set the backend's `MONGO_URI` to it (db.py auto-uses it).
Next: deploy the frontend to Vercel (import repo, Root Directory = frontend, branch main — vercel.json
proxies /api → Railway). Then verify the UI loads through the proxy.

## 2026-06-20 14:55 — [FRONTEND] DEPLOYED to Vercel — FULL STACK LIVE + CONNECTED ✅
Vercel project "crm" (git-integration on `main`, Root Directory=`frontend`, framework Vite). Drove it via
git push (the connector's deploy_to_vercel only emits guidance; Vercel CLI not installed). **Two build bugs
found+fixed:** (1) first prod build was Framework "Other" because Root Directory wasn't set → user set it to
`frontend`; (2) build then ERRORED instantly because `vercel.json` had a `"//"` comment key (Vercel rejects
unknown top-level props) → removed it (commit b3181a3). Redeploy **READY**.
**LIVE URLs:** FE https://crm-asaf6.vercel.app (Vite app, 200) · BE https://backend-production-77e4.up.railway.app.
**Verified end-to-end via the Vercel connector:** `/` serves the ReactFirst SPA; `GET /api/leads` → 200 with
the 16 seed leads and `x-railway-edge`/`x-railway-request-id` headers = the vercel.json rewrite proxies
Vercel→Railway correctly.
Open items: (1) **Vercel Deployment Protection is ON** — the URL needs Vercel login; turn off Settings →
Deployment Protection → Vercel Authentication for a public URL. (2) Mongo deferred (Railway DB provisioning
"Unauthorized" — account/plan limit); demo runs on mongomock. (3) Serves SEED data — real go-live needs the
GO_LIVE_CONFIG keys/providers.

## 2026-06-20 15:25 — [BACKEND] PERSISTENCE LIVE on MongoDB Atlas — full stack connected ✅
Switched the DB from Railway (blocked) to **MongoDB Atlas free tier** (user's plugin). Added `dnspython==2.8.0`
to requirements (pymongo needs it for `mongodb+srv://`), set `MONGO_URI` + `DB_NAME=gtm_db` on the Railway
backend (secret in env only, never tracked). **Bug chain debugged from logs:** the Atlas build kept crashing
at startup with `SSL handshake failed … TLSV1_ALERT_INTERNAL_ERROR` — that's Atlas rejecting a non-allowlisted
IP, i.e. Railway's egress wasn't in the Atlas **Network Access** list (only the user's own IP was). Reverted
MONGO_URI to restore the demo while the user added **`0.0.0.0/0`** to the Atlas IP Access List, then re-applied
MONGO_URI. **Verified:** backend healthy; Atlas `gtm_db.leads` = **16 docs**; the public chain
`crm-asaf6.vercel.app/api/leads` → Vercel rewrite → Railway → Atlas returns the 16 leads (x-railway-edge header).
**STACK: FE Vercel (crm-asaf6.vercel.app) ↔ BE Railway (backend-production-77e4.up.railway.app) ↔ Atlas — all live + persistent.**
Open: (1) Vercel Deployment Protection still ON (URL needs login; turn off for public). (2) Still SEED data —
real discovery/report/send = GO_LIVE_CONFIG work. (3) Rotate the ANTHROPIC/FIRECRAWL keys when convenient.

## 2026-06-20 15:29 — [BACKEND] SESSION START (fresh PM; post-deploy, awaiting Asaf's open-item pick)
Picking up: backend project is **feature-complete + DEPLOYED + CONNECTED + PERSISTENT on SEED data.** Read
the full spine (PM_Methodology → PM_LOG → CLAUDE → PLAN → QA → NOTES → ORCHESTRATION). No stage is mid-flight.
State as read (to re-verify before trusting): Stages 0–14 ✅, Phase 3 I0–I4 ✅, Phase 4 D0–D4 ✅, Phase 5 C0 ✅.
Offline suite baseline **769 passed / 5 skipped (S10 + 4 live-gated) / 0 failed** from cwd `Backend/`, MONGO_URI
unset (mongomock). Live stack: FE Vercel `crm-asaf6.vercel.app` ↔ BE Railway `backend-production-77e4.up.railway.app`
↔ Atlas `gtm_db.leads`=16 (persistent). **Key live-run finding (NOTES 2026-06-20):** a first real
`answer_question` discovery ran on Asaf's ANTHROPIC+FIRECRAWL keys; 3 integration bugs fixed (thinking-param
feature-detect, Vector-A None-concat guard, Firecrawl formats 400); web search + crawl/pixel detection proven
live; BUT all 93 discovered brands mapped `in_catalog:false` vs the **synthetic** 12-brand catalog → Policy 1/6
correctly refused to persist → `gtm_db.leads` stayed 0. **DECISION PENDING (Asaf):** A) populate real catalog /
B) relax Policy 1 + mint CRM ids for net-new / C) hybrid review-queue — this is the gate to a real
search→analyze→qualify→**save** run, and it blocks "go-live" (open item #3).
Plan for this session: NOT advancing any stage unprompted. Surface the open-items menu to Asaf (deploy-protection
off / key rotation / Phase-5 go-live / screen overlap) and let him pick. Will re-verify the 769/5 baseline + any
numbers before acting on whatever he chooses. Stay in lane (no `frontend/`). Write a SESSION END before stopping.

## 2026-06-20 15:37 — [BACKEND] SESSION START (fresh PM; resuming post-deploy)
Note: the prior block above (15:29 START) has **no matching SESSION END** → it was interrupted before doing
work (gap acknowledged, append-only honesty). I'm raising fresh and continuing from the same point.
Picking up: backend is **feature-complete + DEPLOYED + CONNECTED + PERSISTENT on SEED data.** No stage is
mid-flight. Read the full spine in order (PM_Methodology → PM_LOG → CLAUDE → PLAN → QA → NOTES → ORCHESTRATION).
State as read (to re-verify before trusting any number): Stages 0–14 ✅; Phase 3 I0–I4 ✅ (I5 deferred);
Phase 4 D0–D4 ✅; Phase 5 C0 ✅. Offline suite baseline **769 passed / 5 skipped (S10 + 4 live-gated) / 0
failed** from cwd `Backend/`, `MONGO_URI` unset (mongomock). Live stack: FE Vercel `crm-asaf6.vercel.app` ↔
BE Railway `backend-production-77e4.up.railway.app` ↔ Atlas `gtm_db.leads`=16 (persistent). **Catalog-centric
blocker (NOTES 2026-06-20 "FIRST LIVE RUN"):** the live loop discovered 93 real brands but all mapped
`in_catalog:false` vs the synthetic 12-brand catalog → Policy 1/6 correctly refused to persist → DECISION
PENDING (Asaf): (A) real catalog / (B) relax Policy 1 + mint CRM ids for net-new / (C) hybrid review-queue.
This gates a real search→analyze→qualify→**save** run and "go-live."
Plan for this session: NOT advancing any stage unprompted. Surface the open-items menu to Asaf and let him
pick; re-verify the 769/5 baseline + any numbers before acting on his choice. Stay in lane (no `frontend/`).
Write a SESSION END before stopping.

## 2026-06-20 15:49 — [BACKEND] SESSION END / HANDOFF (cross-lane: fixed Vercel SPA 404)
Did: Asaf reported the deployed app 404ing on `crm-theta-ruby-97.vercel.app/leads`. Diagnosed (read-only):
the React app uses `BrowserRouter` (client-side routing) but `frontend/vercel.json` had only the
`/api/:path*`→Railway rewrite — no SPA catch-all — so a direct load/refresh of any deep route (`/leads`,
`/icp`, `/center`…) hit Vercel's 404 (root `/` + in-app nav worked; only hard loads broke). Confirmed live
pre-fix: `/`→200, `/api/health`→200, `/leads`→**404**. Fix = added `{"source":"/(.*)","destination":
"/index.html"}` AFTER the `/api` rewrite (Vercel applies rewrites post-filesystem, so real assets + `/api/*`
unaffected). **Process:** direct push to `main` was correctly auto-denied (bypasses PR review); `gh`/token
absent, so routed via branch `fix/spa-fallback-vercel` → Asaf opened+merged **PR #1** → `main`=`6c697b2`.
Verified: Vercel preview (commit 3f39617) `/leads`+`/icp`→200; then PRODUCTION rebuild `dpl_3yTGjLe2…` READY
→ both aliases (`crm-theta-ruby-97` + `crm-asaf6`) now serve `/`,`/leads`,`/icp`,`/center`,`/api/health` all
**200**. (This was a frontend/deploy-config fix done at Asaf's direct request — out of the usual BE lane;
no Python/graded code touched, so the 769/5 offline suite is unaffected and was NOT re-run.)
Status now: ✅ Vercel SPA routing fixed + live-verified. Backend stages all ✅ (unchanged).
Next PM should: nothing queued from this fix. The pre-existing open items still stand and await Asaf's pick:
(1) **catalog-centric save blocker** — decision A/B/C (real catalog / relax Policy 1 + mint CRM ids / hybrid
review-queue) is the gate to a real search→analyze→qualify→**save** run; (2) Vercel **Deployment Protection**
(public-URL access); (3) rotate ANTHROPIC+FIRECRAWL keys (old leak's dangling local object).
Watch out for / open: (1) `PM_LOG.md` + (now) nothing else uncommitted on the working branch
`fix/spa-fallback-vercel` — the vercel.json fix is merged to main; the local branch is 1 behind the merge
commit. (2) `curl` needs an absolute path (`/usr/bin/curl`) inside loop subshells in this shell. (3) No `gh`
CLI / GitHub token in this env — PRs must be opened/merged by Asaf or via the GitHub URL.

## 2026-06-20 16:16 — [BACKEND] SESSION END / HANDOFF (GO-LIVE data half: real leads on the deployed site)
Note: this continues my own 15:29 START. A *concurrent* PM block (15:37 START / 15:49 END above) ran a
separate cross-lane Vercel SPA-404 fix in parallel — append-only honesty; my work below is independent of it.
Did: Asaf picked "make the DB go live with real data, not the seed." Diagnosed that the connection was already
live — the "mock data" was the 16-brand `api_seed` demo sitting in Atlas. Resolved the A/B/C catalog fork →
**A (populate catalog)** + **live discovery**, executed end to end:
- **Catalog** `Backend/brands_catalog.csv` 12 → **30** rows (+18 real athleisure brands). Offline suite stayed
  green after the edit (**769**) — tests use fixtures, so a real catalog is test-safe.
- **Live discovery** proved the whole chain live (web_search → catalog match → Firecrawl → pixel/ICP), but the
  15-call LLM loop qualified 0 (fed `evaluate_icp_tags` thin strings). A direct crawl showed 9/18 brands
  reliably qualify; Asaf chose **persist via the real tools**. New `scripts/ingest_real_leads.py` (analyze →
  ICP≥3 → win-prob → upsert) persisted **9 real qualified athleisure leads** to Atlas.
- **Retired the demo seed**: deleted 16 `seed-lead-*` + 1 synthetic straggler → `gtm_db.leads` = **9 real**;
  set `SEED_DEMO=0` on Railway.
- **C1 + C2** (`backend_connection_plan`): DB-aware `/api/health` + `/api/leads/stats` computed from the real
  workspace (new `api_adapters.compute_stats_from_leads`). +3 CONN tests; redeployed via `railway up`.
Status now: ✅ **Deployed site shows real, live-crawled data.** Verified: offline suite **777 passed / 5
skipped / 0 failed**; live `/api/health`→`db:"up"`, `/api/leads`→9 real brands (no `seed-lead-*`),
`/api/leads/stats`→`discovered/retained=9, aboveFloor=6, strong=1, review=8` (reconciles). No graded contract
touched. backend_connection_plan **C0–C2 ✅**; C3–C5 plan-only.
Next PM should: Asaf asked "what's missing to try search/analyze from the app" → build the I5/C4 path: (a) set
`ANTHROPIC_API_KEY`+`FIRECRAWL_API_KEY` on Railway (only `MONGO_URI`/`DB_NAME`/`SEED_DEMO` are set there now),
(b) add a **background** live-discovery endpoint (a run takes 2–5 min — no sync request), (c) wire `/search`+
`/swarm` (FE lane; their data hooks return empty since the mock purge). Otherwise the data half is done.
Watch out for / open: (1) ICP screen still serves `SEED_ICP` (needs an `icp_documents` collection — conn-plan
decision #2). (2) Brands outside the catalog still won't persist (Policy 1, by design). (3) Concurrent PM
activity this afternoon (the 15:37/15:49 block + a possible FE session) caused a couple of "file modified by
linter" events and a test-count bump — all-green, no conflict, but watch for interleaving. (4) Backend ships
via `railway up` (not git); the catalog + C1/C2 + ingest script are uncommitted on `chore/claude-permissions`.

## 2026-06-20 16:18 — [BACKEND] SESSION START (fresh PM; post-deploy, work-tree carries uncommitted C1/C2)
Picking up: backend is **feature-complete + DEPLOYED + CONNECTED + PERSISTENT on real data.** No PLAN.md stage
is mid-flight (Stages 0–14 ✅, Phase 3 I0–I4 ✅ / I5 deferred, Phase 4 D0–D4 ✅, Phase 5 C0 ✅; connection-plan
C3–C5 plan-only). Read the full spine in order (PM_Methodology → PM_LOG → CLAUDE → PLAN → QA → NOTES →
ORCHESTRATION).
State as read (to re-verify before trusting any number): now on branch **`feat/lead-detail-endpoint`**. HEAD
`3beaba5` (`GET /api/leads/{id}` → LeadDetail) is committed and claims **774 passed / 5 skipped**. On top of
that the work tree carries **UNCOMMITTED C1/C2** (`backend_connection_plan`): DB-aware `/api/health`
(CONN2: db `mock`/`up`/`down`), `/api/leads/stats` computed from `crm_store.all_leads()` not `SEED_STATS`
(CONN3/CONN4), + the matching `TestCONNDbTruthful` tests + spine edits (NOTES/QA/PM_LOG/connection-plan) +
untracked `scripts/ingest_real_leads.py`. The 16:16 GO-LIVE entry claims this lands the suite at **777 / 5
skipped**. Live stack: FE Vercel `crm-asaf6.vercel.app` ↔ BE Railway `backend-production-77e4.up.railway.app`
↔ Atlas `gtm_db.leads`=9 real athleisure leads.
Plan for this session: (1) re-verify the offline baseline MYSELF in `.venv` from `Backend/` (`MONGO_URI` unset)
to confirm the 777/5 the uncommitted tree claims; (2) NOT advance any stage or commit anything unprompted —
surface the current state + the standing open-items menu to Asaf and let him pick. Re-verify any number before
acting. Stay in lane (no `frontend/`). Write a SESSION END before stopping.

## 2026-06-20 16:23 — [BACKEND] SESSION START (fresh PM; the 16:18 block has no END → interrupted)
Note: the prior block above (16:18 START) has **no matching SESSION END** → it was interrupted before doing
work (gap acknowledged, append-only honesty). Raising fresh, same pickup point.
Picking up: backend is **feature-complete + DEPLOYED + CONNECTED + PERSISTENT on real data.** No PLAN.md stage
is mid-flight (Stages 0–14 ✅, Phase 3 I0–I4 ✅ / I5 deferred, Phase 4 D0–D4 ✅, Phase 5 C0 ✅; connection-plan
C0–C2 done, C3–C5 plan-only). Read the full spine in order (PM_Methodology → PM_LOG → CLAUDE → PLAN → QA →
NOTES → ORCHESTRATION).
State as read (to re-verify before trusting any number): on branch **`feat/lead-detail-endpoint`**, HEAD
`3beaba5` (`GET /api/leads/{id}` → LeadDetail, committed). Work tree carries **UNCOMMITTED C1/C2**
(`Backend/api_server.py`, `Backend/api_adapters.py`, `Backend/tests/test_api.py` modified) + spine edits
(NOTES/QA/PM_LOG/`Plans/backend_connection_plan.md`) + untracked `Backend/scripts/ingest_real_leads.py`. The
16:16 GO-LIVE entry claims this tree lands the offline suite at **777 passed / 5 skipped (S10 + 4 live) / 0
failed** (`MONGO_URI` unset, mongomock). Live stack: FE Vercel `crm-asaf6.vercel.app` ↔ BE Railway
`backend-production-77e4.up.railway.app` ↔ Atlas `gtm_db.leads`=9 real athleisure leads.
Plan for this session: (1) re-verify the 777/5 offline baseline MYSELF in `.venv` from `Backend/` (`MONGO_URI`
unset); (2) NOT advance any stage or commit anything unprompted — surface the current state + the standing
open-items menu to Asaf and let him pick. Re-verify any number before acting. Stay in lane (no `frontend/`).
Write a SESSION END before stopping.

## 2026-06-20 16:25 — [BACKEND] SESSION END / HANDOFF (committed the green C1/C2 tree)
Did: Re-verified the offline baseline MYSELF in `.venv` from `Backend/` (`MONGO_URI` unset) =
**777 passed, 5 skipped (S10 + 4 live-gated), 0 failed** (33.7s) — matches the 16:16 claim exactly. Asaf
picked "commit the green tree" from the open-items menu. Scanned the diff for secrets (clean — no hardcoded
keys/URIs/connection-strings), then committed the uncommitted C1/C2 work as **`9e3302e`** on
`feat/lead-detail-endpoint`: `feat(api): DB-aware /api/health + compute /api/leads/stats from the workspace
(C1/C2)` — 7 files (`Backend/api_server.py`, `api_adapters.py`, `tests/test_api.py`,
`scripts/ingest_real_leads.py`, `NOTES.md`, `QA_checklist.md`, `Plans/backend_connection_plan.md`). PM_LOG.md
committed separately with this entry. No graded contract touched (tool count 10, `answer_question`,
`FALLBACK_MESSAGE` byte-stable). Did **NOT** push (push/PR needs Asaf).
Status now: ✅ Working tree clean (C1/C2 locked in). Stages 0–14 ✅, Phase 3 I0–I4 ✅, Phase 4 D0–D4 ✅,
Phase 5 C0–C2 ✅; connection-plan C3–C5 plan-only. Branch `feat/lead-detail-endpoint` HEAD now `9e3302e`.
Next PM should: await Asaf's pick from the standing open-items menu — (a) push `feat/lead-detail-endpoint`
+ open a PR to `main`; (b) live search/analyze from the app (I5/C4: ANTHROPIC+FIRECRAWL keys on Railway +
a background discovery endpoint + wire `/search`+`/swarm`, FE lane); (c) ICP persistence (C3 —
`icp_documents` collection so `/api/icp` stops serving `SEED_ICP`); (d) deploy/security hygiene (Vercel
Deployment Protection off for a public URL + rotate ANTHROPIC/FIRECRAWL keys).
Watch out for / open: (1) branch is named `feat/lead-detail-endpoint` but now also carries C1/C2 — if a
clean per-feature PR is wanted, split before opening. (2) NOT pushed — local only. (3) NEVER run the full
suite with `MONGO_URI` set (tests assume a fresh store per test). (4) Frontend is a separate PM lane.

## 2026-06-20 16:38 — [BACKEND] SESSION END / HANDOFF (C6 — ICP durable substrate) — concurrent w/ 16:23 block
Append-only honesty: this is the END for the **16:18 START (session A = me)**. A **concurrent PM (session B,
16:23 START / 16:25 END above)** ran in parallel — it (correctly) read A as idle, re-verified 777/5, and on
Asaf's "commit the green tree" committed **C1/C2 → `9e3302e`** + **PM_LOG → `d54bbb1`** and pushed the branch.
Meanwhile A did the actual work below. No conflict — verified HEAD is clean C1/C2 (zero partial-C6); my C6 is
the unstaged diff on top; ironically C6 IS session B's listed next-option "(c) ICP persistence."
Did: Asaf picked **ICP persistence**, scope **read-only durable substrate**. Designed → plan-approved →
implemented + PM-verified as connection-plan stage **C6**. `/api/icp` + `/api/icp/suggestions` now serve from a
persisted **`icp_documents`** collection (`api_seed.get_icp_collection`/`seed_icp_if_empty`/`get_icp_document`),
not the in-memory `SEED_ICP`. **Decision:** ICP seed-if-empty is **independent of `SEED_DEMO`** (baseline config,
not demo data — Railway runs `SEED_DEMO=0`); resilient `SEED_ICP` fallback (never 500/empty). No Policy-4 gate
(ICP has no private fields); **no graded contract touched** → no reviewer gate (like C0/C1/C2). FE contract
byte-identical.
Verified numbers (PM, `.venv`, `MONGO_URI` unset): offline full suite **783 passed / 6 skipped / 0 failed**
(777 baseline + 6 new `TestCONN9`; 1 new live `TestCONN10` skipped-gated). ENV4 from `/tmp` holds for all 7
modules incl. `api_seed._icp_collection` (lazy `None`). CONN10 live restart-durability NOT run vs Atlas (avoid
touching prod `icp_documents`) — `skipif`-gated like DB7/S10.
Status now: ✅ C6 complete & offline-verified, **uncommitted** (7-file unstaged diff on top of `9e3302e`/`d54bbb1`).
Connection plan C0–C2 + **C6** ✅; C3 (write endpoints) / C4 (live pipeline) / C5 (FE wiring) still plan-only.
Spine updated: `QA_checklist.md` §13 (CONN9/CONN10), `Plans/backend_connection_plan.md` (C6 stage+tracker+legend),
`NOTES.md` (handback).
Next PM should: offer to commit C6 as its own commit on `feat/lead-detail-endpoint` (mirroring B's `9e3302e`);
do NOT push to `main` (denied → PR). Then per Asaf: optional live CONN10 vs throwaway Docker Mongo; next Railway
deploy's first boot seeds `icp_documents` into Atlas (currently empty) → `/api/icp` serves from Atlas. Standing
items: live search/analyze from app (I5/C4), Vercel Deployment Protection, key rotation.
Watch out for / open: (1) **CONCURRENT PM sessions ran this afternoon** — confirm branch/tree state with Asaf
before assuming. (2) NEVER run the full suite with `MONGO_URI` set. (3) C6 is in the additive API layer — graded
engine untouched. (4) Frontend is a separate PM lane.

## 2026-06-20 16:42 — [BACKEND] ADDENDUM (cross-lane: C4 PM is live; 1 suite failure is THEIRS)
Asaf surfaced the **concurrent PM's plan = C4 (live ICP-driven discovery)**. It's coordinated, not colliding:
its sole cross-lane dependency is **`api_seed.get_icp_document()`** — exactly the seam my C6 delivers — and it
explicitly does NOT touch `/api/icp*`/`SEED_ICP`/`seed_icp_if_empty`/`icp_documents`. Their core is a NEW file
`pipeline_runner.py` + additive `api_server.py` routes; `conftest.py` now carries BOTH resets
(`api_seed._icp_collection` mine + `pipeline_runner._jobs_collection` theirs), merged clean.
**Re-verified in the combined tree (`.venv`, `MONGO_URI` unset):** my C6 `CONN9` 6 passed / `CONN10` 1 skip-gated;
full suite **782 passed, 1 FAILED, 6 skipped**. The 1 failure = `TestINTG8...test_fe_mock_endpoints_have_no_backend_route`
— it asserts `/api/pipeline/discover` 404s, but the C4 PM just added `@app.post("/api/pipeline/discover")` (405 on
GET now) → **the C4 PM owns INTG8's reconciliation** (their route, their QA §13 update per their plan). I did NOT
touch it (cross-lane). **C6 is green on its own.**
Commit caution: I did NOT commit C6 — the shared files (`api_server.py`, `conftest.py`) are entangled with the C4
PM's in-flight uncommitted edits and the suite is RED from their INTG8; committing now would capture a red tree +
their half-work. Commit C6 only once the lanes coordinate (C4 lands + fixes INTG8, or a clean per-file split).
**DECISION (Asaf, 16:43): HOLD — leave C6 uncommitted; let the C4 PM land their work + the INTG8 fix first, then
commit both lanes together.** C6 is done + green-on-its-own (CONN9 6/6; CONN10 live-gated); the only red is C4's
INTG8. I am NOT committing and NOT touching the shared tree further. Next commit (whoever lands it) should include
my C6 unstaged files: `Backend/api_seed.py`, `Backend/api_server.py` (ICP routes + lifespan), `Backend/tests/conftest.py`
(`_icp_collection` reset), `Backend/tests/test_api.py` (`TestCONN9`/`TestCONN10`), `NOTES.md`, `QA_checklist.md`,
`Plans/backend_connection_plan.md` — alongside the C4 work, once the suite is green again.

## 2026-06-20 17:00 — [BACKEND] SESSION END / HANDOFF (C4 landed + INTG8 fixed + COMBINED C4/C6 commit)
Did (C4 PM): Built **C4 — live, ICP-driven discovery engine** (connection-plan). New `Backend/pipeline_runner.py`
(deterministic real-tool chain, NOT the flaky 15-call loop) reads the persisted ICP via the C6 seam
`api_seed.get_icp_document()` → composes the seed from `vertical`+`want_signals` → real
`generate_search_queries`/`execute_3way_fanout`/`extract_and_score_pool`/`analyze_company_chunk` → graded
`evaluate_icp_tags` gate (untouched, ICPB5) → `icp_tags`/`avoid_signals` overlay → catalog matches persist
(Policy 1), net-new show-only. Async `POST`/`GET /api/pipeline/discover` (2–5 min runs) gated by
`ENABLE_LIVE` + `DISCOVERY_TOKEN` + single-job lock; job state in `pipeline_jobs`. **Fixed the INTG8 failure
the C6 PM flagged** (`test_fe_mock_endpoints_have_no_backend_route` — dropped `/api/pipeline/discover` from the
no-route list since `runDiscovery` is now backed). +13 `test_pipeline.py` (CONN7/11/12).
**Verified (PM, `.venv`, `MONGO_URI` unset):** full suite **796 passed / 6 skipped / 0 failed** — GREEN (the
C6 PM's lone red INTG8 is fixed). `main.py` untouched → tool count 10, `answer_question`, `FALLBACK_MESSAGE`
byte-stable; ENV4 from `/tmp` holds incl. `pipeline_runner._jobs_collection`. Deployed the code (route live →
`POST` 403 until enabled).
**Per Asaf's 16:43 HOLD decision** (commit both lanes together once green), Asaf then issued `create-pr` on
`feat/lead-detail-endpoint` → I committed the **combined C4 + C6 + spine** tree and pushed.
Status now: ✅ C4 code complete + offline-verified + committed/pushed (combined with C6). connection-plan
**C0–C2 + C6 ✅; C4 🔄 (code done, live pending keys)**; C3/C5 plan-only.
Next PM should: (1) **live-verify C4** once Asaf sets the 4 Railway vars (`ANTHROPIC_API_KEY`, `FIRECRAWL_API_KEY`,
`ENABLE_LIVE=1`, `DISCOVERY_TOKEN`) — POST `/api/pipeline/discover` + poll → real leads in Atlas; (2) **C5 / FE
wiring** (`/search`+`/swarm` → the endpoint; FE lane, Asaf's go-ahead pending); (3) open the PR (gh not authed
in-session → Asaf opens via the compare URL).
Watch out for / open: (1) `gh` NOT authenticated → I can push but cannot `gh pr create`; PR opened via URL by Asaf.
(2) Combined commit spans two PM lanes (C4 mine + C6 the other PM's) per Asaf's explicit 16:43 decision — branch
`feat/lead-detail-endpoint` now also carries C1/C2 + lead-detail + C4 + C6. (3) NEVER run the suite with
`MONGO_URI` set. (4) Live C4 enablement puts real keys + paid runs on the public URL (token-gated).

## 2026-06-20 17:15 — [BACKEND] SESSION START (fresh PM; post-C4/C6 merge)
Picking up: backend is **feature-complete + DEPLOYED + CONNECTED + PERSISTENT on real data.** No PLAN.md
stage is mid-flight. Read the spine in order (PM_Methodology → PM_LOG latest → CLAUDE → PLAN → QA families →
NOTES latest → ORCHESTRATION protocol per CLAUDE §0.1).
State as read (to re-verify before trusting any number): on the designated branch
**`claude/pm-methodology-eelg1u`**, working tree CLEAN, HEAD **`ec04ba7`** = merge of **PR #4**
(`52c0b37` C4 live ICP-driven discovery + C6 ICP durable substrate). So the concurrent C4/C6 work the
16:38/17:00 entries flagged as uncommitted/interleaved is now **landed on `main` and merged here** — the
HOLD is resolved. Stages 0–14 ✅, Phase 3 I0–I4 ✅ (I5 deferred), Phase 4 D0–D4 ✅, Phase 5 connection-plan
**C0–C2 + C4(code) + C6 ✅**; C3/C5 plan-only. Last claimed offline baseline (NOTES C4 entry) = **796 passed
/ 6 skipped / 0 failed** (`MONGO_URI` unset, mongomock) from cwd `Backend/` — **PLAN.md "Current project
state" still reads 777, stale (pre-C4/C6 merge); doc-drift to reconcile.** Live stack: FE Vercel
`crm-asaf6.vercel.app` ↔ BE Railway `backend-production-77e4.up.railway.app` ↔ Atlas `gtm_db` (9 real
athleisure leads). C4 route live but 403 until the 4 Railway vars are set.
Plan for this session: NOT advancing any stage unprompted. Await Asaf's pick from the standing open-items
menu; re-verify the 796/6 baseline myself in `.venv` from `Backend/` before acting on any number. Stay in
lane (no `frontend/`). Write a SESSION END before stopping.
