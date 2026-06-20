import { Outlet } from "react-router-dom";
import { IconRail } from "./IconRail";
import { TopBar } from "./TopBar";

export function AppShell() {
  return (
    <div className="flex h-screen w-full overflow-hidden bg-background">
      <IconRail />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar />
        <main className="min-h-0 flex-1 overflow-auto">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
