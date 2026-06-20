import { cn, fmtInt } from "@/lib/utils";

export interface Metric {
  label: string;
  value: string | number;
  sub?: string;
  accent?: "default" | "success" | "warning" | "info";
}

const accentDot: Record<NonNullable<Metric["accent"]>, string> = {
  default: "bg-muted-foreground/40",
  success: "bg-success",
  warning: "bg-warning",
  info: "bg-info",
};

export function MetricCards({ metrics }: { metrics: Metric[] }) {
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
      {metrics.map((m) => (
        <div key={m.label} className="rounded-lg border border-border bg-card px-4 py-3">
          <div className="flex items-center gap-1.5">
            <span className={cn("h-1.5 w-1.5 rounded-full", accentDot[m.accent ?? "default"])} />
            <span className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
              {m.label}
            </span>
          </div>
          <div className="mt-1.5 text-2xl font-semibold tabular-nums">
            {typeof m.value === "number" ? fmtInt(m.value) : m.value}
          </div>
          {m.sub && <div className="mt-0.5 text-xs text-muted-foreground">{m.sub}</div>}
        </div>
      ))}
    </div>
  );
}
