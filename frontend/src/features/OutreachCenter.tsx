import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { CalendarPlus, RefreshCw } from "lucide-react";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { MetricCards, type Metric } from "@/components/shell/MetricCards";
import { CohortTimeline } from "@/components/outreach/CohortTimeline";
import { EnrollmentCalendar } from "@/components/outreach/EnrollmentCalendar";

/* ── Consistent inline error card ────────────────────────────────────────── */
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

export function OutreachCenter() {
  const navigate = useNavigate();
  const statsQuery       = useQuery({ queryKey: ["outreachStats"],  queryFn: api.getOutreachStats });
  const cohortsQuery     = useQuery({ queryKey: ["cohorts"],        queryFn: api.getCohorts });
  const enrollmentsQuery = useQuery({ queryKey: ["enrollments"],    queryFn: api.getEnrollments });

  // Derive metric cards from stats once loaded
  const metrics: Metric[] = statsQuery.data
    ? [
        { label: "Total Cohorts",    value: statsQuery.data.totalCohorts },
        { label: "Total Companies",  value: statsQuery.data.totalCompanies },
        {
          label: "In Campaign",
          value: statsQuery.data.inCampaign,
          sub: `across ${statsQuery.data.inCampaignCohorts} cohorts`,
        },
        { label: "Replied",     value: statsQuery.data.replies },
        {
          label: "Reply Rate",
          value: `${(statsQuery.data.replyRate * 100).toFixed(1)}%`,
        },
      ]
    : [];

  const activeCampaigns = statsQuery.data
    ? Math.min(statsQuery.data.totalCohorts, 3)
    : 3;
  const totalCohorts = statsQuery.data?.totalCohorts ?? 4;

  return (
    <div className="overflow-auto p-6">
      <div className="mx-auto flex max-w-6xl flex-col gap-5">

        {/* ── Header row ─────────────────────────────────────────────── */}
        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="text-lg font-semibold">Outreach Center</h1>
            <p className="text-sm text-muted-foreground">
              {activeCampaigns} active campaigns / {totalCohorts} total
            </p>
          </div>
          <Button onClick={() => navigate("/outreach")}>
            <CalendarPlus className="h-4 w-4" />
            New Enrollment
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

        {/* ── Cohort timelines + enrollment calendar (backend-served) ──── */}
        <div className="grid grid-cols-3 gap-4">
          <div className="col-span-2">
            {cohortsQuery.isLoading ? (
              <div className="h-[300px] animate-pulse rounded-lg bg-muted" />
            ) : cohortsQuery.isError ? (
              <ErrorCard label="cohorts" onRetry={() => cohortsQuery.refetch()} className="h-[300px]" />
            ) : (
              <CohortTimeline cohorts={cohortsQuery.data ?? []} />
            )}
          </div>
          <div className="col-span-1">
            {enrollmentsQuery.isLoading ? (
              <div className="h-[300px] animate-pulse rounded-lg bg-muted" />
            ) : enrollmentsQuery.isError ? (
              <ErrorCard label="enrollments" onRetry={() => enrollmentsQuery.refetch()} className="h-[300px]" />
            ) : (
              <EnrollmentCalendar enrollments={enrollmentsQuery.data ?? []} />
            )}
          </div>
        </div>

      </div>
    </div>
  );
}
