/*
 * THE backend seam.
 * The 8 WIRED methods below fetch from the FastAPI backend (Phase 3) via the Vite
 * `/api` proxy (vite.config.ts → http://localhost:8000). The remaining methods
 * (lead detail, reach series, agent events, discovery, swarm stages) stay on local
 * fixtures in v1 — the backend does not serve those yet (see PLAN.md Phase 3 / I5).
 * Components import ONLY from here, never from `@/mocks/*` directly.
 */
import type {
  Lead,
  LeadDetail,
  LeadDiscoveryStats,
  IcpDocument,
  OutreachStats,
  ReachPoint,
  AgentEvent,
  Cohort,
  EnrollmentEvent,
  DiscoveryResult,
  SwarmStage,
} from "@/types";
const BASE_URL = import.meta.env.VITE_API_URL ?? "/api";

function delay<T>(value: T, ms = 280): Promise<T> {
  return new Promise((resolve) => setTimeout(() => resolve(value), ms));
}

async function getJSON<T>(path: string): Promise<T> {
  const r = await fetch(`${BASE_URL}${path}`);
  if (!r.ok) throw new Error(`GET ${path} failed: ${r.status} ${r.statusText}`);
  return r.json() as Promise<T>;
}

async function postJSON<T>(path: string, body: unknown): Promise<T> {
  const r = await fetch(`${BASE_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`POST ${path} failed: ${r.status} ${r.statusText}`);
  return r.json() as Promise<T>;
}

export const api = {
  // ─── Leads (WIRED → backend) ────────────────────────────────────────────────
  getLeads(): Promise<Lead[]> {
    return getJSON<Lead[]>("/leads");
  },

  getLeadStats(): Promise<LeadDiscoveryStats> {
    return getJSON<LeadDiscoveryStats>("/leads/stats");
  },

  /** Loop control: "Find N More" — server dedupes against the domains we already have. */
  findMoreLeads(existing: Lead[], target = 4): Promise<Lead[]> {
    return postJSON<Lead[]>("/leads/find-more", {
      existing_domains: existing.map((l) => l.domain),
      target,
    });
  },

  // ─── ICP Builder (WIRED → backend) ──────────────────────────────────────────
  getIcpDocument(): Promise<IcpDocument> {
    return getJSON<IcpDocument>("/icp");
  },

  getIcpSuggestions(): Promise<string[]> {
    return getJSON<string[]>("/icp/suggestions");
  },

  // ─── Outreach Center (WIRED → backend) ──────────────────────────────────────
  getOutreachStats(): Promise<OutreachStats> {
    return getJSON<OutreachStats>("/outreach/stats");
  },

  getCohorts(): Promise<Cohort[]> {
    return getJSON<Cohort[]>("/outreach/cohorts");
  },

  getEnrollments(): Promise<EnrollmentEvent[]> {
    return getJSON<EnrollmentEvent[]>("/outreach/enrollments");
  },

  // ─── Still FE-mock in v1 (no backend route yet — see PLAN.md Phase 3 / I5) ────

  // No per-lead detail endpoint yet (needs /api/leads/{id} behind the Policy-4 gate).
  // Reject so the drawer shows its honest "couldn't load" state instead of fabricated detail.
  getLeadDetail(_id: string): Promise<LeadDetail> {
    return Promise.reject(new Error("Lead detail source not connected"));
  },

  // No live reach-by-stage source (needs the outreach execution log — not built). Empty, not faked.
  getReachSeries(): Promise<ReachPoint[]> {
    return delay([]);
  },

  // No live agent-event source (needs the agent observability layer — not built). Empty, not faked.
  getAgentEvents(): Promise<AgentEvent[]> {
    return delay([], 180);
  },

  // Live discovery needs the search/analyze pipeline + API keys (not configured). Empty, not faked.
  runDiscovery(_seed: string, _count: number, _run = 1): Promise<DiscoveryResult[]> {
    return delay([], 400);
  },

  // No live swarm/enrichment pipeline (needs the analyze layer + keys). Empty, not faked.
  getSwarmStages(): Promise<SwarmStage[]> {
    return delay([]);
  },
};
