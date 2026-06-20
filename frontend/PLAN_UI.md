# PLAN_UI.md — Frontend stage tracker

Frontend-only workstream (SLED-style GTM dashboard). Parallel to, and independent of, the backend
PM's `PLAN.md`/`NOTES.md`. Approved plan: `~/.claude/plans/proud-brewing-scott.md`.

Read order for a session: `../PM_Methodology_Prompt.md` → latest `[FRONTEND]` entry in
`../PM_LOG.md` → this file → `NOTES_UI.md` → the screenshot in `../Images/` for the screen at hand.

**PM session ritual (non-negotiable, per `../PM_Methodology_Prompt.md`):** at session start,
append a `[FRONTEND] SESSION START` entry to the root `../PM_LOG.md`; at session end (or any
halt), append a `[FRONTEND] SESSION END / HANDOFF` entry. The shared `PM_LOG.md` is the only
backend-root file the Frontend PM writes — otherwise stay in `frontend/`.

Status: ⬜ Not started · 🔄 In progress · 🟡 Awaiting parity check · ✅ Complete

| Stage | Name | Parity ref | Status |
|---|---|---|---|
| F0 | Scaffold + design system + app shell | `…9.03.19` (nav) | ✅ Complete |
| F1 | Leads Dashboard (lead table) | `…9.04.11` | ✅ Complete |
| F2 | ICP Builder (tags + AI suggestions) | `…9.03.36` / `…9.03.43` | ✅ Complete |
| F3 | Outreach Center | `…9.07.17` | ✅ Complete |
| F4 | Search & Explore + Leads Swarm | `…9.03.48` + swarm slide | ✅ Complete |
| F5 | Cross-screen state + lead-detail + final parity | all | ✅ Complete |

## Gate discipline
A stage is done only when (1) its interaction checks work against mocks **when run**, and (2) a
Preview-MCP screenshot has been reviewed against the reference screenshot and judged "same product."

## F0 — DoD
- [x] Vite + React + TS + Tailwind + shadcn-style components under `frontend/`.
- [x] Light design tokens extracted from screenshots (`src/index.css`).
- [x] `AppShell` = dark icon rail (6 layers) + top bar + content outlet.
- [x] React Router: all 6 routes navigable; active state tracks (verified via Preview MCP).
- [x] `lib/api.ts` seam + TanStack Query provider + Zustand store scaffolded.
- [x] `tsc --noEmit` clean; dev server runs with no errors.
- [x] Nav/chrome parity vs `…9.03.19` confirmed via Preview-MCP screenshot.

## F1 — Leads Dashboard ✅ Complete (2026-06-19)
Target: `Images/…9.04.11`. Metric-card header; LeadTable (Company+domain / Score / Fit / Gov / Lead
badges); sortable; row checkboxes + Select-all-actionable + BulkActionBar; FilterTabs (All/New/Existing)
+ search; left discovery rail with loop controls (Discovery goal, Find N More, Replace, Clear).
DoD: parity vs `…9.04.11`; sort / filter / multi-select / bulk / Find-More all work against mocks.

- [x] `LeadsDashboard` page composes rail + funnel header + filter tabs + search + table + bulk bar,
      wired to `lib/api.ts` via TanStack Query; `/leads` route now renders it (was `Placeholder`).
- [x] `DiscoveryFunnel` — green "Discovery complete · Balanced strictness" funnel
      (Goal 150 → Discovered 131 −36 filtered by ICP → Retained 95 −43 below floor → Above floor 52)
      + retained breakdown line (74 new · 21 existing; 69 Strong / 10 Review / 16 Weak; 21 in CRM).
- [x] `FilterTabs` — All/New/Existing/Above-floor pills with live count badges + dashed "N filtered out".
- [x] Badges to reference labels: Score violet (`rgb(124,58,237)`, inspected); Fit "Strong Fit" (green);
      Gov "Light Gov" (blue) / "Heavy Gov" (amber); Lead "Existing" (green) / "New". Circular row checkboxes.
- [x] **Interactions verified live (Preview MCP):** sort (Score 85→64 on flip), filter (All 16 → New 9,
      all kind New), search ("boom" → 1 = BoomPop), multi-select → BulkActionBar "16 selected", Find-More
      (16 → 20, 4 deduped rows appended). `tsc --noEmit` exit 0; no console errors.
- [x] **Parity:** Preview-MCP screenshot @1280px judged "same product" vs `…9.04.11`.

## 2026-06-20 — Outreach Engine screen + button-functionality pass (post-F5)
- **Built `/outreach` "Outreach Engine"** (`features/OutreachEngine.tsx`) — was the last `Placeholder`.
  Reuses `CohortTimeline` + `AgentEventLog` + `MetricCards`; **wired** to `api.getOutreachStats` +
  `api.getCohorts` (real backend data via the `/api` proxy — verified: `GET /api/outreach/stats|cohorts`
  200; metrics 3 cohorts/16 companies/12.5% match the seed). Routed in `App.tsx` (Placeholder removed).
- **Button-functionality pass** (Asaf flagged dead buttons). Wired every dead content/action button:
  - `BulkActionBar`: Enroll→`/outreach`, Add tag→`/icp`, Export→CSV download (new `lib/exportCsv.ts`).
  - `DiscoveryRail`: Replace→reset+refetch, Clear→reset, Restore→find-more, Enrichment→`/swarm`,
    "Other ways"→`/search`.
  - `LeadDetailDrawer`: Generate deck→brief `.txt`, Export→CSV, Enroll→`/outreach`.
  - `OutreachCenter`: New Enrollment→`/outreach`.
  - **Verified live:** Enrichment→/swarm; Select-all→BulkActionBar→Enroll→/outreach. `tsc --noEmit` clean.
  - **Still decorative (flagged, not faked):** TopBar bell / avatar / global-search — need real
    notifications/profile/global-search features; left for a follow-up.
