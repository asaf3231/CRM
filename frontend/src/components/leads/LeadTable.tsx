import { useMemo, useState } from "react";
import { ArrowUpDown, ArrowUp, ArrowDown, ExternalLink } from "lucide-react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Checkbox } from "@/components/ui/checkbox";
import { cn } from "@/lib/utils";
import type { Lead } from "@/types";
import { useGtmStore } from "@/store/useGtmStore";
import { FitBadge, GovBadge, LeadKindBadge, ScoreCell } from "./StatusBadges";

type SortKey = "company" | "score" | "fit" | "gov" | "lead";
type SortDir = "asc" | "desc";

const FIT_RANK = { Strong: 3, Medium: 2, Weak: 1 } as const;
const GOV_RANK = { "Heavy Gov": 3, "Light Gov": 2, "No Gov": 1 } as const;
const LEAD_RANK = { Existing: 2, New: 1 } as const;

const ANGLE_TIER_STYLE: Record<number, string> = {
  1: "bg-primary/10 text-primary",
  2: "bg-info/10 text-info",
  3: "bg-muted text-muted-foreground",
};

/** Real RAG-matched solicitation-angle tier chip (C14). Tier 4 / absent → em dash. */
function AngleTierBadge({ tier }: { tier?: number | null }) {
  if (!tier || tier === 4) return <span className="text-xs text-muted-foreground">—</span>;
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium",
        ANGLE_TIER_STYLE[tier] ?? "bg-muted text-muted-foreground"
      )}
    >
      Tier {tier}
    </span>
  );
}

export function LeadTable({
  leads,
  onRowClick,
}: {
  leads: Lead[];
  onRowClick?: (lead: Lead) => void;
}) {
  const [sortKey, setSortKey] = useState<SortKey>("score");
  const [sortDir, setSortDir] = useState<SortDir>("desc");
  const { selectedLeadIds, toggleLead, setSelectedLeads } = useGtmStore();

  const sorted = useMemo(() => {
    const arr = [...leads];
    arr.sort((a, b) => {
      let cmp = 0;
      switch (sortKey) {
        case "company":
          cmp = a.company.localeCompare(b.company);
          break;
        case "score":
          cmp = a.score - b.score;
          break;
        case "fit":
          cmp = FIT_RANK[a.fit] - FIT_RANK[b.fit];
          break;
        case "gov":
          cmp = GOV_RANK[a.gov] - GOV_RANK[b.gov];
          break;
        case "lead":
          cmp = LEAD_RANK[a.kind] - LEAD_RANK[b.kind];
          break;
      }
      return sortDir === "asc" ? cmp : -cmp;
    });
    return arr;
  }, [leads, sortKey, sortDir]);

  function sort(key: SortKey) {
    if (key === sortKey) setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    else {
      setSortKey(key);
      setSortDir(key === "company" ? "asc" : "desc");
    }
  }

  const allSelected = leads.length > 0 && selectedLeadIds.length === leads.length;
  const someSelected = selectedLeadIds.length > 0 && !allSelected;

  function toggleAll() {
    setSelectedLeads(allSelected ? [] : leads.map((l) => l.id));
  }

  return (
    <div className="rounded-lg border border-border bg-card">
      <Table>
        <TableHeader>
          <TableRow className="hover:bg-transparent">
            <TableHead className="w-10 pl-4">
              <Checkbox
                checked={allSelected ? true : someSelected ? "indeterminate" : false}
                onCheckedChange={toggleAll}
                aria-label="Select all"
              />
            </TableHead>
            <SortHead label="Company" active={sortKey === "company"} dir={sortDir} onClick={() => sort("company")} />
            <SortHead label="Score" active={sortKey === "score"} dir={sortDir} onClick={() => sort("score")} />
            <SortHead label="Fit" active={sortKey === "fit"} dir={sortDir} onClick={() => sort("fit")} />
            <SortHead label="Gov" active={sortKey === "gov"} dir={sortDir} onClick={() => sort("gov")} />
            <SortHead label="Lead" active={sortKey === "lead"} dir={sortDir} onClick={() => sort("lead")} />
            <TableHead className="text-xs font-medium text-muted-foreground">Angle</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {sorted.map((lead) => {
            const checked = selectedLeadIds.includes(lead.id);
            return (
              <TableRow
                key={lead.id}
                data-state={checked ? "selected" : undefined}
                className={onRowClick ? "cursor-pointer" : undefined}
                onClick={() => onRowClick?.(lead)}
              >
                <TableCell
                  className="pl-4"
                  onClick={(e) => e.stopPropagation()}
                >
                  <Checkbox
                    checked={checked}
                    onCheckedChange={() => toggleLead(lead.id)}
                    className="rounded-full"
                    aria-label={`Select ${lead.company}`}
                  />
                </TableCell>
                <TableCell>
                  <div className="font-medium text-foreground">{lead.company}</div>
                  <a
                    href={`https://${lead.domain}`}
                    target="_blank"
                    rel="noreferrer"
                    onClick={(e) => e.stopPropagation()}
                    className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-info hover:underline"
                  >
                    {lead.domain}
                    <ExternalLink className="h-3 w-3" />
                  </a>
                </TableCell>
                <TableCell>
                  <ScoreCell score={lead.score} />
                </TableCell>
                <TableCell>
                  <FitBadge fit={lead.fit} />
                </TableCell>
                <TableCell>
                  <GovBadge gov={lead.gov} />
                </TableCell>
                <TableCell>
                  <LeadKindBadge kind={lead.kind} />
                </TableCell>
                <TableCell>
                  <AngleTierBadge tier={lead.angleTier} />
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
      {leads.length === 0 && (
        <div className="py-12 text-center text-sm text-muted-foreground">No leads match this filter.</div>
      )}
    </div>
  );
}

function SortHead({
  label,
  active,
  dir,
  onClick,
  align = "left",
}: {
  label: string;
  active: boolean;
  dir: SortDir;
  onClick: () => void;
  align?: "left" | "right";
}) {
  const Icon = !active ? ArrowUpDown : dir === "asc" ? ArrowUp : ArrowDown;
  return (
    <TableHead>
      <button
        onClick={onClick}
        className={cn(
          "inline-flex items-center gap-1 hover:text-foreground",
          active && "text-foreground",
          align === "right" && "flex-row-reverse"
        )}
      >
        {label}
        <Icon className="h-3 w-3" />
      </button>
    </TableHead>
  );
}
