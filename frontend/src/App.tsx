import { Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "@/components/shell/AppShell";
import { LeadsDashboard } from "@/features/LeadsDashboard";
import { IcpBuilder } from "@/features/IcpBuilder";
import { OutreachCenter } from "@/features/OutreachCenter";
import { OutreachEngine } from "@/features/OutreachEngine";
import { SearchExplore } from "@/features/SearchExplore";
import { LeadsSwarm } from "@/features/LeadsSwarm";

export default function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<Navigate to="/leads" replace />} />
        <Route path="/icp" element={<IcpBuilder />} />
        <Route path="/search" element={<SearchExplore />} />
        <Route path="/swarm" element={<LeadsSwarm />} />
        <Route path="/leads" element={<LeadsDashboard />} />
        <Route path="/outreach" element={<OutreachEngine />} />
        <Route path="/center" element={<OutreachCenter />} />
        <Route path="*" element={<Navigate to="/leads" replace />} />
      </Route>
    </Routes>
  );
}
