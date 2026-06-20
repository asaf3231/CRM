import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Search, CheckSquare, SquareDashed, RefreshCw } from "lucide-react";
import { api } from "@/lib/api";
import type { Lead } from "@/types";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { useGtmStore } from "@/store/useGtmStore";
import { DiscoveryRail } from "@/components/leads/DiscoveryRail";
import { DiscoveryFunnel } from "@/components/leads/DiscoveryFunnel";
import { FilterTabs, type LeadFilter } from "@/components/leads/FilterTabs";
import { LeadTable } from "@/components/leads/LeadTable";
import { BulkActionBar } from "@/components/leads/BulkActionBar";
import { LeadDetailDrawer } from "@/components/leads/LeadDetailDrawer";

/** Score floor for the "Above floor" filter — leads at/above are immediately actionable. */
const SCORE_FLOOR = 75;

export function LeadsDashboard() {
  const leadsQuery = useQuery({ queryKey: ["leads"], queryFn: api.getLeads });
  const statsQuery = useQuery({ queryKey: ["leadStats"], queryFn: api.getLeadStats });

  const [extra, setExtra] = useState<Lead[]>([]);
  const [filter, setFilter] = useState<LeadFilter>("All");
  const [search, setSearch] = useState("");
  const [goal, setGoal] = useState(150);
  const [finding, setFinding] = useState(false);
  const [findError, setFindError] = useState<string | null>(null);
  const [activeLead, setActiveLead] = useState<Lead | null>(null);

  const { setSelectedLeads, discoveredLeads } = useGtmStore();

  // Merge queryData + extra (Find-More) + discoveredLeads from SearchExplore.
  // Deduplicate by domain so the same company doesn't appear twice if it was
  // both in the initial data and pushed from the discovery screen.
  const allLeads = useMemo(() => {
    const pool: Lead[] = [];
    const seenDomains = new Set<string>();
    for (const l of [...(leadsQuery.data ?? []), ...extra, ...discoveredLeads]) {
      if (!seenDomains.has(l.domain)) {
        seenDomains.add(l.domain);
        pool.push(l);
      }
    }
    return pool;
  }, [leadsQuery.data, extra, discoveredLeads]);

  const counts: Record<LeadFilter, number> = useMemo(
    () => ({
      All: allLeads.length,
      New: allLeads.filter((l) => l.kind === "New").length,
      Existing: allLeads.filter((l) => l.kind === "Existing").length,
      "Above floor": allLeads.filter((l) => l.score >= SCORE_FLOOR).length,
    }),
    [allLeads]
  );

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return allLeads.filter((l) => {
      if (filter === "New" && l.kind !== "New") return false;
      if (filter === "Existing" && l.kind !== "Existing") return false;
      if (filter === "Above floor" && l.score < SCORE_FLOOR) return false;
      if (q && !`${l.company} ${l.domain}`.toLowerCase().includes(q)) return false;
      return true;
    });
  }, [allLeads, filter, search]);

  async function handleFindMore() {
    setFinding(true);
    setFindError(null);
    try {
      const fresh = await api.findMoreLeads(allLeads, goal);
      setExtra((prev) => [...prev, ...fresh]);
    } catch (e) {
      setFindError(e instanceof Error ? e.message : "Find more failed");
    } finally {
      setFinding(false);
    }
  }

  function handleClearDraft() {
    setExtra([]);
    setSelectedLeads([]);
    setFindError(null);
  }

  function handleReplaceDiscovery() {
    setExtra([]);
    setSelectedLeads([]);
    setFindError(null);
    leadsQuery.refetch();
  }

  function selectAllActionable() {
    setSelectedLeads(filtered.map((l) => l.id));
  }

  return (
    <div className="flex h-full min-h-0">
      <DiscoveryRail
        goal={goal}
        setGoal={setGoal}
        onFindMore={handleFindMore}
        onReplace={handleReplaceDiscovery}
        onClear={handleClearDraft}
        finding={finding}
        foundCount={allLeads.length}
      />

      <div className="min-w-0 flex-1 overflow-auto p-6">
        <div className="mx-auto flex max-w-5xl flex-col gap-4">
          <div>
            <h1 className="text-lg font-semibold">Lead Discovery</h1>
            <p className="text-sm text-muted-foreground">
              Review, sort and qualify the discovered pool, then hand the actionable set to
              outreach.
            </p>
          </div>

          {/* Funnel header — stats error handled gracefully (just hide funnel) */}
          {statsQuery.data && <DiscoveryFunnel stats={statsQuery.data} />}

          {findError && (
            <div className="rounded-lg border border-warning/40 bg-warning/10 px-4 py-2 text-sm text-warning">
              Couldn't fetch more leads — {findError}
            </div>
          )}

          <FilterTabs
            value={filter}
            onChange={setFilter}
            counts={counts}
            filteredOut={statsQuery.data?.filteredByIcp ?? 0}
          />

          <div className="flex items-center gap-3">
            <div className="relative flex-1">
              <Search className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search…"
                className="pl-8"
              />
            </div>
            <Button variant="outline" size="sm" onClick={() => setSelectedLeads([])}>
              <SquareDashed className="h-4 w-4" /> Select
            </Button>
            <Button variant="outline" size="sm" onClick={selectAllActionable}>
              <CheckSquare className="h-4 w-4" /> Select all actionable ({filtered.length})
            </Button>
          </div>

          {leadsQuery.isError ? (
            <div className="rounded-lg border border-border bg-muted/30 px-4 py-10 text-center text-sm text-muted-foreground">
              Couldn't load leads —{" "}
              <button
                onClick={() => leadsQuery.refetch()}
                className="inline-flex items-center gap-1 text-info underline-offset-2 hover:underline"
              >
                <RefreshCw className="h-3 w-3" /> retry
              </button>
            </div>
          ) : leadsQuery.isLoading ? (
            <div className="rounded-lg border border-border bg-card py-16 text-center text-sm text-muted-foreground">
              Loading discovered leads…
            </div>
          ) : (
            <LeadTable leads={filtered} onRowClick={setActiveLead} />
          )}
        </div>
      </div>

      {/* Bulk action float */}
      <div className="pointer-events-none fixed inset-x-0 bottom-6 z-30 flex justify-center">
        <BulkActionBar leads={allLeads} />
      </div>

      {/* Lead detail drawer — rendered outside the scroll container so it can be truly fixed */}
      <LeadDetailDrawer lead={activeLead} onClose={() => setActiveLead(null)} />
    </div>
  );
}
