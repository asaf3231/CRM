import { Send, Tag, Download, X } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { useGtmStore } from "@/store/useGtmStore";
import { exportLeadsCsv } from "@/lib/exportCsv";
import type { Lead } from "@/types";

/** Floating action bar shown when one or more leads are selected. */
export function BulkActionBar({ leads }: { leads: Lead[] }) {
  const { selectedLeadIds, clearSelection } = useGtmStore();
  const navigate = useNavigate();
  if (selectedLeadIds.length === 0) return null;

  const selected = leads.filter((l) => selectedLeadIds.includes(l.id));

  return (
    <div className="pointer-events-auto flex items-center gap-2 rounded-full border border-border bg-card px-3 py-2 shadow-lg">
      <span className="pl-1 text-sm font-medium">
        {selectedLeadIds.length} selected
      </span>
      <span className="mx-1 h-4 w-px bg-border" />
      <Button size="sm" variant="default" onClick={() => navigate("/outreach")}>
        <Send className="h-4 w-4" /> Enroll in cohort
      </Button>
      <Button size="sm" variant="outline" onClick={() => navigate("/icp")}>
        <Tag className="h-4 w-4" /> Add tag
      </Button>
      <Button
        size="sm"
        variant="outline"
        onClick={() => exportLeadsCsv(selected.length ? selected : leads, "selected-leads.csv")}
      >
        <Download className="h-4 w-4" /> Export
      </Button>
      <Button size="icon" variant="ghost" className="h-8 w-8" onClick={clearSelection} aria-label="Clear selection">
        <X className="h-4 w-4" />
      </Button>
    </div>
  );
}
