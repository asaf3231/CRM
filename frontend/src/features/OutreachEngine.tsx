import { useQuery } from "@tanstack/react-query";
import { RefreshCw, Linkedin, Mail, Workflow } from "lucide-react";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { MetricCards, type Metric } from "@/components/shell/MetricCards";
import { CohortTimeline } from "@/components/outreach/CohortTimeline";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

/* ── Consistent inline error card (same pattern as OutreachCenter) ───────────── */
function ErrorCard({
  label,
  onRetry,
  className,
}: {
  label: string;
  onRetry: () => void;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex items-center justify-center rounded-lg border border-border bg-muted/30 text-sm text-muted-foreground",
        className
      )}
    >
      Couldn't load {label} —{" "}
      <button
        onClick={onRetry}
        className="ml-1 inline-flex items-center gap-1 text-info underline-offset-2 hover:underline"
      >
        <RefreshCw className="h-3 w-3" /> retry
      </button>
    </div>
  );
}

/* ── Channel summary card (LinkedIn · Email · Orchestrated) ───────────────────── */
function ChannelCard() {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-semibold">Channels</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-2 text-sm">
        <div className="flex items-center gap-2">
          <Linkedin className="h-4 w-4 text-info" /> LinkedIn
          <span className="ml-auto text-xs text-muted-foreground">Phantombuster</span>
        </div>
        <div className="flex items-center gap-2">
          <Mail className="h-4 w-4 text-accent-foreground" /> Email
          <span className="ml-auto text-xs text-muted-foreground">Bound CU</span>
        </div>
        <div className="flex items-center gap-2">
          <Workflow className="h-4 w-4 text-muted-foreground" /> Orchestrated
          <span className="ml-auto text-xs text-muted-foreground">A/B sequenced</span>
        </div>
      </CardContent>
    </Card>
  );
}

export function OutreachEngine() {
  const statsQuery   = useQuery({ queryKey: ["outreachStats"], queryFn: api.getOutreachStats });
  const cohortsQuery = useQuery({ queryKey: ["cohorts"],       queryFn: api.getCohorts });

  const refreshing = cohortsQuery.isFetching || statsQuery.isFetching;

  function refresh() {
    statsQuery.refetch();
    cohortsQuery.refetch();
  }

  const metrics: Metric[] = statsQuery.data
    ? [
        { label: "Cohorts", value: statsQuery.data.totalCohorts },
        { label: "Companies", value: statsQuery.data.totalCompanies },
        {
          label: "In Campaign",
          value: statsQuery.data.inCampaign,
          sub: `across ${statsQuery.data.inCampaignCohorts} cohorts`,
        },
        { label: "Replied", value: statsQuery.data.replies },
        { label: "Reply Rate", value: `${(statsQuery.data.replyRate * 100).toFixed(1)}%` },
      ]
    : [];

  return (
    <div className="overflow-auto p-6">
      <div className="mx-auto flex max-w-6xl flex-col gap-5">

        {/* ── Header ──────────────────────────────────────────────────── */}
        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="text-lg font-semibold">Outreach Engine</h1>
            <p className="text-sm text-muted-foreground">
              Engage at scale — LinkedIn · Email · Orchestrated
            </p>
          </div>
          <Button variant="outline" onClick={refresh} disabled={refreshing}>
            <RefreshCw className={cn("h-4 w-4", refreshing && "animate-spin")} />
            {refreshing ? "Refreshing…" : "Refresh"}
          </Button>
        </div>

        {/* ── Metric cards ────────────────────────────────────────────── */}
        {statsQuery.isLoading ? (
          <div className="h-[72px] animate-pulse rounded-lg bg-muted" />
        ) : statsQuery.isError ? (
          <ErrorCard label="outreach stats" onRetry={() => statsQuery.refetch()} />
        ) : (
          <MetricCards metrics={metrics} />
        )}

        {/* ── Main: cohort sequences (wired) + side column ────────────── */}
        <div className="grid grid-cols-3 gap-4">
          <div className="col-span-2">
            {cohortsQuery.isLoading ? (
              <div className="h-[360px] animate-pulse rounded-lg bg-muted" />
            ) : cohortsQuery.isError ? (
              <ErrorCard label="cohorts" onRetry={() => cohortsQuery.refetch()} className="h-[360px]" />
            ) : (
              <CohortTimeline cohorts={cohortsQuery.data ?? []} />
            )}
          </div>

          <div className="col-span-1 flex flex-col gap-4">
            <ChannelCard />
          </div>
        </div>

      </div>
    </div>
  );
}
