import { X, Plus } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

interface TagChipProps {
  label: string;
  /** "remove" shows ×; "add" shows +. Default "remove". */
  action?: "remove" | "add";
  onAction: () => void;
  className?: string;
}

/**
 * Green pill (Badge `tag` variant) with the text + an action button.
 * Used both as a removable chip in TagInput and as an addable chip in the AI Suggestions rail.
 */
export function TagChip({ label, action = "remove", onAction, className }: TagChipProps) {
  return (
    <Badge
      variant="tag"
      className={cn("inline-flex cursor-default items-center gap-1 py-0.5 pl-2 pr-1", className)}
    >
      <span className="text-xs">{label}</span>
      <button
        type="button"
        onClick={onAction}
        aria-label={action === "remove" ? `Remove ${label}` : `Add ${label}`}
        className="ml-0.5 inline-flex h-4 w-4 items-center justify-center rounded-full opacity-60 hover:opacity-100 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
      >
        {action === "remove" ? <X className="h-2.5 w-2.5" /> : <Plus className="h-2.5 w-2.5" />}
      </button>
    </Badge>
  );
}
