/*
 * UI domain types. These are the contract for the `lib/api.ts` seam.
 * They loosely mirror the backend shapes (crm_store.py records, qualified_leads.json)
 * so swapping mocks for real responses later is mechanical. UI-oriented field names.
 */

export type FitGrade = "Strong" | "Medium" | "Weak";
export type GovBand = "Heavy Gov" | "Light Gov" | "No Gov";
export type LeadKind = "New" | "Existing";

/** Where a lead sits in the 6-layer lifecycle. */
export type LifecycleStage =
  | "discovered" // L2 search & explore
  | "enriched" // L3/L5 swarm profiling
  | "qualified" // passed ICP gate
  | "in_crm" // L5 workspace
  | "enrolled" // L6 outreach cohort
  | "replied"
  | "closed";

export interface Lead {
  id: string;
  company: string;
  domain: string;
  score: number; // 0-100 unified score
  fit: FitGrade;
  gov: GovBand;
  kind: LeadKind;
  stage: LifecycleStage;
  tags: string[]; // ICP tags this lead matched
  winProb?: number; // 0-1, from compute_win_prob (catalog-sourced)
}

/**
 * The discovery-run funnel shown in the dashboard header. Mirrors the SLED
 * "Discovery complete" strip: goal → discovered (−filteredByIcp) → retained
 * (−belowFloor) → aboveFloor, plus the retained-set breakdown chips.
 */
export interface LeadDiscoveryStats {
  goal: number; // target companies for the loop
  discovered: number; // raw found
  filteredByIcp: number; // dropped by the ICP gate
  retained: number; // kept "in table"
  belowFloor: number; // dropped below the media floor
  aboveFloor: number; // new + above floor (actionable)
  newCount: number; // of retained: new
  existingCount: number; // of retained: existing
  alreadyInCrm: number; // existing already in CRM
  strong: number; // retained fit breakdown
  review: number;
  weak: number;
  strictness: string; // e.g. "Balanced strictness"
}

/** Grouped tag chips that both define an ICP and filter the lead list. */
export interface TagGroupData {
  id: string;
  label: string;
  tags: string[];
}

export interface IcpDocument {
  id: string;
  title: string;
  description: string;
  source: "Companies" | "Leads";
  keywords: string[];
  industryVerticals: string[];
  geographicFocus: string[];
  /** Company size band, e.g. "Mid-Market" / "Enterprise" (drives the discovery seed). */
  sizeBand: string;
  /** Canonical ICP tags (== backend _ICP_TAGS keys) — these drive per-lead ICP scoring. */
  icpTags: string[];
  qualificationCriteria: { criterion: string; importance: "High" | "Medium" | "Low" }[];
  anchorCompanies: { name: string; domain: string; why: string }[];
}

export type CohortStageStatus = "sent" | "queued" | "replied" | "lead" | "skipped";

// ─── Outreach Center types ────────────────────────────────────────────────────

export interface OutreachStats {
  totalCohorts: number;
  totalCompanies: number;
  inCampaign: number;
  inCampaignCohorts: number; // for the sub-line "across N cohorts"
  replies: number;
  replyRate: number; // 0-1 (e.g. 0.025 = 2.5%)
}

/** One data-point for the "Companies reached by stage" line chart. */
export interface ReachPoint {
  date: string;    // e.g. "Apr 24"
  formBot: number;
  connect: number;
  email1: number;
  email2: number;
  liMessage: number;
  email3: number;
}

/** A single event in the agent observability feed. */
export interface AgentEvent {
  id: string;
  date: string;    // "YYYY-MM-DD" — used for day-divider grouping
  time: string;    // "HH:MM AM/PM"
  text: string;    // e.g. "Roy Linkedin inbox scrape"
}

/** A single stage node inside a cohort variant row. */
export interface CohortVariantStage {
  icon: "clock" | "linkedin" | "mail";
  status: "done" | "queued" | "dead";
  count: string;       // e.g. "14" or "35+28"
  gapBefore?: string;  // e.g. "1d" — duration label on the connector before this node
}

export interface CohortVariant {
  label: string;       // e.g. "control", "email_heavy"
  stages: CohortVariantStage[];
  outcome: { dead: number; success: number };
}

export interface Cohort {
  id: string;
  name: string;
  enrolledAt: string;  // human-readable e.g. "Mar 31, 2026 4:58 PM"
  leadsCount: number;
  variants: CohortVariant[];
}

/** A single enrollment event to render as a pill on the calendar. */
export interface EnrollmentEvent {
  id: string;
  date: string;  // ISO "YYYY-MM-DD"
  label: string;
}

// ─── Legacy Cohort/CohortStage (kept for type-safety, not used on F3) ─────────
export interface CohortStage {
  label: string;
  count: number;
  status: CohortStageStatus;
}

// ─── Lead detail workspace (F5 — drawer) ──────────────────────────────────────

export interface LeadContact {
  name: string;
  role: string;
  email: string;
}

export interface LeadAngle {
  title: string;
  /** 1–4; Tier 4 = No Match */
  tier: 1 | 2 | 3 | 4;
  rationale: string;
}

/** Extended lead record returned by api.getLeadDetail(). */
export interface LeadDetail extends Lead {
  contacts: LeadContact[];
  angle: LeadAngle;
  brief: string;
}

// ─── Pipeline types (F4 — Search & Explore + Leads Swarm) ─────────────────────

/** A single company discovered during a Search & Explore run. */
export interface DiscoveryResult {
  domain: string;
  company: string;
  score: number;   // 0-100
  fit: "Strong" | "Medium" | "Weak";
}

/** Swarm enrichment status for a single stage card. */
export type SwarmStageStatus = "queued" | "running" | "done";

/** One of the 4 durable-workflow stages in the Leads Swarm view. */
export interface SwarmStage {
  id: string;
  title: string;
  subtitle: string;
  targetCount: number;
  /** Optional pixel-detection chip labels emitted by this stage (e.g. Analyzer). */
  pixelChips?: string[];
}
