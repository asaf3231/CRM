import { useState } from "react";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import type { ReachPoint } from "@/types";

type Range = "7d" | "30d" | "All";

interface Props {
  data: ReachPoint[];
}

const SERIES = [
  { key: "formBot",  label: "FormBot",    color: "hsl(var(--success))" },
  { key: "connect",  label: "Connect",    color: "hsl(var(--info))" },
  { key: "email1",   label: "Email #1",   color: "#8b5cf6" },
  { key: "email2",   label: "Email #2",   color: "#14b8a6" },
  { key: "liMessage",label: "LI Message", color: "#f97316" },
  { key: "email3",   label: "Email #3",   color: "hsl(var(--destructive))" },
] as const;

export function ReachByStageChart({ data }: Props) {
  const [range, setRange] = useState<Range>("30d");

  // Visual-only range toggle: slice the data for 7d, keep all for 30d/All
  const visible = range === "7d" ? data.slice(-7) : data;

  return (
    <Card className="flex flex-col">
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm font-semibold">Companies reached by stage</CardTitle>
          {/* Segmented range toggle */}
          <div className="inline-flex rounded border border-border bg-muted p-0.5 text-xs">
            {(["7d", "30d", "All"] as Range[]).map((r) => (
              <button
                key={r}
                type="button"
                onClick={() => setRange(r)}
                className={cn(
                  "rounded px-2 py-0.5 font-medium transition-colors",
                  range === r
                    ? "bg-card text-foreground shadow-sm"
                    : "text-muted-foreground hover:text-foreground"
                )}
              >
                {r}
              </button>
            ))}
          </div>
        </div>
      </CardHeader>
      <CardContent className="pb-4">
        <ResponsiveContainer width="100%" height={240}>
          <LineChart data={visible} margin={{ top: 4, right: 8, left: -20, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
            <XAxis
              dataKey="date"
              tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }}
              axisLine={false}
              tickLine={false}
            />
            <YAxis
              domain={[0, 280]}
              tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }}
              axisLine={false}
              tickLine={false}
            />
            <Tooltip
              contentStyle={{
                fontSize: 11,
                borderColor: "hsl(var(--border))",
                backgroundColor: "hsl(var(--card))",
                borderRadius: "var(--radius)",
              }}
            />
            <Legend
              iconType="plainline"
              iconSize={16}
              wrapperStyle={{ fontSize: 11, paddingTop: 8 }}
            />
            {SERIES.map((s) => (
              <Line
                key={s.key}
                type="monotone"
                dataKey={s.key}
                name={s.label}
                stroke={s.color}
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 3 }}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}
