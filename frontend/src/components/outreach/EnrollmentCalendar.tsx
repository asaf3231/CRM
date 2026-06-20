import { useState } from "react";
import { ChevronLeft, ChevronRight, Calendar } from "lucide-react";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import type { EnrollmentEvent } from "@/types";

interface Props {
  enrollments: EnrollmentEvent[];
}

const WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

const MONTH_NAMES = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

/** Build the grid of day cells for a given year+month. */
function buildGrid(year: number, month: number): (number | null)[] {
  const firstDay = new Date(year, month, 1).getDay(); // 0=Sun
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const cells: (number | null)[] = [];
  for (let i = 0; i < firstDay; i++) cells.push(null);
  for (let d = 1; d <= daysInMonth; d++) cells.push(d);
  return cells;
}

/** Format a Date to "YYYY-MM-DD". */
function isoDate(year: number, month: number, day: number): string {
  const mm = String(month + 1).padStart(2, "0");
  const dd = String(day).padStart(2, "0");
  return `${year}-${mm}-${dd}`;
}

export function EnrollmentCalendar({ enrollments }: Props) {
  const today = new Date();
  const [year, setYear]   = useState(today.getFullYear());
  const [month, setMonth] = useState(today.getMonth());

  const todayIso = isoDate(today.getFullYear(), today.getMonth(), today.getDate());

  function prevMonth() {
    if (month === 0) { setMonth(11); setYear((y) => y - 1); }
    else setMonth((m) => m - 1);
  }
  function nextMonth() {
    if (month === 11) { setMonth(0); setYear((y) => y + 1); }
    else setMonth((m) => m + 1);
  }

  const grid = buildGrid(year, month);

  // Build a lookup: "YYYY-MM-DD" → EnrollmentEvent[]
  const byDate = new Map<string, EnrollmentEvent[]>();
  for (const ev of enrollments) {
    const bucket = byDate.get(ev.date) ?? [];
    bucket.push(ev);
    byDate.set(ev.date, bucket);
  }

  return (
    <Card className="flex flex-col">
      <CardHeader className="pb-2">
        <div className="flex items-center gap-2">
          <Calendar className="h-4 w-4 text-muted-foreground" />
          <span className="flex-1 text-sm font-semibold">Enrollment Calendar</span>
          <button
            type="button"
            onClick={prevMonth}
            className="rounded p-0.5 hover:bg-muted"
            aria-label="Previous month"
          >
            <ChevronLeft className="h-4 w-4 text-muted-foreground" />
          </button>
          <span className="min-w-[100px] text-center text-xs font-medium">
            {MONTH_NAMES[month]} {year}
          </span>
          <button
            type="button"
            onClick={nextMonth}
            className="rounded p-0.5 hover:bg-muted"
            aria-label="Next month"
          >
            <ChevronRight className="h-4 w-4 text-muted-foreground" />
          </button>
        </div>
      </CardHeader>

      <CardContent className="pb-4">
        {/* Weekday header */}
        <div className="mb-1 grid grid-cols-7 gap-px">
          {WEEKDAYS.map((wd) => (
            <div
              key={wd}
              className="py-1 text-center text-[10px] font-medium text-muted-foreground"
            >
              {wd}
            </div>
          ))}
        </div>

        {/* Day cells */}
        <div className="grid grid-cols-7 gap-px">
          {grid.map((day, i) => {
            if (day === null) {
              return <div key={`null-${i}`} className="min-h-[36px]" />;
            }
            const iso = isoDate(year, month, day);
            const isToday = iso === todayIso;
            const evs = byDate.get(iso) ?? [];

            return (
              <div
                key={iso}
                className={cn(
                  "flex min-h-[36px] flex-col rounded p-0.5",
                  isToday && "bg-muted"
                )}
              >
                <span
                  className={cn(
                    "text-right text-[10px] leading-tight",
                    isToday ? "font-semibold text-foreground" : "text-muted-foreground"
                  )}
                >
                  {day}
                </span>
                {evs.map((ev) => (
                  <div
                    key={ev.id}
                    className="mt-0.5 truncate rounded bg-success/15 px-1 py-px text-[9px] font-medium text-success"
                    title={ev.label}
                  >
                    {ev.label}
                  </div>
                ))}
              </div>
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
}
