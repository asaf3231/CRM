import { Check, ArrowRight } from "lucide-react";
import { fmtInt } from "@/lib/utils";
import type { LeadDiscoveryStats } from "@/types";

/**
 * The "Discovery complete" funnel header (parity: Images/…9.04.11).
 * A soft-green card framing the discovery run as a funnel —
 * Goal → Discovered (−filtered by ICP) → Retained (−below floor) → Above floor —
 * followed by the retained-set breakdown line with fit chips.
 */
export function DiscoveryFunnel({ stats }: { stats: LeadDiscoveryStats }) {
  return (
    <section className="rounded-xl border border-success/25 bg-success/[0.05] px-5 py-4">
      <div className="flex items-center gap-1.5 text-sm font-semibold text-success">
        <Check className="h-4 w-4" strokeWidth={3} />
        Discovery complete
        <span className="font-normal text-muted-foreground">· {stats.strictness}</span>
      </div>

      <div className="mt-3 flex flex-wrap items-end gap-x-1 gap-y-3">
        <Node label="Goal" value={stats.goal} sub="target" />
        <Connector />
        <Node label="Discovered" value={stats.discovered} sub="found" />
        <Connector delta={stats.filteredByIcp} deltaLabel="filtered by ICP" />
        <Node label="Retained" value={stats.retained} sub="in table" />
        <Connector delta={stats.belowFloor} deltaLabel="below floor" />
        <Node label="Above floor" value={stats.aboveFloor} sub="new + above" emphasis />
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-x-2 gap-y-1 border-t border-success/15 pt-3 text-xs text-muted-foreground">
        <span>
          Of <span className="font-semibold text-foreground">{stats.retained}</span> retained:{" "}
          <span className="font-medium text-foreground">{stats.newCount} new</span> ·{" "}
          <span className="font-medium text-foreground">{stats.existingCount} existing</span>
        </span>
        <Chip className="bg-success/12 text-success">{stats.strong} Strong</Chip>
        <Chip className="bg-warning/14 text-warning">{stats.review} Review</Chip>
        <Chip className="bg-destructive/12 text-destructive">{stats.weak} Weak</Chip>
      </div>
      <p className="mt-1 text-xs text-muted-foreground">
        {stats.alreadyInCrm} already in CRM — toggle the “Existing” chip to include
      </p>
    </section>
  );
}

function Node({
  label,
  value,
  sub,
  emphasis,
}: {
  label: string;
  value: number;
  sub: string;
  emphasis?: boolean;
}) {
  return (
    <div className="min-w-[64px] px-2">
      <div className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
        {label}
      </div>
      <div
        className={`mt-0.5 text-2xl font-semibold tabular-nums leading-none ${
          emphasis ? "text-success" : "text-foreground"
        }`}
      >
        {fmtInt(value)}
      </div>
      <div className="mt-1 text-[10px] text-muted-foreground">{sub}</div>
    </div>
  );
}

function Connector({ delta, deltaLabel }: { delta?: number; deltaLabel?: string }) {
  return (
    <div className="flex min-w-[56px] flex-col items-center justify-center self-center px-1 pb-3">
      {delta != null && (
        <span className="text-[11px] font-semibold tabular-nums text-destructive">−{delta}</span>
      )}
      <ArrowRight className="h-3.5 w-3.5 text-muted-foreground" />
      {deltaLabel && <span className="text-[9px] text-muted-foreground">{deltaLabel}</span>}
    </div>
  );
}

function Chip({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <span className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${className}`}>
      {children}
    </span>
  );
}
