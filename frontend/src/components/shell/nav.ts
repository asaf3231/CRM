import {
  Crosshair,
  Telescope,
  Workflow,
  Table2,
  Send,
  BarChart3,
  type LucideIcon,
} from "lucide-react";

/** The 6-layer pipeline — the spine of the product and its primary navigation. */
export interface NavLayer {
  index: number;
  path: string;
  label: string;
  caption: string; // the right-aligned slide caption
  icon: LucideIcon;
}

export const NAV_LAYERS: NavLayer[] = [
  { index: 1, path: "/icp", label: "ICP Builder", caption: "Define who", icon: Crosshair },
  { index: 2, path: "/search", label: "Search & Explore", caption: "Find opportunity", icon: Telescope },
  { index: 3, path: "/swarm", label: "Leads Swarm", caption: "Analyze & enrich", icon: Workflow },
  { index: 4, path: "/leads", label: "Leads Dashboard", caption: "Workspace & exports", icon: Table2 },
  { index: 5, path: "/outreach", label: "Outreach Engine", caption: "LinkedIn · Email · Orchestrated", icon: Send },
  { index: 6, path: "/center", label: "Outreach Center", caption: "Unified analytics", icon: BarChart3 },
];
