import { useLocation } from "react-router-dom";
import { Search, Bell, ChevronDown } from "lucide-react";
import { NAV_LAYERS } from "./nav";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";

export function TopBar() {
  const { pathname } = useLocation();
  const active = NAV_LAYERS.find((l) => pathname.startsWith(l.path)) ?? NAV_LAYERS[0];

  return (
    <header className="flex h-14 shrink-0 items-center justify-between border-b border-border bg-card/60 px-5 backdrop-blur">
      <div className="flex items-center gap-2 text-sm">
        <span className="text-muted-foreground">Layer {active.index}</span>
        <span className="text-muted-foreground">/</span>
        <span className="font-semibold">{active.label}</span>
      </div>
      <div className="flex items-center gap-3">
        <div className="relative hidden md:block">
          <Search className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input placeholder="Search leads, cohorts…" className="h-8 w-64 pl-8" />
        </div>
        <Button variant="ghost" size="icon" className="h-8 w-8">
          <Bell className="h-4 w-4" />
        </Button>
        <button className="flex items-center gap-2 rounded-md py-1 pl-1 pr-2 hover:bg-muted">
          <span className="flex h-7 w-7 items-center justify-center rounded-full bg-primary text-xs font-semibold text-primary-foreground">
            AR
          </span>
          <ChevronDown className="h-4 w-4 text-muted-foreground" />
        </button>
      </div>
    </header>
  );
}
