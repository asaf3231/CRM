/*
 * Search & Explore — /search
 * Shows the 3-way discovery fanout pipeline and allows a mock "run" that
 * animates the nodes and streams discovered companies one-by-one.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { Play, Search } from "lucide-react";
import { api } from "@/lib/api";
import type { DiscoveryResult, Lead } from "@/types";
import type { FlowNodeStatus } from "@/components/pipeline/FlowNode";
import { useGtmStore } from "@/store/useGtmStore";
import { FlowNode } from "@/components/pipeline/FlowNode";
import { FlowArrow } from "@/components/pipeline/FlowArrow";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";

/* ─── Node ids for the flow diagram ─────────────────────────────────────── */
type NodeId = "queryGen" | "vectorA" | "vectorB" | "vectorC" | "extractor" | "scorer";

type NodeStatuses = Record<NodeId, FlowNodeStatus>;

const IDLE_STATUSES: NodeStatuses = {
  queryGen: "idle",
  vectorA:  "idle",
  vectorB:  "idle",
  vectorC:  "idle",
  extractor:"idle",
  scorer:   "idle",
};

/* ─── Fit → badge variant ────────────────────────────────────────────────── */
function fitVariant(fit: DiscoveryResult["fit"]): "success" | "warning" | "muted" {
  if (fit === "Strong") return "success";
  if (fit === "Medium") return "warning";
  return "muted";
}

/* ─── Helper: map a DiscoveryResult to a Lead for the cross-screen store ─── */
let _discoverySeq = 9000; // synthetic ids that won't collide with MOCK_LEADS
function toStoreLead(r: DiscoveryResult): Lead {
  return {
    id: `disc-${++_discoverySeq}`,
    company: r.company,
    domain: r.domain,
    score: r.score,
    fit: r.fit,
    gov: "No Gov",
    kind: "New",
    stage: "discovered",
    tags: [],
  };
}

