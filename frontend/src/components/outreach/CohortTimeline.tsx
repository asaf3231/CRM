import { Clock, Linkedin, Mail, XCircle, CheckCircle2 } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import type { Cohort, CohortVariantStage } from "@/types";

interface Props {
  cohorts: Cohort[];
}

// ─── Status colour helpers ─────────────────────────────────────────────────────

const statusRing: Record<CohortVariantStage["status"], string> = {
  done:   "border-success  bg-success/10  text-success",
  queued: "border-warning  bg-warning/10  text-warning",
  dead:   "border-destructive bg-destructive/10 text-destructive",
};

function StageNode({ stage }: { stage: CohortVariantStage }) {
  const Icon =
    stage.icon === "clock"    ? Clock :
    stage.icon === "linkedin" ? Linkedin :
                                Mail;

  return (
    <div className="flex flex-col items-center gap-0.5">
      <div
        className={cn(
          "flex h-7 w-7 items-center justify-center rounded-full border-2",
          statusRing[stage.status]
        )}
      >
        <Icon className="h-3 w-3" />
      </div>
      <span className="text-[10px] leading-none text-muted-foreground tabular-nums">
        {stage.count}
      </span>
    </div>
  );
}

function Connector({ label }: { label: string }) {
  return (
    <div className="flex items-center gap-0.5 self-start mt-[10px]">
      <div className="h-px w-3 bg-border" />
      <span className="text-[9px] text-muted-foreground whitespace-nowrap">{label}</span>
      <div className="h-px w-3 bg-border" />
    </div>
  );
}

function OutcomeNode({
  count,
  kind,
}: {
  count: number;
  kind: "dead" | "success";
}) {
  if (kind === "dead") {
    return (
      <div className="flex flex-col items-center gap-0.5">
        <XCircle className="h-5 w-5 text-destructive" />
        <span className="text-[10px] text-muted-foreground tabular-nums">{count}</span>
      </div>
    );
  }
  return (
    <div className="flex flex-col items-center gap-0.5">
      <CheckCircle2 className="h-5 w-5 text-success" />
      <span className="text-[10px] text-muted-foreground tabular-nums">{count}</span>
    </div>
  );
}

// ─── Single variant row ────────────────────────────────────────────────────────

function VariantRow({ variant }: { variant: Cohort["variants"][number] }) {
  return (
    <div className="flex items-start gap-3 py-1.5">
      {/* Left label */}
      <span className="mt-1 w-20 shrink-0 text-right text-[10px] text-muted-foreground">
        {variant.label}
      </span>

      {/* Scrollable stage strip */}
      <div className="flex-1 overflow-x-auto">
        <div className="flex min-w-max items-start gap-0">
          {variant.stages.map((stage, i) => (
            <div key={i} className="flex items-start">
              {stage.gapBefore && <Connector label={stage.gapBefore} />}
              <StageNode stage={stage} />
            </div>
          ))}

          {/* Outcome separator */}
          <div className="mx-2 self-start mt-[10px] h-px w-4 border-t-2 border-dashed border-border" />

          {/* Dead + success outcomes */}
          <div className="flex items-start gap-1.5">
            <OutcomeNode count={variant.outcome.dead} kind="dead" />
            <OutcomeNode count={variant.outcome.success} kind="success" />
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── Single cohort block ───────────────────────────────────────────────────────

function CohortBlock({ cohort }: { cohort: Cohort }) {
  return (
    <div className="mb-4">
      {/* Cohort header */}
      <div className="mb-1 text-xs font-medium text-foreground">
        {cohort.name}{" "}
        <span className="text-muted-foreground">
          — {cohort.enrolledAt} ({cohort.leadsCount} leads)
        </span>
      </div>

      {/* Variant rows */}
      <div className="flex flex-col divide-y divide-border/40">
        {cohort.variants.map((v) => (
          <VariantRow key={v.label} variant={v} />
        ))}
      </div>
    </div>
  );
}

// ─── Panel ─────────────────────────────────────────────────────────────────────

export function CohortTimeline({ cohorts }: Props) {
  return (
    <Card className="flex flex-col">
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between gap-4">
          <CardTitle className="text-sm font-semibold">Cohorts &amp; variants</CardTitle>

          {/* Legend */}
          <div className="flex shrink-0 items-center gap-3 text-[10px] text-muted-foreground">
            <span className="flex items-center gap-1">
              <span className="h-2 w-2 rounded-full bg-success" /> done
            </span>
            <span className="flex items-center gap-1">
              <span className="h-2 w-2 rounded-full bg-warning" /> queued
            </span>
            <span className="flex items-center gap-1">
              <span className="h-2 w-2 rounded-full bg-destructive" /> dead
            </span>
            <span>3 active · 1 closed (hidden)</span>
          </div>
        </div>
      </CardHeader>

      <CardContent className="overflow-x-auto pb-4">
        {cohorts.map((c) => (
          <CohortBlock key={c.id} cohort={c} />
        ))}
      </CardContent>
    </Card>
  );
}
