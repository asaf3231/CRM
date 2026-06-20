/*
 * LeadDetailDrawer — right-side workspace sheet for a single lead.
 * Opens from LeadsDashboard when a row is clicked.
 * Fetches api.getLeadDetail(lead.id) and renders the full workspace.
 */
import { ExternalLink, Presentation, Download, Send, Loader2 } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { api } from "@/lib/api";
import type { Lead } from "@/types";
import { cn } from "@/lib/utils";
import { exportLeadsCsv, downloadText } from "@/lib/exportCsv";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
  SheetBody,
  SheetFooter,
} from "@/components/ui/sheet";
import { FitBadge, GovBadge, LeadKindBadge, ScoreCell } from "./StatusBadges";

/* ── Tier badge ───────────────────────────────────────────────────────────── */
const TIER_STYLE: Record<number, string> = {
  1: "bg-success/12 text-success border-success/30",
  2: "bg-info/12 text-info border-info/30",
  3: "bg-warning/12 text-warning border-warning/30",
  4: "border-border text-muted-foreground",
};

function TierBadge({ tier }: { tier: 1 | 2 | 3 | 4 }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium",
        TIER_STYLE[tier]
      )}
    >
      Tier {tier}
    </span>
  );
}

/* ── Section heading ─────────────────────────────────────────────────────── */
function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <h3 className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
      {children}
    </h3>
  );
}

/* ── Main component ──────────────────────────────────────────────────────── */
interface Props {
  lead: Lead | null;
  onClose: () => void;
}

