/*
 * FlowArrow — a horizontal connector between FlowNodes.
 * Renders an ArrowRight icon (or a CSS line) with an optional small label.
 */
import { ArrowRight } from "lucide-react";
import { cn } from "@/lib/utils";

export interface FlowArrowProps {
  label?: string;
  className?: string;
  /** If true, dims the arrow (e.g. when the upstream node is idle). */
  dim?: boolean;
}

export function FlowArrow({ label, className, dim = false }: FlowArrowProps) {
  return (
    <div
      className={cn(
        "flex shrink-0 flex-col items-center justify-center gap-0.5 px-1 transition-opacity duration-300",
        dim ? "opacity-30" : "opacity-70",
        className
      )}
    >
      <ArrowRight className="h-4 w-4 text-muted-foreground" />
      {label && (
        <span className="whitespace-nowrap font-mono text-[10px] text-muted-foreground">{label}</span>
      )}
    </div>
  );
}
