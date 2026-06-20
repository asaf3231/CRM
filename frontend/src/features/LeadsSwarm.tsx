/*
 * Leads Swarm — /swarm
 * Durable-workflow chunk-progress view: 4 enrichment stages run sequentially,
 * each with a progress bar and a live log. A mock "Run Swarm" animates them.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Workflow } from "lucide-react";
import { api } from "@/lib/api";
import type { SwarmStage } from "@/types";
import type { FlowNodeStatus } from "@/components/pipeline/FlowNode";
import { FlowNode } from "@/components/pipeline/FlowNode";
import { FlowArrow } from "@/components/pipeline/FlowArrow";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";

/* ─── Per-stage runtime state ────────────────────────────────────────────── */
interface StageRuntime {
  status: FlowNodeStatus;
  processed: number;   // how many domains processed so far
  pixelActive: string[]; // which pixel chips have been detected (Analyzer only)
}

type RuntimeMap = Record<string, StageRuntime>;

function buildIdleRuntime(stages: SwarmStage[]): RuntimeMap {
  const map: RuntimeMap = {};
  for (const s of stages) {
    map[s.id] = { status: "idle", processed: 0, pixelActive: [] };
  }
  return map;
}

/* ─── Mock log lines per stage ───────────────────────────────────────────── */
const STAGE_LOG_LINES: Record<string, string[]> = {
  analyzer: [
    "Analyzer: bcdme.com — Meta Pixel ✓, GTM ✓",
    "Analyzer: conferencedirect.com — TikTok Pixel ✓, GTM ✓",
    "Analyzer: travelinc.com — Meta Pixel ✓",
    "Analyzer: adtrav.com — GTM ✓",
  ],
  tag_evaluator: [
    "Tag Evaluator: bcdme.com — qualified (5 tags)",
    "Tag Evaluator: conferencedirect.com — qualified (4 tags)",
    "Tag Evaluator: travelinc.com — qualified (3 tags)",
    "Tag Evaluator: egencia.com — not qualified (2 tags)",
  ],
  matcher: [
    "Matcher: bcdme.com → Tier 1",
    "Matcher: conferencedirect.com → Tier 1",
    "Matcher: travelinc.com → Tier 2",
    "Matcher: adtrav.com → Tier 2",
  ],
  expander: [
    "Expander: bcdme.com — +3 contacts, win-prob 0.62",
    "Expander: conferencedirect.com — +2 contacts, win-prob 0.58",
    "Expander: travelinc.com — +1 contact, win-prob 0.55",
  ],
};

/* ─── Pixel chips for the Analyzer stage ────────────────────────────────── */
const PIXEL_CHIPS = ["TikTok Pixel", "Meta Pixel", "GTM"];

