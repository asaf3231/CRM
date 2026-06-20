import { create } from "zustand";
import type { Lead } from "@/types";

/*
 * Cross-screen state. The shared `tagVocabulary` is the single source of truth used
 * by BOTH the ICP Builder (to define an ICP) and the Leads Dashboard (to filter) —
 * SLED's "one vocabulary, two jobs" pattern. `selectedLeadIds` drives bulk actions.
 *
 * `discoveredLeads` (F5) holds companies discovered on Search & Explore that haven't
 * yet been loaded into the main leads query — the cross-screen flow that makes a lead
 * travel from "discovered" to the Lead Workspace.
 */
interface GtmState {
  tagVocabulary: string[];
  selectedLeadIds: string[];
  activeIcpId: string | null;
  /** Leads discovered via Search & Explore that flow into the Leads Dashboard pool. */
  discoveredLeads: Lead[];

  addTag: (tag: string) => void;
  removeTag: (tag: string) => void;
  setTagVocabulary: (tags: string[]) => void;
  setSelectedLeads: (ids: string[]) => void;
  toggleLead: (id: string) => void;
  clearSelection: () => void;
  setActiveIcp: (id: string | null) => void;
  /** Merge new leads into discoveredLeads, deduped by domain. */
  addDiscoveredLeads: (leads: Lead[]) => void;
  clearDiscovered: () => void;
}

export const useGtmStore = create<GtmState>((set) => ({
  tagVocabulary: [],
  selectedLeadIds: [],
  activeIcpId: null,
  discoveredLeads: [],

  addTag: (tag) =>
    set((s) =>
      s.tagVocabulary.includes(tag) ? s : { tagVocabulary: [...s.tagVocabulary, tag] }
    ),
  removeTag: (tag) => set((s) => ({ tagVocabulary: s.tagVocabulary.filter((t) => t !== tag) })),
  setTagVocabulary: (tags) => set({ tagVocabulary: tags }),
  setSelectedLeads: (ids) => set({ selectedLeadIds: ids }),
  toggleLead: (id) =>
    set((s) => ({
      selectedLeadIds: s.selectedLeadIds.includes(id)
        ? s.selectedLeadIds.filter((x) => x !== id)
        : [...s.selectedLeadIds, id],
    })),
  clearSelection: () => set({ selectedLeadIds: [] }),
  setActiveIcp: (id) => set({ activeIcpId: id }),
  addDiscoveredLeads: (incoming) =>
    set((s) => {
      const existingDomains = new Set(s.discoveredLeads.map((l) => l.domain));
      const fresh = incoming.filter((l) => !existingDomains.has(l.domain));
      if (fresh.length === 0) return s;
      return { discoveredLeads: [...s.discoveredLeads, ...fresh] };
    }),
  clearDiscovered: () => set({ discoveredLeads: [] }),
}));
