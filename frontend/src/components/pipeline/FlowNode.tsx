/*
 * FlowNode — a card-style node for pipeline flow diagrams.
 * Used by both SearchExplore (3-way fanout) and LeadsSwarm (stage cards).
 */
import type { LucideIcon } from "lucide-react";
import { CheckCircle2 } from "lucide-react";
import { cn } from "@/lib/utils";

export type FlowNodeStatus = "idle" | "running" | "done";
export type FlowNodeTone = "default" | "a" | "b" | "c";

export interface FlowNodeProps {
  title: string;
  subtitle?: string;
  status?: FlowNodeStatus;
  icon?: LucideIcon;
  tone?: FlowNodeTone;
  className?: string;
  children?: React.ReactNode;
}

const toneRing: Record<FlowNodeTone, string> = {
  default: "",
  a: "ring-info/40",
  b: "ring-warning/40",
  c: "ring-accent-foreground/30",
};

const toneRunRing: Record<FlowNodeTone, string> = {
  default: "ring-warning/60",
  a: "ring-info/70",
  b: "ring-warning/70",
  c: "ring-accent-foreground/50",
};

const toneDoneRing: Record<FlowNodeTone, string> = {
  default: "ring-success/60",
  a: "ring-success/60",
  b: "ring-success/60",
  c: "ring-success/60",
};

export function FlowNode({
  title,
  subtitle,
  status = "idle",
  icon: Icon,
  tone = "default",
  className,
  children,
}: FlowNodeProps) {
  const isRunning = status === "running";
  const isDone = status === "done";

  return (
    <div
      className={cn(
        "relative flex min-w-[160px] flex-col gap-1 rounded-lg border border-border bg-card px-4 py-3 shadow-sm transition-all duration-300",
        isRunning && ["ring-2", toneRunRing[tone]],
        isDone && ["ring-2", toneDoneRing[tone]],
        !isRunning && !isDone && tone !== "default" && ["ring-1", toneRing[tone]],
        className
      )}
    >
      {/* Running indicator dot */}
      {isRunning && (
        <span className="absolute -right-1 -top-1 flex h-2.5 w-2.5">
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-warning opacity-75" />
          <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-warning" />
        </span>
      )}

      {/* Done checkmark */}
      {isDone && (
        <span className="absolute -right-1 -top-1 flex items-center justify-center rounded-full bg-card">
          <CheckCircle2 className="h-3.5 w-3.5 text-success" />
        </span>
      )}

      <div className="flex items-center gap-2">
        {Icon && <Icon className="h-4 w-4 shrink-0 text-muted-foreground" />}
        <span className="text-sm font-semibold leading-tight">{title}</span>
      </div>

      {subtitle && (
        <span className="font-mono text-xs leading-tight text-muted-foreground">{subtitle}</span>
      )}

      {children}
    </div>
  );
}