/* ─── Main component ─────────────────────────────────────────────────────── */
export function LeadsSwarm() {
  const stagesQuery = useQuery({ queryKey: ["swarmStages"], queryFn: api.getSwarmStages });
  const stages: SwarmStage[] = stagesQuery.data ?? [];

  const [running, setRunning] = useState(false);
  const [hasRun, setHasRun] = useState(false);
  const [runtime, setRuntime] = useState<RuntimeMap>({});
  const [log, setLog] = useState<string[]>([]);
  const [overallProgress, setOverallProgress] = useState(0); // 0-100

  // Initialize runtime when stages load.
  useEffect(() => {
    if (stages.length > 0) {
      setRuntime(buildIdleRuntime(stages));
    }
  }, [stages.length]); // eslint-disable-line react-hooks/exhaustive-deps

  const timers = useRef<ReturnType<typeof setTimeout>[]>([]);

  function pushTimer(id: ReturnType<typeof setTimeout>) {
    timers.current.push(id);
  }

  useEffect(() => {
    return () => {
      timers.current.forEach(clearTimeout);
    };
  }, []);

  const appendLog = useCallback((line: string) => {
    setLog((prev) => [...prev, line]);
  }, []);

  const runSwarm = useCallback(() => {
    if (running || stages.length === 0) return;
    setRunning(true);
    setHasRun(true);
    setLog([]);
    setOverallProgress(0);
    setRuntime(buildIdleRuntime(stages));

    // Each stage gets ~800ms of "running" time, then transitions to done.
    // Stages run sequentially. We also tick the overall progress bar.
    const STAGE_DURATION = 850;   // ms per stage
    const LOG_INTERVAL   = 180;   // ms between log lines per stage
    const stageCount     = stages.length;

    stages.forEach((stage, stageIdx) => {
      const stageStart = stageIdx * (STAGE_DURATION + 100);

      // Mark this stage as "running"
      pushTimer(setTimeout(() => {
        setRuntime((prev) => ({
          ...prev,
          [stage.id]: { ...prev[stage.id], status: "running", processed: 0, pixelActive: [] },
        }));

        // Tick progress within the stage
        const tickCount = 8;
        for (let t = 1; t <= tickCount; t++) {
          pushTimer(setTimeout(() => {
            const progress = Math.round((t / tickCount) * stage.targetCount);
            const overallBase = (stageIdx / stageCount) * 100;
            const overallStep = ((stageIdx + t / tickCount) / stageCount) * 100;
            setRuntime((prev) => ({
              ...prev,
              [stage.id]: { ...prev[stage.id], processed: progress },
            }));
            setOverallProgress(Math.round(Math.max(overallBase, overallStep)));

            // For the Analyzer, progressively reveal pixel chips.
            if (stage.id === "analyzer" && stage.pixelChips) {
              const chipsToReveal = PIXEL_CHIPS.slice(0, Math.ceil((t / tickCount) * PIXEL_CHIPS.length));
              setRuntime((prev) => ({
                ...prev,
                [stage.id]: { ...prev[stage.id], pixelActive: chipsToReveal },
              }));
            }
          }, (t / tickCount) * STAGE_DURATION));
        }

        // Stream log lines during the stage
        const logLines = STAGE_LOG_LINES[stage.id] ?? [];
        logLines.forEach((line, li) => {
          pushTimer(setTimeout(() => appendLog(line), li * LOG_INTERVAL + 100));
        });

      }, stageStart));

      // Mark this stage as "done"
      pushTimer(setTimeout(() => {
        setRuntime((prev) => ({
          ...prev,
          [stage.id]: {
            ...prev[stage.id],
            status: "done",
            processed: stage.targetCount,
            pixelActive: stage.id === "analyzer" ? [...PIXEL_CHIPS] : (prev[stage.id]?.pixelActive ?? []),
          },
        }));
      }, stageStart + STAGE_DURATION));
    });

    // After all stages done
    const totalDuration = stageCount * (STAGE_DURATION + 100) + 200;
    pushTimer(setTimeout(() => {
      setOverallProgress(100);
      setRunning(false);
    }, totalDuration));

  }, [running, stages, appendLog]);

  const totalDomains = stages.reduce((acc, s) => acc + s.targetCount, 0) / (stages.length || 1);

  return (
    <div className="overflow-auto p-6">
      <div className="mx-auto flex max-w-5xl flex-col gap-6">

        {/* ── Header ─────────────────────────────────────────────────────── */}
        <div>
          <h1 className="text-lg font-semibold">Leads Swarm</h1>
          <p className="text-sm text-muted-foreground">
            Durable enrichment workflow — analyze, qualify, match and expand discovered companies in bounded chunks.
          </p>
        </div>

        {/* ── Run bar ────────────────────────────────────────────────────── */}
        <Card className="flex flex-wrap items-center gap-4 p-4">
          <Button onClick={runSwarm} disabled={running || stages.length === 0}>
            <Workflow className="h-4 w-4" />
            {running ? "Running swarm…" : hasRun ? "Re-run Swarm" : "Run Swarm"}
          </Button>

          <div className="flex min-w-0 flex-1 flex-col gap-1">
            <div className="flex items-center justify-between gap-2">
              <span className="text-xs text-muted-foreground">
                Chunk 1 / 2 · {Math.round(totalDomains)} domains · 800s budget
              </span>
              <span className="font-mono text-xs font-semibold text-foreground">
                {overallProgress}%
              </span>
            </div>
            <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
              <div
                className="h-full rounded-full bg-success transition-all duration-300"
                style={{ width: `${overallProgress}%` }}
              />
            </div>
          </div>
        </Card>

        {/* ── Stage cards ────────────────────────────────────────────────── */}
        {stagesQuery.isLoading ? (
          <div className="py-10 text-center text-sm text-muted-foreground">Loading stages…</div>
        ) : (
          <div className="overflow-x-auto pb-2">
            <div className="flex min-w-max items-center gap-0">
              {stages.map((stage, idx) => {
                const rt = runtime[stage.id] ?? { status: "idle" as FlowNodeStatus, processed: 0, pixelActive: [] };
                const pct = stage.targetCount > 0
                  ? Math.round((rt.processed / stage.targetCount) * 100)
                  : 0;

                return (
                  <div key={stage.id} className="flex items-center gap-0">
                    <SwarmStageCard
                      stage={stage}
                      status={rt.status}
                      processed={rt.processed}
                      pct={pct}
                      pixelActive={rt.pixelActive}
                    />
                    {idx < stages.length - 1 && (
                      <FlowArrow dim={rt.status === "idle"} />
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* ── Live swarm log ──────────────────────────────────────────────── */}
        <div className="flex flex-col gap-2">
          <h2 className="text-sm font-medium text-muted-foreground">Swarm log</h2>
          {log.length === 0 ? (
            <div
              className={cn(
                "rounded-lg border border-dashed border-border py-8 text-center text-xs text-muted-foreground",
                running && "border-warning/40 bg-warning/5"
              )}
            >
              {running ? "Swarm starting…" : hasRun ? "Run complete." : "Run the swarm to see live log output."}
            </div>
          ) : (
            <div className="flex flex-col gap-0 rounded-lg border border-border bg-card font-mono text-xs">
              {log.map((line, i) => (
                <div
                  key={i}
                  className="border-b border-border px-4 py-1.5 last:border-0 text-muted-foreground"
                >
                  <span className="text-foreground/80">{line}</span>
                </div>
              ))}
              {running && (
                <div className="flex items-center gap-2 px-4 py-1.5">
                  <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-warning" />
                  <span className="text-muted-foreground">processing…</span>
                </div>
              )}
            </div>
          )}
        </div>

      </div>
    </div>
  );
}

/* ─── SwarmStageCard ─────────────────────────────────────────────────────── */
interface SwarmStageCardProps {
  stage: SwarmStage;
  status: FlowNodeStatus;
  processed: number;
  pct: number;
  pixelActive: string[];
}

function SwarmStageCard({ stage, status, processed, pct, pixelActive }: SwarmStageCardProps) {
  const statusLabel: Record<FlowNodeStatus, string> = {
    idle:    "queued",
    running: "running",
    done:    "done",
  };
  const statusVariant: Record<FlowNodeStatus, "muted" | "warning" | "success"> = {
    idle:    "muted",
    running: "warning",
    done:    "success",
  };

  return (
    <FlowNode
      title={stage.title}
      subtitle={stage.subtitle}
      status={status}
      className="w-52"
    >
      {/* Progress bar */}
      <div className="mt-2 flex flex-col gap-1">
        <div className="flex items-center justify-between">
          <span className="font-mono text-[10px] text-muted-foreground">
            {processed} / {stage.targetCount}
          </span>
          <Badge variant={statusVariant[status]} className="text-[10px]">
            {statusLabel[status]}
          </Badge>
        </div>
        <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
          <div
            className={cn(
              "h-full rounded-full transition-all duration-300",
              status === "done" ? "bg-success" : "bg-warning"
            )}
            style={{ width: `${pct}%` }}
          />
        </div>
      </div>

      {/* Pixel detection chips (Analyzer only) */}
      {stage.pixelChips && (
        <div className="mt-2 flex flex-wrap gap-1">
          {stage.pixelChips.map((chip) => {
            const active = pixelActive.includes(chip);
            return (
              <span
                key={chip}
                className={cn(
                  "inline-flex items-center rounded-full px-1.5 py-0.5 font-mono text-[9px] font-medium transition-all duration-300",
                  active
                    ? "bg-success/15 text-success"
                    : "bg-muted text-muted-foreground opacity-40"
                )}
              >
                {chip}
              </span>
            );
          })}
        </div>
      )}
    </FlowNode>
  );
}
