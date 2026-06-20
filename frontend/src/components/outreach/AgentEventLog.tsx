import { useMemo, useState } from "react";
import { Search } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import type { AgentEvent } from "@/types";

interface Props {
  events: AgentEvent[];
}

/** Format a "YYYY-MM-DD" string into a display label like "MAY 3". */
function formatDivider(dateStr: string): string {
  const d = new Date(dateStr + "T00:00:00");
  return d
    .toLocaleDateString("en-US", { month: "short", day: "numeric" })
    .toUpperCase();
}

export function AgentEventLog({ events }: Props) {
  const [query, setQuery] = useState("");

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return events;
    return events.filter((e) => e.text.toLowerCase().includes(q));
  }, [events, query]);

  // Group by date to render day-dividers
  const grouped: Array<{ date: string; rows: AgentEvent[] }> = useMemo(() => {
    const map = new Map<string, AgentEvent[]>();
    for (const e of filtered) {
      const bucket = map.get(e.date) ?? [];
      bucket.push(e);
      map.set(e.date, bucket);
    }
    return Array.from(map.entries()).map(([date, rows]) => ({ date, rows }));
  }, [filtered]);

  return (
    <Card className="flex flex-col">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-semibold">Agent Event Logs</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-2 pb-4">
        {/* Search */}
        <div className="relative">
          <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search contact, company, action"
            className="h-8 pl-8 text-xs"
          />
        </div>

        {/* Scrollable event list */}
        <div className="max-h-[240px] overflow-auto font-mono text-xs">
          {grouped.length === 0 && (
            <p className="py-4 text-center text-muted-foreground">No events match.</p>
          )}
          {grouped.map(({ date, rows }) => (
            <div key={date}>
              {/* Day divider */}
              <div className="sticky top-0 bg-card py-1 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                {formatDivider(date)}
              </div>
              {rows.map((e) => (
                <div
                  key={e.id}
                  className="flex items-baseline gap-2 py-0.5 hover:bg-muted/40"
                >
                  <span className="shrink-0 text-muted-foreground">{e.time}</span>
                  <span className="text-foreground">{e.text}</span>
                </div>
              ))}
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
