import { NavLink } from "react-router-dom";
import { Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";
import { NAV_LAYERS } from "./nav";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";

/** Dark left icon rail. Each layer is a step in the lead lifecycle. */
export function IconRail() {
  return (
    <TooltipProvider delayDuration={120}>
      <nav className="flex h-screen w-[60px] flex-col items-center gap-1 bg-sidebar py-3 text-sidebar-foreground">
        <div className="mb-3 flex h-9 w-9 items-center justify-center rounded-lg bg-white/10 text-white">
          <Sparkles className="h-[18px] w-[18px]" />
        </div>
        {NAV_LAYERS.map((layer) => {
          const Icon = layer.icon;
          return (
            <Tooltip key={layer.path}>
              <TooltipTrigger asChild>
                <NavLink
                  to={layer.path}
                  className={({ isActive }) =>
                    cn(
                      "flex h-10 w-10 items-center justify-center rounded-lg transition-colors hover:bg-white/10 hover:text-white",
                      isActive
                        ? "bg-white/15 text-white shadow-[inset_2px_0_0_0_hsl(0_0%_100%)]"
                        : "text-sidebar-foreground"
                    )
                  }
                >
                  <Icon className="h-5 w-5" />
                </NavLink>
              </TooltipTrigger>
              <TooltipContent side="right">
                <span className="font-semibold">{layer.label}</span>
                <span className="ml-2 opacity-60">{layer.caption}</span>
              </TooltipContent>
            </Tooltip>
          );
        })}
      </nav>
    </TooltipProvider>
  );
}
