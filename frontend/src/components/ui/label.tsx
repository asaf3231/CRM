import * as React from "react";
import { cn } from "@/lib/utils";

/*
 * Tiny label wrapper. Matches the muted uppercase style from DiscoveryRail's Section helper.
 */
const Label = React.forwardRef<HTMLLabelElement, React.LabelHTMLAttributes<HTMLLabelElement>>(
  ({ className, ...props }, ref) => (
    <label
      ref={ref}
      className={cn("text-[11px] font-medium uppercase tracking-wide text-muted-foreground", className)}
      {...props}
    />
  )
);
Label.displayName = "Label";

export { Label };
