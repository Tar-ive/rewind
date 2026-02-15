"use client";

import type { Task } from "@/types/schedule";
import { PRIORITY_CONFIG } from "@/lib/constants";

function formatTime(iso: string): string {
  return new Date(iso).toLocaleTimeString("en-US", {
    hour: "numeric",
    minute: "2-digit",
    hour12: true,
  });
}

function EnergyDots({ cost }: { cost: number }) {
  return (
    <div className="flex gap-0.5">
      {Array.from({ length: 5 }, (_, i) => (
        <div
          key={i}
          className={`h-1.5 w-1.5 rounded-full ${
            i < cost ? "bg-amber-400" : "bg-zinc-700"
          }`}
        />
      ))}
    </div>
  );
}

interface TaskCardProps {
  task: Task;
  isSwapping?: boolean;
  swapDirection?: "in" | "out";
}

export default function TaskCard({
  task,
  isSwapping = false,
  swapDirection,
}: TaskCardProps) {
  const priority = PRIORITY_CONFIG[task.priority];

  return (
    <div
      className={`
        relative rounded-lg border p-3 transition-all duration-500 ease-in-out
        ${priority.bg} ${priority.border}
        ${isSwapping && swapDirection === "out" ? "animate-slide-out" : ""}
        ${isSwapping && swapDirection === "in" ? "animate-slide-in" : ""}
        ${task.status === "delegated" ? "opacity-60" : ""}
      `}
    >
      {/* Priority badge */}
      <div className="flex items-center justify-between mb-2">
        <span
          className={`text-xs font-semibold uppercase tracking-wider ${priority.color}`}
        >
          {task.priority} · {priority.label}
        </span>
        <span className="text-xs text-zinc-500">
          {task.estimated_duration}m
        </span>
      </div>

      {/* Title */}
      <h3 className="font-medium text-sm text-zinc-100">{task.title}</h3>

      {/* Time & metadata */}
      <div className="flex items-center justify-between mt-3">
        <span className="text-xs text-zinc-500">
          {formatTime(task.start_time)} — {formatTime(task.end_time)}
        </span>
        <EnergyDots cost={task.energy_cost} />
      </div>

      {/* Status indicators */}
      {task.status === "delegated" && (
        <div className="absolute top-2 right-2">
          <span className="text-xs bg-purple-500/20 text-purple-400 px-2 py-0.5 rounded-full">
            GhostWorker
          </span>
        </div>
      )}
      {task.status === "in_progress" && (
        <div className="absolute top-0 left-0 h-full w-0.5 rounded-l-lg bg-green-500" />
      )}
    </div>
  );
}
