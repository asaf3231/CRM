import { Badge } from "@/components/ui/badge";
import type { FitGrade, GovBand, LeadKind } from "@/types";

/** Fit pill: "Strong Fit" (green) / "Medium Fit" (amber) / "Weak Fit" (muted). */
export function FitBadge({ fit }: { fit: FitGrade }) {
  const variant = fit === "Strong" ? "success" : fit === "Medium" ? "warning" : "muted";
  return <Badge variant={variant}>{fit} Fit</Badge>;
}

/** Gov band: "Light Gov" (blue outline) / "Heavy Gov" (amber outline) / "No Gov" (muted). */
export function GovBadge({ gov }: { gov: GovBand }) {
  if (gov === "No Gov") return <Badge variant="muted">No Gov</Badge>;
  const cls =
    gov === "Heavy Gov"
      ? "border-warning/40 bg-warning/10 text-warning"
      : "border-info/40 bg-info/10 text-info";
  return <Badge variant="outline" className={cls}>{gov}</Badge>;
}

/** Lead origin: "Existing" (green outline) / "New" (slate outline). */
export function LeadKindBadge({ kind }: { kind: LeadKind }) {
  const cls =
    kind === "Existing"
      ? "border-success/40 bg-success/8 text-success"
      : "border-border text-muted-foreground";
  return <Badge variant="outline" className={cls}>{kind}</Badge>;
}

/** Unified score — rendered in the brand violet, as in the reference table. */
export function ScoreCell({ score }: { score: number }) {
  return <span className="font-semibold tabular-nums text-violet-600">{score}</span>;
}
