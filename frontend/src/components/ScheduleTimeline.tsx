"use client";

import type { Task } from "@/types/schedule";
import TaskCard from "./TaskCard";

interface ScheduleTimelineProps {
  tasks: Task[];
  swappingTaskIds?: Set<string>;
  swapDirections?: Map<string, "in" | "out">;
}

export default function ScheduleTimeline({
  tasks,
  swappingTaskIds,
  swapDirections,
}: ScheduleTimelineProps) {
  const sortedTasks = [...tasks]
    .filter((t) => t.status !== "buffered")
    .sort(
      (a, b) =>
        new Date(a.start_time).getTime() - new Date(b.start_time).getTime()
    );

  // Group tasks by hour for the timeline labels
  const grouped = groupByHour(sortedTasks);

  return (
    <div className="space-y-1">
      {sortedTasks.length === 0 ? (
        <div className="flex items-center justify-center py-20">
          <p className="text-zinc-600 text-sm">
            No tasks scheduled. Waiting for data...
          </p>
        </div>
      ) : (
        grouped.map(({ hour, tasks: hourTasks }) => (
          <div key={hour} className="flex gap-3">
            {/* Time label */}
            <div className="w-14 shrink-0 pt-3 text-right">
              <span className="text-[11px] text-zinc-600 tabular-nums">
                {formatHour(hour)}
              </span>
            </div>

            {/* Tasks in this hour */}
            <div className="flex-1 space-y-1.5 border-l border-zinc-800 pl-3 pb-2">
              {hourTasks.map((task) => (
                <TaskCard
                  key={task.id}
                  task={task}
                  isSwapping={swappingTaskIds?.has(task.id)}
                  swapDirection={swapDirections?.get(task.id)}
                />
              ))}
            </div>
          </div>
        ))
      )}

      {/* Current time indicator */}
      <CurrentTimeIndicator />
    </div>
  );
}

interface HourGroup {
  hour: number;
  tasks: Task[];
}

function groupByHour(tasks: Task[]): HourGroup[] {
  const groups: Map<number, Task[]> = new Map();

  for (const task of tasks) {
    const hour = new Date(task.start_time).getHours();
    if (!groups.has(hour)) {
      groups.set(hour, []);
    }
    groups.get(hour)!.push(task);
  }

  return Array.from(groups.entries())
    .sort(([a], [b]) => a - b)
    .map(([hour, tasks]) => ({ hour, tasks }));
}

function formatHour(hour: number): string {
  if (hour < 12) return `${hour} AM`;
  if (hour === 12) return "12 PM";
  return `${hour - 12} PM`;
}

function CurrentTimeIndicator() {
  const now = new Date();
  const hours = now.getHours();
  const timeStr = now.toLocaleTimeString("en-US", {
    hour: "numeric",
    minute: "2-digit",
    hour12: true,
  });

  if (hours < 6 || hours > 23) return null;

  return (
    <div className="flex items-center gap-3 py-1">
      <div className="w-14 text-right">
        <span className="text-[10px] text-red-500 font-medium tabular-nums">
          {timeStr}
        </span>
      </div>
      <div className="flex flex-1 items-center">
        <div className="h-2 w-2 rounded-full bg-red-500" />
        <div className="flex-1 h-px bg-red-500/40" />
      </div>
    </div>
  );
}
