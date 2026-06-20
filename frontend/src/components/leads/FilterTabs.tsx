import { Filter } from "lucide-react";
import { cn } from "@/lib/utils";

export type LeadFilter = "All" | "New" | "Existing" | "Above floor";

export const LEAD_FILTERS: LeadFilter[] = ["All", "New", "Existing", "Above floor"];

interface FilterTabsProps {
  value: LeadFilter;
  onChange: (f: LeadFilter) => void;
  counts: Record<LeadFilter, number>;
  filteredOut: number;
}

/** Segmented filter pills with live count badges (parity: Images/…9.04.11). */
export function FilterTabs({ value, onChange, counts, filteredOut }: FilterTabsProps) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      {LEAD_FILTERS.map((f) => {
        const active = f === value;
        return (
          <button
            key={f}
            onClick={() => onChange(f)}
            aria-pressed={active}
            className={cn(
              "inline-flex items-center gap-2 rounded-lg border px-3 py-1.5 text-sm font-medium transition-colors",
              active
                ? "border-primary bg-primary text-primary-foreground"
                : "border-border bg-card text-foreground hover:bg-muted"
            )}
          >
            {f}
            <span
              className={cn(
                "rounded px-1.5 py-0.5 text-[11px] font-semibold tabular-nums",
                active ? "bg-primary-foreground/20" : "bg-muted text-muted-foreground"
              )}
            >
              {counts[f]}
            </span>
          </button>
        );
      })}
      <span className="inline-flex items-center gap-1.5 rounded-lg border border-dashed border-border px-3 py-1.5 text-sm text-muted-foreground">
        <Filter className="h-3.5 w-3.5" />
        {filteredOut} filtered out
      </span>
    </div>
  );
}
