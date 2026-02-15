"use client";

import { useEffect, useState, useCallback } from "react";
import { API_URL } from "@/lib/constants";
import { MOCK_CALENDAR_EVENTS } from "@/lib/mockCalendar";

// ── Types ──────────────────────────────────────────────────────────────

interface CalendarEvent {
  id: string;
  title: string;
  start: string;
  end: string;
  description?: string;
  location?: string;
}

// ── Date helpers ───────────────────────────────────────────────────────

function addDays(date: Date, days: number): Date {
  const d = new Date(date);
  d.setDate(d.getDate() + days);
  return d;
}

function getWeekStart(date: Date): Date {
  const d = new Date(date);
  const day = d.getDay();
  const diff = day === 0 ? -6 : 1 - day; // Monday start
  d.setDate(d.getDate() + diff);
  d.setHours(0, 0, 0, 0);
  return d;
}

function isSameDay(a: Date, b: Date): boolean {
  return a.toDateString() === b.toDateString();
}

function formatTime(iso: string): string {
  return new Date(iso).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatDateShort(date: Date): string {
  return date.toLocaleDateString([], { weekday: "short", month: "short", day: "numeric" });
}

function formatWeekRange(start: Date): string {
  const end = addDays(start, 6);
  const startStr = start.toLocaleDateString([], { month: "short", day: "numeric" });
  const endStr = end.toLocaleDateString([], { month: "short", day: "numeric", year: "numeric" });
  return `${startStr} - ${endStr}`;
}

function isToday(date: Date): boolean {
  return date.toDateString() === new Date().toDateString();
}

// ── Accent colors for events ───────────────────────────────────────────

const EVENT_COLORS = [
  { border: "border-l-blue-500", bg: "bg-blue-500/5" },
  { border: "border-l-cyan-500", bg: "bg-cyan-500/5" },
  { border: "border-l-purple-500", bg: "bg-purple-500/5" },
  { border: "border-l-green-500", bg: "bg-green-500/5" },
  { border: "border-l-amber-500", bg: "bg-amber-500/5" },
];

// ── Component ──────────────────────────────────────────────────────────

export default function CalendarPage() {
  const [events, setEvents] = useState<CalendarEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [source, setSource] = useState<"google" | "local">("local");
  const [view, setView] = useState<"week" | "day">("week");
  const [weekOffset, setWeekOffset] = useState(0);

  const weekStart = getWeekStart(addDays(new Date(), weekOffset * 7));

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  function parseCalendarItems(rawItems: any[]): CalendarEvent[] {
    return rawItems.map((e) => {
      const startStr =
        typeof e.start === "string"
          ? e.start
          : e.start?.dateTime ?? e.start?.date ?? "";
      const endStr =
        typeof e.end === "string"
          ? e.end
          : e.end?.dateTime ?? e.end?.date ?? "";
      return {
        id: e.id || String(Math.random()),
        title: e.summary || e.title || "Untitled",
        start: startStr,
        end: endStr,
        description: e.description || undefined,
        location: e.location || undefined,
      };
    });
  }

  function loadMockEvents() {
    const parsed = parseCalendarItems(MOCK_CALENDAR_EVENTS);
    setEvents(parsed.sort((a, b) => a.start.localeCompare(b.start)));
    setError(null);
    setLoading(false);
  }

  const fetchGoogleEvents = useCallback(async () => {
    setLoading(true);
    setError(null);

    const timeMin = weekStart.toISOString();
    const timeMax = addDays(weekStart, 7).toISOString();

    try {
      const res = await fetch(
        `${API_URL}/api/calendar/events?time_min=${encodeURIComponent(timeMin)}&time_max=${encodeURIComponent(timeMax)}`
      );
      const data = await res.json();

      if (data.error || data.successful === false) {
        const raw = data.error || "Unknown error";
        const friendly = raw.includes("ConnectedAccountNotFound")
          ? "Google Calendar not connected. Go to Integrations to connect, or view the Before Rewind schedule."
          : raw;
        setError(friendly);
        setEvents([]);
      } else {
        const rawItems =
          data.events ??
          data.data?.items ??
          (Array.isArray(data.data) ? data.data : []);

        const parsed = parseCalendarItems(rawItems);
        setEvents(parsed.sort((a, b) => a.start.localeCompare(b.start)));
      }
    } catch {
      setError("Failed to fetch calendar events.");
      setEvents([]);
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [weekOffset]);

  // Load data based on selected source
  useEffect(() => {
    if (source === "local") {
      loadMockEvents();
    } else {
      fetchGoogleEvents();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [source, fetchGoogleEvents]);

  // Auto-refresh when viewing Google Calendar
  useEffect(() => {
    if (source !== "google") return;
    const interval = setInterval(fetchGoogleEvents, 30_000);
    return () => clearInterval(interval);
  }, [source, fetchGoogleEvents]);

  const days = Array.from({ length: 7 }, (_, i) => addDays(weekStart, i));

  const getEventsForDay = (date: Date) =>
    events.filter((e) => e.start && isSameDay(new Date(e.start), date));

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <header className="flex items-center justify-between border-b border-zinc-800 px-6 py-4">
        <div className="flex items-center gap-3">
          <h1 className="text-lg font-semibold text-white">Calendar</h1>
          {/* Source toggle */}
          <div className="flex rounded-lg border border-zinc-700 overflow-hidden">
            <button
              onClick={() => setSource("local")}
              className={`px-3 py-1 text-[11px] transition-colors ${
                source === "local"
                  ? "bg-violet-500/20 text-violet-300 border-r border-zinc-700"
                  : "text-zinc-500 hover:text-zinc-300 border-r border-zinc-700"
              }`}
            >
              Before Rewind
            </button>
            <button
              onClick={() => setSource("google")}
              className={`px-3 py-1 text-[11px] transition-colors ${
                source === "google"
                  ? "bg-green-500/20 text-green-300"
                  : "text-zinc-500 hover:text-zinc-300"
              }`}
            >
              Google Calendar
            </button>
          </div>
        </div>

        {/* Week navigation */}
        <div className="flex items-center gap-3">
          <button
            onClick={() => setWeekOffset((o) => o - 1)}
            className="rounded-lg border border-zinc-700 px-2 py-1 text-xs text-zinc-400 hover:bg-zinc-800 transition-colors"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
              <path d="M15 18l-6-6 6-6" />
            </svg>
          </button>
          <span className="text-sm text-zinc-300 min-w-[180px] text-center">
            {formatWeekRange(weekStart)}
          </span>
          <button
            onClick={() => setWeekOffset((o) => o + 1)}
            className="rounded-lg border border-zinc-700 px-2 py-1 text-xs text-zinc-400 hover:bg-zinc-800 transition-colors"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
              <path d="M9 18l6-6-6-6" />
            </svg>
          </button>
          {weekOffset !== 0 && (
            <button
              onClick={() => setWeekOffset(0)}
              className="rounded-lg bg-zinc-800 px-2 py-1 text-xs text-zinc-400 hover:text-zinc-200 transition-colors"
            >
              Today
            </button>
          )}
        </div>

        {/* View toggle */}
        <div className="flex rounded-lg border border-zinc-700 overflow-hidden">
          <button
            onClick={() => setView("week")}
            className={`px-3 py-1.5 text-xs transition-colors ${
              view === "week"
                ? "bg-zinc-700 text-white"
                : "text-zinc-500 hover:text-zinc-300"
            }`}
          >
            Week
          </button>
          <button
            onClick={() => setView("day")}
            className={`px-3 py-1.5 text-xs transition-colors ${
              view === "day"
                ? "bg-zinc-700 text-white"
                : "text-zinc-500 hover:text-zinc-300"
            }`}
          >
            Day
          </button>
        </div>
      </header>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-6">
        {loading ? (
          <div className="grid grid-cols-7 gap-3">
            {Array.from({ length: 7 }, (_, i) => (
              <div key={i} className="space-y-2">
                <div className="h-4 w-16 animate-pulse rounded bg-zinc-800" />
                <div className="h-16 animate-pulse rounded-lg bg-zinc-800/50" />
                <div className="h-12 animate-pulse rounded-lg bg-zinc-800/50" />
              </div>
            ))}
          </div>
        ) : error ? (
          <div className="flex flex-col items-center justify-center py-20 gap-3">
            <p className="text-sm text-zinc-500">{error}</p>
            <a
              href="/integrations"
              className="text-xs text-blue-400 hover:underline"
            >
              Go to Integrations to connect
            </a>
          </div>
        ) : view === "week" ? (
          /* Week View */
          <div className="grid grid-cols-7 gap-3">
            {days.map((day) => {
              const dayEvents = getEventsForDay(day);
              const today = isToday(day);

              return (
                <div key={day.toISOString()} className="flex flex-col gap-1.5">
                  {/* Day header */}
                  <div
                    className={`pb-2 border-b text-xs font-medium ${
                      today
                        ? "border-blue-500/50 text-blue-400"
                        : "border-zinc-800 text-zinc-500"
                    }`}
                  >
                    {day.toLocaleDateString([], { weekday: "short" })}
                    <span className={`ml-1 ${today ? "text-blue-300" : "text-zinc-400"}`}>
                      {day.getDate()}
                    </span>
                  </div>

                  {/* Events */}
                  {dayEvents.length === 0 ? (
                    <p className="text-[10px] text-zinc-700 py-2 text-center">
                      No events
                    </p>
                  ) : (
                    dayEvents.map((event, idx) => {
                      const color = EVENT_COLORS[idx % EVENT_COLORS.length];
                      return (
                        <div
                          key={event.id}
                          className={`rounded-lg border border-zinc-800 border-l-2 ${color.border} ${color.bg} px-2 py-1.5`}
                        >
                          <p className="text-[11px] text-zinc-200 font-medium truncate">
                            {event.title}
                          </p>
                          <p className="text-[10px] text-zinc-500">
                            {formatTime(event.start)}
                            {event.end && ` - ${formatTime(event.end)}`}
                          </p>
                        </div>
                      );
                    })
                  )}
                </div>
              );
            })}
          </div>
        ) : (
          /* Day View */
          <div className="max-w-2xl mx-auto">
            <h2 className="text-sm font-semibold text-zinc-300 mb-4">
              {formatDateShort(new Date())}
            </h2>
            {(() => {
              const todayEvents = getEventsForDay(new Date());
              if (todayEvents.length === 0) {
                return (
                  <p className="text-sm text-zinc-600 text-center py-12">
                    No events today.
                  </p>
                );
              }
              return (
                <div className="space-y-2">
                  {todayEvents.map((event, idx) => {
                    const color = EVENT_COLORS[idx % EVENT_COLORS.length];
                    return (
                      <div
                        key={event.id}
                        className={`flex gap-4 rounded-xl border border-zinc-800 border-l-2 ${color.border} ${color.bg} p-4`}
                      >
                        <div className="text-xs text-zinc-500 w-24 shrink-0 pt-0.5">
                          {formatTime(event.start)}
                          {event.end && (
                            <>
                              <br />
                              {formatTime(event.end)}
                            </>
                          )}
                        </div>
                        <div className="flex-1 min-w-0">
                          <h3 className="text-sm font-medium text-zinc-200">
                            {event.title}
                          </h3>
                          {event.location && (
                            <p className="text-xs text-zinc-500 mt-0.5">
                              {event.location}
                            </p>
                          )}
                          {event.description && (
                            <p className="text-xs text-zinc-500 mt-1 line-clamp-2">
                              {event.description}
                            </p>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              );
            })()}
          </div>
        )}
      </div>
    </div>
  );
}
