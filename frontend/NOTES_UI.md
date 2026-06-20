# NOTES_UI.md — Frontend decisions & handbacks

## 2026-06-19 — Stack & approach
- **Stack:** Vite 5 + React 18 + TS + Tailwind 3 + shadcn-style components on Radix.
- **Decision:** built shadcn-style primitives by hand (`src/components/ui/*`) instead of the
  shadcn CLI — the CLI is interactive/registry-dependent; hand-built copies are identical in spirit
  (shadcn *is* copy-paste components) and fully reproducible offline. Radix + cva + tailwind-merge.
- **Decision:** mock fixtures live in `src/mocks/*.ts` (typed modules), not `.json` — lets the
  `@/types` contract enforce shape at author time. Components import **only** from `@/lib/api.ts`
  (the backend seam), never from `@/mocks` directly.
- **State:** TanStack Query wraps the api seam (free loading/empty/error); Zustand
  (`store/useGtmStore.ts`) holds cross-screen state — the **shared tag vocabulary** (ICP defines /
  leads filter, SLED's "one vocabulary, two jobs") and the lead selection set for bulk actions.

## 2026-06-19 — Design tokens (light, from SLED product screenshots)
HSL CSS vars in `src/index.css`:
- `--background 40 14% 97%` warm off-white canvas; `--card 0 0% 100%` white cards.
- `--foreground 220 14% 16%` near-black slate text; `--border 30 8% 90%` hairline.
- `--primary 222 24% 18%` dark slate buttons; `--sidebar 222 24% 13%` dark icon rail.
- `--accent 152 32% 92%` / `--accent-foreground 152 45% 24%` → green tag chips.
- Status palette: `--success` green (Strong/Retained), `--warning` amber (queued/medium),
  `--info` blue (gov). Radius `0.625rem`. Font: Inter.

## 2026-06-19 — F0 handback
- **Built:** config (vite/ts/tailwind/postcss), `index.css` tokens, UI primitives
  (button, card, badge, input, tabs, checkbox, table, tooltip), `lib/utils` (`cn`, `fmtInt`),
  `types/index.ts`, `mocks/leads.ts`, `lib/api.ts`, Zustand store, `nav.ts` (6 layers),
  `IconRail` / `TopBar` / `AppShell`, routes + `Placeholder`, `main.tsx`.
- **Preview:** `.claude/launch.json` (root) runs `npm --prefix frontend run dev` on :5173.
- **Fix during parity check:** the active-nav indicator (absolutely-positioned `<span>` via a
  NavLink children-render-fn) escaped its link and rendered in empty rail space. Replaced with a
  className-function + `shadow-[inset_2px_0_0_0_#fff]` accent — robust, no absolute child. Verified.
- **QA:** `tsc --noEmit` exit 0; dev server no errors; 6 routes navigable; active state tracks
  (`aria-current=page` + visible highlight) — confirmed via Preview-MCP screenshots.
- **Next:** F1 Leads Dashboard.

## 2026-06-19 — F1 handback (Leads Dashboard, parity `…9.04.11`)
- **Built:** `features/LeadsDashboard.tsx` (the page — composes rail + funnel + filter tabs +
  search + Select controls + table + bulk bar; data via TanStack Query on `lib/api.ts`),
  `components/leads/DiscoveryFunnel.tsx`, `components/leads/FilterTabs.tsx`. Refined
  `DiscoveryRail`, `StatusBadges`, `LeadTable`; widened the contract in `types/index.ts` +
  `mocks/leads.ts`. Wired `/leads` → `LeadsDashboard` in `App.tsx` (was `Placeholder`).
- **Funnel header** = the SLED "Discovery complete · Balanced strictness" strip rendered from
  `LeadDiscoveryStats`. I **redefined `LeadDiscoveryStats`** from the old discovered/scored/
  retained/meanScore/qualified shape to a funnel shape (goal/discovered/filteredByIcp/retained/
  belowFloor/aboveFloor + new/existing/alreadyInCrm + strong/review/weak + strictness). Only the
  api seam + this header consume it, so the swap was contained. Made the mock numbers internally
  consistent (131−95 = 36 `filteredByIcp`, matching the "36 filtered out" pill; 95−43 = 52
  aboveFloor; 74+21 = 95; 69+10+16 = 95) — the reference's own −38 was inconsistent, so I used 36.
- **Type change:** `GovBand` "Strong Gov" → **"Heavy Gov"** to match the reference label (amber).
  Gov palette: Light Gov = blue/info outline, Heavy Gov = amber/warning outline, No Gov = muted.
  Fit badge now renders `"{grade} Fit"` ("Strong Fit"). Score is brand **violet**
  (`text-violet-600` = rgb(124,58,237), inspected live). Row checkboxes are circular
  (`rounded-full`) to match the reference's ○ selectors.
- **Decision — tab counts are live, funnel is the run summary.** Filter-tab badges
  (All 16 / New 9 / Existing 7 / Above floor 10) derive from the **actual rendered pool** so
  filtering stays honest; the funnel header keeps the discovery-run totals (150/131/95/52). They
  describe different things (the loaded table vs the whole run), so the count mismatch is by design,
  not a bug. "Above floor" = score ≥ `SCORE_FLOOR` (75). "Select all actionable (N)" selects the
  current filtered set; "Select" clears.
- **Orphan:** `components/shell/MetricCards.tsx` is now unused (the funnel replaced the card grid).
  Left in place, not imported — harmless; can be deleted in a later cleanup.
- **Verified live (Preview MCP, 1280px):** `tsc --noEmit` exit 0; no console errors; sort
  (Score 85→64 on flip), filter (16→9, all New), search ("boom"→1 BoomPop), multi-select →
  BulkActionBar "16 selected", Find-More (16→20, 4 deduped appended). Screenshot judged
  "same product" vs `…9.04.11`.
- **Next:** F2 ICP Builder (parity `…9.03.36` / `…9.03.43`) — tags + AI suggestions; will reuse the
  Zustand `tagVocabulary` (the shared ICP↔Leads vocabulary already scaffolded).

## 2026-06-19 — F2 handback (ICP Builder, parity `…9.03.36`/`…9.03.43`)
- **Delegated to a fresh `general-purpose` executer (sonnet)** with a self-contained brief; PM ran the
  parity gate. Handback at `frontend/handbacks/F2.md`.
- **Built:** `features/IcpBuilder.tsx` (3-column: left Configuration / center editor / right AI rail),
  new ui primitives `ui/select.tsx` (native styled), `ui/textarea.tsx`, tag components
  `components/tags/{TagChip,TagInput,TagGroup}.tsx`, `mocks/icp.ts` (MOCK_ICP + 8 suggestions),
  `api.getIcpDocument()` + `api.getIcpSuggestions()`, store action `setTagVocabulary`. Route `/icp`
  → `IcpBuilder` (was Placeholder).
- **Shared vocabulary (DoD):** Keywords group is backed by Zustand `tagVocabulary` (seeded from the doc
  on load via `setTagVocabulary`; add/remove → `addTag`/`removeTag`). Industry Verticals + Geographic
  Focus are local state.
- **PM-verified live (Preview MCP @1360px):** screenshot judged "same product" vs ref (3 columns,
  editable title + Copy/Delete, Editor/Markdown/Examples tabs, green Keyword/Industry/Geographic chip
  groups, left config form with Source toggle + selects + Require-US-office + team-size + segments,
  right AI rail). `tsc --noEmit` exit 0; no console errors. **Interactions I re-ran myself:** Get
  Suggestions → 8 chips; accept one → suggestions 8→7 AND Keywords helper count 16→17 (confirms the
  store-backed add). Executer additionally verified source toggle, tab switch, typed-keyword add.
- **Tolerated minor:** section labels render UPPERCASE (KEYWORDS / INDUSTRY VERTICALS) vs the ref's
  sentence-case — within "same product"; consistent with the left panel's "QUALIFICATION CRITERIA".
  Markdown/Examples tabs are placeholder bodies (brief scope: only Editor built out).
- **Next:** F3 Outreach Center (parity `…9.07.17`) — metric cards + reach-by-stage line chart (Recharts)
  + cohort timelines + agent event log + enrollment calendar.

## 2026-06-19 — F3 handback (Outreach Center, parity `…9.07.17`)
- **Fresh `general-purpose` executer (sonnet)**, new cold agent (different from F2's). Handback at
  `frontend/handbacks/F3.md`.
- **Built:** `features/OutreachCenter.tsx` + `components/outreach/{ReachByStageChart,AgentEventLog,
  CohortTimeline,EnrollmentCalendar}.tsx`, `mocks/outreach.ts`, 5 new `api.*` methods. **Reused the
  orphaned `shell/MetricCards.tsx`** for the 5-card row (un-orphaned). Route `/center` → `OutreachCenter`.
- **Type reshape (executer-owned, recorded):** `OutreachStats` (totalCohorts/totalCompanies/inCampaign/
  inCampaignCohorts/replies/replyRate), `ReachPoint` → 6 series fields (formBot/connect/email1/email2/
  liMessage/email3), `AgentEvent` → {id,date,time,text} for day-divider grouping, `Cohort` →
  {name,enrolledAt,leadsCount,variants:[{label,stages:[{icon,status,count,gapBefore}],outcome}]},
  new `EnrollmentEvent`. Old `CohortStage` kept as legacy (unused). These are frontend-only mock
  contracts (backend still mocked behind api.ts), so the reshape is contained.
- **PM-verified live (Preview MCP @1360px):** screenshot judged "same product" vs ref — header +
  "3 active campaigns / 4 total" + New Enrollment; 5 metric cards (4 / 221 / 150 / 6 / 2.5%); 6-series
  Recharts line chart with `[7d|30d|All]` toggle + legend "FormBot · Connect · Email #1 · Email #2 ·
  LI Message · Email #3"; mono Agent Event Log w/ date dividers; Cohorts & variants funnel timelines
  (status-colored nodes done/queued/dead + ✗/✓ outcomes); Enrollment Calendar. `tsc --noEmit` exit 0;
  no console errors. **Interactions I re-ran myself:** event-log search "Connection" → narrows to the
  Connection-export rows; calendar prev-month June 2026→May 2026 → green enrollment pills appear.
- **Note for later:** mock enrollments are dated **May 2026** while today is June 2026, so pills only
  show after one Prev click — fine, just a mock-date choice. Recharts emits no console noise.
- **Next:** F4 Search & Explore (`…9.03.48`) + Leads Swarm (swarm slide) — query-gen → 3-way fanout viz
  → unified scorer; durable-workflow chunk progress.

## 2026-06-19 — F4 handback (Search & Explore + Leads Swarm)
- **Fresh `general-purpose` executer (sonnet)**, new cold agent. Handback `frontend/handbacks/F4.md`.
- **Decision (recorded) — light, not dark.** The F4 references (`…9.03.48`, `…9.07.01`) are DARK
  marketing/architecture slides. The locked product decision is LIGHT. Building dark pages inside the
  light app shell would look broken, so I had the executer build **light** screens that faithfully
  reproduce the *pipeline structure* from the slides. Parity bar for F4 = "reflects the pipeline, looks
  like part of this product, run animates + streams" (looser than F1–F3's pixel parity, per the plan).
- **Decision (recorded) — our Claude labels, not the slide's.** The slide says Gemini/gpt-4o-mini; our
  engine is Claude-based (see backend CLAUDE.md §1.2). Used OUR real names: Query Generator = Claude
  Haiku 4.5, Vector A = Claude Web Search (web_search·web_fetch), Vector B = SerpAPI+Maps, Vector C =
  Tavily Recovery, Unified Scorer = Claude. Swarm stages map to the real tools (analyze_company_chunk
  Sonnet+Firecrawl ≤100/800s + pixel detection, evaluate_icp_tags ≥3, match_solicitation_angle RRF
  Tier 1–4, profile/contacts expander).
- **Built:** `components/pipeline/{FlowNode,FlowArrow}.tsx`, `features/SearchExplore.tsx`,
  `features/LeadsSwarm.tsx`, `mocks/pipeline.ts`, `api.runDiscovery()` + `api.getSwarmStages()`,
  types `DiscoveryResult`/`SwarmStage`. Routes `/search` + `/swarm` wired (were Placeholders);
  `/outreach` (Outreach Engine L5) intentionally left Placeholder (no reference; out of F4 scope).
- **PM-verified live (Preview MCP):** both render as coherent light product screens. `tsc --noEmit`
  exit 0; no console errors. **Run animations I drove myself:** Run Discovery → all flow nodes
  idle→running→done (green checks), button → "Run Again", 10 companies streamed into "Discovered
  companies" with violet scores + Strong/Medium Fit badges. Run Swarm → 4 stages queued→done, overall
  100%, pixel chips lit, swarm log streamed realistic lines (Analyzer pixels, Tag Evaluator ≥3-tag
  qualify, Matcher Tier 1–4, Expander +contacts/win-prob). Executer cleaned up all timers on unmount.
- **Next:** F5 — cross-screen state (discovery → leads pool), lead-detail drawer, empty/loading/error
  polish, final parity pass across all 6 screens.

## 2026-06-19 — F5 handback (cross-screen + lead detail + polish) — FRONTEND COMPLETE
- **Fresh `general-purpose` executer (sonnet)**, new cold agent. Handback `frontend/handbacks/F5.md`.
- **Built:** `ui/sheet.tsx` (Radix Dialog as right slide-in sheet, Esc/overlay/X close, focus trap),
  `components/leads/LeadDetailDrawer.tsx` (workspace: header+badges, ICP tags, win-prob bar, matched
  angle+Tier badge+rationale, key contacts + Policy-4 note, pre-meeting brief, Generate deck / Export /
  Enroll actions), `mocks/leadDetail.ts`, `api.getLeadDetail()`. Store: `discoveredLeads` +
  `addDiscoveredLeads` (dedupe by domain) + `clearDiscovered`. `LeadTable` gained `onRowClick` (rows
  `cursor-pointer`; checkbox cell + domain link `stopPropagation`). `LeadsDashboard` merges
  query+extra+discovered (deduped) and renders the drawer; error fallbacks added to Leads/ICP/Outreach.
- **PM fixture fix (inline, recorded):** the discovery mock reused only companies already in the leads
  pool, so the cross-screen merge deduped to ZERO visible rows (feature correct but invisible). I made a
  trivial fixture edit in `mocks/pipeline.ts` — swapped a few duplicate companies for 3 net-new ones
  (Reed & Mackay / World Travel Inc / Corporate Traveler) + a new 2nd batch (Altour / Gant Travel / JTB)
  — so the merge is demonstrable. Chose inline over a fresh-executer spawn per the budget rule (don't
  spawn a cold agent for a 3-line fixture change needed for my own gate). `tsc --noEmit` exit 0 after.
- **PM-verified live (Preview MCP @1360px):** **Lead-detail drawer** opens on company-cell row-click
  (screenshot: BCD Meetings & Events workspace — tags MICE/DMC, win-prob 62%, angle "Full-Funnel Event
  Attribution" Tier 1, 3 contacts + Policy-4 note, brief, action buttons); **checkbox click selects the
  row WITHOUT opening the drawer** (BulkActionBar "1 selected", no dialog) — the row-click discrimination
  works; **Close button dismisses** the drawer. **Cross-screen:** ran discovery on `/search` → `/leads`
  pool grew 16→**19** ("All 19", "New 12"); searching "reed" surfaced the discovered **Reed & Mackay**
  (reedmackay.com, 73, Medium Fit, New). `tsc --noEmit` exit 0; no console errors.
- **Tooling note:** synthetic `MouseEvent`/`KeyboardEvent` dispatch does NOT trigger Radix Dialog close
  (modality/focus) — use the Preview MCP **real** `preview_click` on `[aria-label="Close"]`. Recorded so
  the next PM doesn't chase a phantom "drawer won't close" bug.
- **Final parity pass (all 6 routes):** `/leads` (F1+F5) ✅, `/icp` (F2) ✅, `/center` (F3) ✅,
  `/search` + `/swarm` (F4) ✅ — all judged "same product" vs their refs and interaction-verified.
  `/outreach` (Outreach Engine, Layer 5) intentionally remains a Placeholder — no reference screenshot
  exists for it and it is out of the F0–F5 scope.
- **STATUS: Frontend F0–F5 COMPLETE.** Backend swap remains the only future work (each `api.*` fn flips
  from `delay(mock)` to `fetch()` with no component change — the seam held across all 5 stages).
