"use client";

import { useState, useCallback } from "react";
import type {
  Task,
  SwapOperation,
  EnergyLevel,
  WSMessage,
  UpdatedSchedule,
  DisruptionEvent,
} from "@/types/schedule";

interface ScheduleState {
  tasks: Task[];
  energy: EnergyLevel | null;
  swappingTaskIds: Set<string>;
  swapDirections: Map<string, "in" | "out">;
  lastDisruption: DisruptionEvent | null;
  agentLog: AgentLogEntry[];
}

export interface AgentLogEntry {
  id: string;
  timestamp: string;
  agent: string;
  message: string;
  type: "info" | "disruption" | "swap" | "delegation" | "ghostworker";
}

export function useScheduleStore(initialTasks: Task[] = []) {
  const [state, setState] = useState<ScheduleState>({
    tasks: initialTasks,
    energy: null,
    swappingTaskIds: new Set(),
    swapDirections: new Map(),
    lastDisruption: null,
    agentLog: [],
  });

  const addLogEntry = useCallback(
    (agent: string, message: string, type: AgentLogEntry["type"] = "info") => {
      setState((prev) => ({
        ...prev,
        agentLog: [
          {
            id: crypto.randomUUID(),
            timestamp: new Date().toISOString(),
            agent,
            message,
            type,
          },
          ...prev.agentLog,
        ].slice(0, 100), // keep last 100
      }));
    },
    []
  );

  const applySwaps = useCallback(
    (swaps: SwapOperation[], updatedTasks: Task[]) => {
      // Mark tasks as swapping for animation
      const swappingIds = new Set(swaps.map((s) => s.task_id));
      const directions = new Map(
        swaps.map((s) => [
          s.task_id,
          s.action === "swap_in" ? ("in" as const) : ("out" as const),
        ])
      );

      setState((prev) => ({
        ...prev,
        swappingTaskIds: swappingIds,
        swapDirections: directions,
      }));

      // After animation, update the tasks
      setTimeout(() => {
        setState((prev) => ({
          ...prev,
          tasks: updatedTasks,
          swappingTaskIds: new Set(),
          swapDirections: new Map(),
        }));
      }, 600);
    },
    []
  );

  const handleWSMessage = useCallback(
    (message: WSMessage) => {
      switch (message.type) {
        case "updated_schedule": {
          const data = message.payload as UpdatedSchedule;
          if (data.swaps.length > 0) {
            applySwaps(data.swaps, data.tasks);
            data.swaps.forEach((s) =>
              addLogEntry(
                "Scheduler Kernel",
                `${s.action}: "${state.tasks.find((t) => t.id === s.task_id)?.title || s.task_id}" — ${s.reason}`,
                "swap"
              )
            );
          } else {
            setState((prev) => ({ ...prev, tasks: data.tasks }));
          }
          if (data.energy) {
            setState((prev) => ({ ...prev, energy: data.energy }));
          }
          break;
        }
        case "disruption_event": {
          const disruption = message.payload as DisruptionEvent;
          setState((prev) => ({ ...prev, lastDisruption: disruption }));
          addLogEntry(
            "Disruption Detector",
            `${disruption.severity.toUpperCase()}: ${disruption.context_summary}`,
            "disruption"
          );
          break;
        }
        case "energy_update": {
          const energy = message.payload as EnergyLevel;
          setState((prev) => ({ ...prev, energy }));
          addLogEntry(
            "Energy Monitor",
            `Energy level: ${energy.level}/5 (${energy.source})`,
            "info"
          );
          break;
        }
        case "ghost_worker_status": {
          const status = message.payload as { task_id: string; status: string; message: string };
          addLogEntry("GhostWorker", status.message, "ghostworker");
          break;
        }
        default:
          break;
      }
    },
    [applySwaps, addLogEntry, state.tasks]
  );

  return {
    ...state,
    handleWSMessage,
    addLogEntry,
    setTasks: (tasks: Task[]) => setState((prev) => ({ ...prev, tasks })),
  };
}
