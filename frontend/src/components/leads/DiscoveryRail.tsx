import {
  ArrowRight,
  ChevronDown,
  Crosshair,
  Plus,
  RefreshCw,
  Save,
  Trash2,
} from "lucide-react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

interface DiscoveryRailProps {
  goal: number;
  setGoal: (n: number) => void;
  onFindMore: () => void;
  onReplace: () => void;
  onClear: () => void;
  finding: boolean;
  foundCount: number;
}

/** Left config rail — the looped discovery controls (SLED pattern; parity: Images/…9.04.11). */
export function DiscoveryRail({ goal, setGoal, onFindMore, onReplace, onClear, finding, foundCount }: DiscoveryRailProps) {
  const navigate = useNavigate();
  return (
    <aside className="flex w-80 shrink-0 flex-col gap-4 overflow-auto border-r border-border bg-card/40 p-4">
      <div className="flex items-start justify-between gap-2">
        <div>
          <h2 className="text-sm font-semibold">Lead Discovery</h2>
          <p className="mt-0.5 text-xs leading-snug text-muted-foreground">
            Discover, analyze, and score companies before handing the list off to enrichment.
          </p>
        </div>
        <button
          onClick={() => navigate("/swarm")}
          className="inline-flex shrink-0 items-center gap-1 text-xs font-medium text-muted-foreground hover:text-foreground"
        >
          Enrichment <ArrowRight className="h-3 w-3" />
        </button>
      </div>

      <div className="rounded-lg border border-border bg-card p-3">
        <div className="flex items-center justify-between">
          <span className="inline-flex items-center gap-1.5 text-sm font-semibold">
            <Crosshair className="h-3.5 w-3.5 text-muted-foreground" /> ICP discovery
          </span>
          <button
            onClick={() => navigate("/search")}
            className="inline-flex items-center gap-1 text-[11px] text-muted-foreground hover:text-foreground"
          >
            Other ways to add leads <ChevronDown className="h-3 w-3" />
          </button>
        </div>
        <p className="mt-1.5 text-xs leading-snug text-muted-foreground">
          Pick an ICP, set a target lead count, then tune discovery only if you need tighter
          control.
        </p>
      </div>

      <Section title="ICP angle">
        <div className="rounded-md border border-border bg-card px-3 py-2 text-sm">
          <div className="font-medium">Venue Sourcing &amp; Site Selection</div>
          <p className="mt-1 text-xs text-muted-foreground">
            Balanced threshold · Nationwide · Gov-experience
          </p>
        </div>
      </Section>

      <Section title="Saved discovery draft">
        <button
          onClick={onFindMore}
          className="flex w-full items-center justify-between rounded-md border border-dashed border-border px-3 py-2 text-left text-xs text-muted-foreground hover:bg-muted"
        >
          <span className="inline-flex items-center gap-1.5">
            <Save className="h-3.5 w-3.5" /> Restore saved draft
          </span>
          <span>{foundCount} found</span>
        </button>
      </Section>

      <Section title="Discovery goal">
        <div className="flex items-center gap-2">
          <Input
            type="number"
            value={goal}
            min={10}
            step={10}
            onChange={(e) => setGoal(Number(e.target.value) || 0)}
            className="h-9 w-24"
          />
          <span className="text-xs text-muted-foreground">target companies</span>
        </div>
        <p className="mt-1.5 text-[11px] leading-snug text-muted-foreground">
          Set the maximum number of companies this discovery loop should research.
        </p>
      </Section>

      <div className="mt-auto flex flex-col gap-2 pt-2">
        <Button onClick={onFindMore} disabled={finding} className="w-full">
          {finding ? (
            <>
              <RefreshCw className="h-4 w-4 animate-spin" /> Searching…
            </>
          ) : (
            <>
              <Plus className="h-4 w-4" /> Find {goal} More
            </>
          )}
        </Button>
        <p className="text-center text-[11px] text-muted-foreground">{goal} recommended</p>
        <Button variant="outline" className="w-full" onClick={onReplace} disabled={finding}>
          <RefreshCw className="h-4 w-4" /> Replace with New Discovery
        </Button>
        <Button variant="destructive" className="w-full" onClick={onClear}>
          <Trash2 className="h-4 w-4" /> Clear Saved Draft
        </Button>
      </div>
    </aside>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <div className="mb-1.5 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
        {title}
      </div>
      {children}
    </div>
  );
}