/* ─── Main component ─────────────────────────────────────────────────────── */
export function SearchExplore() {
  const [seed, setSeed]           = useState("corporate travel & meetings");
  const [targetCount, setTargetCount] = useState(15);
  const [running, setRunning]     = useState(false);
  const [runCount, setRunCount]   = useState(0);               // how many runs completed
  const [statuses, setStatuses]   = useState<NodeStatuses>(IDLE_STATUSES);
  const [results, setResults]     = useState<DiscoveryResult[]>([]);
  const [streaming, setStreaming] = useState<DiscoveryResult[]>([]);  // items being streamed in

  const { addDiscoveredLeads } = useGtmStore();

  // Keep ref of all timer handles so we can clear them on unmount.
  const timers = useRef<ReturnType<typeof setTimeout>[]>([]);

  function pushTimer(id: ReturnType<typeof setTimeout>) {
    timers.current.push(id);
  }

  // Cleanup all timers on unmount.
  useEffect(() => {
    return () => {
      timers.current.forEach(clearTimeout);
    };
  }, []);

  const run = useCallback(async () => {
    if (running) return;
    setRunning(true);
    setStreaming([]);

    const nextRun = runCount + 1;

    // ── Phase 1: queryGen running (0ms) ──────────────────────────────────
    setStatuses((s) => ({ ...s, queryGen: "running" }));

    // ── Phase 2: queryGen done + vectors start (700ms) ───────────────────
    pushTimer(setTimeout(() => {
      setStatuses((s) => ({
        ...s,
        queryGen: "done",
        vectorA: "running",
        vectorB: "running",
        vectorC: "running",
      }));
    }, 700));

    // ── Phase 3: vectors done + extractor starts (1600ms) ────────────────
    pushTimer(setTimeout(() => {
      setStatuses((s) => ({
        ...s,
        vectorA: "done",
        vectorB: "done",
        vectorC: "done",
        extractor: "running",
      }));
    }, 1600));

    // ── Phase 4: extractor done + scorer starts (2400ms) ─────────────────
    pushTimer(setTimeout(() => {
      setStatuses((s) => ({ ...s, extractor: "done", scorer: "running" }));
    }, 2400));

    // ── Phase 5: fetch data + begin streaming (2800ms) ───────────────────
    pushTimer(setTimeout(async () => {
      try {
        const batch = await api.runDiscovery(seed, targetCount, nextRun);

        // Dedup against existing results.
        const seen = new Set(results.map((r) => r.domain));
        const fresh = batch.filter((r) => !seen.has(r.domain));

        // Stream items in one-by-one, 220ms apart.
        fresh.forEach((item, i) => {
          pushTimer(setTimeout(() => {
            setStreaming((prev) => {
              const already = prev.some((x) => x.domain === item.domain);
              return already ? prev : [...prev, item];
            });
          }, i * 220));
        });

        // After all items streamed, merge into results + mark scorer done.
        const allDoneAt = fresh.length * 220 + 300;
        pushTimer(setTimeout(() => {
          setResults((prev) => {
            const seenDomains = new Set(prev.map((r) => r.domain));
            const deduped = fresh.filter((r) => !seenDomains.has(r.domain));
            return [...prev, ...deduped];
          });
          // Push the batch into the cross-screen store so LeadsDashboard picks them up.
          addDiscoveredLeads(fresh.map(toStoreLead));
          setStreaming([]);
          setStatuses((s) => ({ ...s, scorer: "done" }));
          setRunCount(nextRun);
          setRunning(false);
        }, allDoneAt));

      } catch {
        // On error, reset to idle.
        setStatuses(IDLE_STATUSES);
        setRunning(false);
      }
    }, 2800));
  }, [running, runCount, results, seed, targetCount, addDiscoveredLeads]);

  // Combined display list: persisted results + currently streaming items
  const seenInResults = new Set(results.map((r) => r.domain));
  const displayList: DiscoveryResult[] = [
    ...results,
    ...streaming.filter((r) => !seenInResults.has(r.domain)),
  ];

  const anyRunDone = runCount > 0;

  return (
    <div className="overflow-auto p-6">
      <div className="mx-auto flex max-w-5xl flex-col gap-6">

        {/* ── Header ─────────────────────────────────────────────────────── */}
        <div>
          <h1 className="text-lg font-semibold">Search &amp; Explore</h1>
          <p className="text-sm text-muted-foreground">
            Generate queries, fan out across three discovery providers, score every hit against the ICP.
          </p>
        </div>

        {/* ── Run controls ───────────────────────────────────────────────── */}
        <Card className="flex flex-wrap items-center gap-3 p-4">
          <div className="relative min-w-[260px] flex-1">
            <Search className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={seed}
              onChange={(e) => setSeed(e.target.value)}
              placeholder="Vertical seed — e.g. corporate travel & meetings"
              className="pl-8"
              disabled={running}
            />
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <label className="text-xs text-muted-foreground whitespace-nowrap">Target queries</label>
            <Input
              type="number"
              value={targetCount}
              onChange={(e) => setTargetCount(Math.max(1, Number(e.target.value)))}
              className="w-16 text-center"
              min={1}
              max={20}
              disabled={running}
            />
          </div>
          <Button onClick={run} disabled={running || !seed.trim()} className="shrink-0">
            <Play className="h-4 w-4" />
            {running ? "Running…" : anyRunDone ? "Run Again" : "Run Discovery"}
          </Button>
        </Card>

        {/* ── Stat chips ─────────────────────────────────────────────────── */}
        <div className="flex flex-wrap gap-2">
          {[
            `${targetCount} queries / run`,
            "3-way discovery",
            "recall to strict_target",
            "hybrid RAG backend",
          ].map((chip) => (
            <Badge key={chip} variant="outline" className="text-xs text-muted-foreground">
              {chip}
            </Badge>
          ))}
        </div>

        {/* ── 3-way fanout flow diagram ───────────────────────────────────── */}
        <div className="overflow-x-auto pb-2">
          <div className="flex min-w-max items-center gap-0">

            {/* Query Generator */}
            <FlowNode
              title="Query Generator"
              subtitle={`Claude Haiku 4.5 · 10–20 queries · adaptive`}
              status={statuses.queryGen}
            />

            {/* Fan-out arrows to 3 vectors */}
            <div className="flex flex-col items-stretch gap-0 self-stretch">
              {/* Top arrow (Vector A) */}
              <div className="flex flex-1 items-start pt-4">
                <FlowArrow dim={statuses.queryGen === "idle"} />
              </div>
              {/* Middle arrow (Vector B) */}
              <div className="flex flex-1 items-center">
                <FlowArrow dim={statuses.queryGen === "idle"} />
              </div>
              {/* Bottom arrow (Vector C) */}
              <div className="flex flex-1 items-end pb-4">
                <FlowArrow dim={statuses.queryGen === "idle"} />
              </div>
            </div>

            {/* Three parallel vector nodes stacked vertically */}
            <div className="flex flex-col gap-3">
              <FlowNode
                title="Claude Web Search"
                subtitle="web_search · web_fetch · grounded"
                status={statuses.vectorA}
                tone="a"
              />
              <FlowNode
                title="SerpAPI + Maps"
                subtitle="organic + place enrichment"
                status={statuses.vectorB}
                tone="b"
              />
              <FlowNode
                title="Tavily Recovery"
                subtitle="fires when &lt; 2 results"
                status={statuses.vectorC}
                tone="c"
              />
            </div>

            {/* Merge arrows from 3 vectors → Lead Extractor */}
            <div className="flex flex-col items-stretch gap-0 self-stretch">
              <div className="flex flex-1 items-start pt-4">
                <FlowArrow dim={statuses.vectorA === "idle" && statuses.vectorB === "idle"} />
              </div>
              <div className="flex flex-1 items-center">
                <FlowArrow dim={statuses.vectorA === "idle" && statuses.vectorB === "idle"} />
              </div>
              <div className="flex flex-1 items-end pb-4">
                <FlowArrow dim={statuses.vectorC === "idle"} />
              </div>
            </div>

            {/* Lead Extractor */}
            <FlowNode
              title="Lead Extractor"
              subtitle="domain dedup · entity extraction"
              status={statuses.extractor}
            />

            <FlowArrow dim={statuses.extractor === "idle"} />

            {/* Unified Scorer */}
            <FlowNode
              title="Unified Scorer"
              subtitle="Claude · gov-exp band · ICP filters"
              status={statuses.scorer}
            />
          </div>
        </div>

        {/* ── Results area ───────────────────────────────────────────────── */}
        <div className="flex flex-col gap-2">
          <h2 className="text-sm font-medium text-muted-foreground">
            Discovered companies
            {displayList.length > 0 && (
              <span className="ml-2 tabular-nums text-foreground">{displayList.length}</span>
            )}
          </h2>

          {displayList.length === 0 ? (
            <div
              className={cn(
                "rounded-lg border border-dashed border-border py-12 text-center text-sm text-muted-foreground",
                running && "border-warning/40 bg-warning/5"
              )}
            >
              {running
                ? "Running discovery…"
                : "Run discovery to stream matched companies into the pool."}
            </div>
          ) : (
            <div className="flex flex-col divide-y divide-border rounded-lg border border-border bg-card">
              {displayList.map((r) => (
                <DiscoveryRow key={r.domain} result={r} />
              ))}
              {/* Streaming spinner row */}
              {running && streaming.length < 10 && statuses.scorer === "running" && (
                <div className="flex items-center gap-2 px-4 py-2">
                  <span className="h-2 w-2 animate-pulse rounded-full bg-warning" />
                  <span className="text-xs text-muted-foreground">Streaming results…</span>
                </div>
              )}
            </div>
          )}
        </div>

      </div>
    </div>
  );
}

/* ─── Row component ──────────────────────────────────────────────────────── */
function DiscoveryRow({ result }: { result: DiscoveryResult }) {
  return (
    <div className="flex items-center gap-3 px-4 py-2.5">
      <div className="min-w-0 flex-1">
        <span className="block truncate text-sm font-medium">{result.company}</span>
        <span className="block truncate font-mono text-xs text-muted-foreground">{result.domain}</span>
      </div>
      <span className="shrink-0 font-mono text-xs font-semibold text-violet-600">
        scored {result.score}
      </span>
      <Badge variant={fitVariant(result.fit)} className="shrink-0">
        {result.fit} Fit
      </Badge>
    </div>
  );
}