export function LeadDetailDrawer({ lead, onClose }: Props) {
  const open = lead !== null;
  const navigate = useNavigate();

  const detailQuery = useQuery({
    queryKey: ["leadDetail", lead?.id],
    queryFn: () => api.getLeadDetail(lead!.id),
    enabled: open,
    staleTime: 1000 * 60 * 5, // 5 min — don't refetch while drawer is open
  });

  const detail = detailQuery.data;

  return (
    <Sheet open={open} onOpenChange={(v) => !v && onClose()}>
      <SheetContent side="right">
        {/* ── Header ─────────────────────────────────────────────────────── */}
        <SheetHeader>
          {lead ? (
            <>
              <SheetTitle>{lead.company}</SheetTitle>
              <SheetDescription asChild>
                <div className="flex flex-wrap items-center gap-2">
                  <a
                    href={`https://${lead.domain}`}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-info hover:underline"
                  >
                    {lead.domain}
                    <ExternalLink className="h-3 w-3" />
                  </a>
                  <span className="text-border">·</span>
                  <ScoreCell score={lead.score} />
                  <FitBadge fit={lead.fit} />
                  <GovBadge gov={lead.gov} />
                  <LeadKindBadge kind={lead.kind} />
                </div>
              </SheetDescription>
            </>
          ) : (
            <SheetTitle>Lead Workspace</SheetTitle>
          )}
        </SheetHeader>

        {/* ── Body ───────────────────────────────────────────────────────── */}
        <SheetBody className="flex flex-col gap-6">
          {detailQuery.isLoading && (
            <div className="flex items-center justify-center py-16 text-muted-foreground">
              <Loader2 className="h-5 w-5 animate-spin" />
            </div>
          )}

          {detailQuery.isError && (
            <div className="rounded-lg border border-border bg-muted/30 px-4 py-6 text-center text-sm text-muted-foreground">
              Couldn't load lead details —{" "}
              <button
                onClick={() => detailQuery.refetch()}
                className="text-info underline-offset-2 hover:underline"
              >
                retry
              </button>
            </div>
          )}

          {detail && (
            <>
              {/* ICP tags */}
              <div>
                <SectionLabel>ICP Tags</SectionLabel>
                <div className="flex flex-wrap gap-1.5">
                  {detail.tags.length > 0 ? (
                    detail.tags.map((tag) => (
                      <Badge key={tag} variant="tag" className="text-xs">
                        {tag}
                      </Badge>
                    ))
                  ) : (
                    <span className="text-xs text-muted-foreground">No tags matched</span>
                  )}
                </div>
              </div>

              {/* Win probability */}
              {detail.winProb !== undefined && (
                <div>
                  <SectionLabel>Win Probability</SectionLabel>
                  <div className="flex items-center gap-3">
                    <div className="h-2 flex-1 overflow-hidden rounded-full bg-muted">
                      <div
                        className="h-full rounded-full bg-violet-500 transition-all"
                        style={{ width: `${Math.round(detail.winProb * 100)}%` }}
                      />
                    </div>
                    <span className="min-w-[3ch] text-right text-sm font-semibold tabular-nums text-violet-600">
                      {Math.round(detail.winProb * 100)}%
                    </span>
                  </div>
                </div>
              )}

              {/* Matched solicitation angle */}
              <div>
                <SectionLabel>Matched Angle</SectionLabel>
                <div className="rounded-lg border border-border bg-card p-3">
                  <div className="mb-1 flex items-center gap-2">
                    <span className="text-sm font-medium">{detail.angle.title}</span>
                    <TierBadge tier={detail.angle.tier} />
                  </div>
                  <p className="text-xs text-muted-foreground leading-relaxed">
                    {detail.angle.rationale}
                  </p>
                </div>
              </div>

              {/* Contacts */}
              <div>
                <SectionLabel>Key Contacts</SectionLabel>
                <div className="flex flex-col divide-y divide-border rounded-lg border border-border">
                  {detail.contacts.map((c) => (
                    <div
                      key={c.email}
                      className="flex items-center gap-3 px-3 py-2.5"
                    >
                      <div className="flex h-7 w-7 items-center justify-center rounded-full bg-accent text-[11px] font-semibold text-accent-foreground shrink-0">
                        {c.name.charAt(0)}
                      </div>
                      <div className="min-w-0 flex-1">
                        <div className="truncate text-sm font-medium">{c.name}</div>
                        <div className="truncate text-xs text-muted-foreground">{c.role}</div>
                      </div>
                      <span className="hidden truncate text-xs text-muted-foreground sm:block">
                        {c.email}
                      </span>
                    </div>
                  ))}
                </div>
                <p className="mt-1.5 text-[11px] text-muted-foreground">
                  Revealed via the Policy-4 auth gate
                </p>
              </div>

              {/* Pre-meeting brief */}
              <div>
                <SectionLabel>Pre-meeting Brief</SectionLabel>
                <p className="text-sm text-foreground leading-relaxed">
                  {detail.brief}
                </p>
              </div>
            </>
          )}
        </SheetBody>

        {/* ── Footer actions ──────────────────────────────────────────────── */}
        <SheetFooter>
          <Button
            variant="outline"
            size="sm"
            disabled={!detail || !lead}
            onClick={() =>
              lead &&
              detail &&
              downloadText(
                `${lead.domain}-brief.txt`,
                `${lead.company} (${lead.domain})\nScore ${lead.score} · ${lead.fit} fit · ${lead.gov}\n\n` +
                  `Matched angle: ${detail.angle.title} (Tier ${detail.angle.tier})\n${detail.angle.rationale}\n\n` +
                  `Pre-meeting brief:\n${detail.brief}`
              )
            }
          >
            <Presentation className="h-4 w-4" />
            Generate deck
          </Button>
          <Button
            variant="outline"
            size="sm"
            disabled={!lead}
            onClick={() => lead && exportLeadsCsv([lead], `${lead.domain}.csv`)}
          >
            <Download className="h-4 w-4" />
            Export
          </Button>
          <Button
            size="sm"
            className="ml-auto"
            disabled={!detail}
            onClick={() => {
              onClose();
              navigate("/outreach");
            }}
          >
            <Send className="h-4 w-4" />
            Enroll in cohort
          </Button>
        </SheetFooter>
      </SheetContent>
    </Sheet>
  );
}
