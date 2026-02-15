"use client";

import { useState, useCallback } from "react";
import type { Draft } from "@/components/DraftReview";
import type {
  Task,
  SwapOperation,
  EnergyLevel,
  WSMessage,
  UpdatedSchedule,
  DisruptionEvent,
  ReminderNotification,
} from "@/types/schedule";

interface ScheduleState {
  tasks: Task[];
  backlog: Task[];
  energy: EnergyLevel | null;
  swappingTaskIds: Set<string>;
  swapDirections: Map<string, "in" | "out">;
  lastDisruption: DisruptionEvent | null;
  activeReminder: ReminderNotification | null;
  agentLog: AgentLogEntry[];
  drafts: Draft[];
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
    backlog: [],
    energy: null,
    swappingTaskIds: new Set(),
    swapDirections: new Map(),
    lastDisruption: null,
    activeReminder: null,
    agentLog: [],
    drafts: [],
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

  const addDraft = useCallback((draft: Draft) => {
    setState((prev) => ({
      ...prev,
      drafts: [...prev.drafts, draft],
    }));
  }, []);

  const removeDraft = useCallback((draftId: string) => {
    setState((prev) => ({
      ...prev,
      drafts: prev.drafts.filter((d) => d.id !== draftId),
    }));
  }, []);

  const addTask = useCallback((task: Task) => {
    setState((prev) => ({ ...prev, tasks: [...prev.tasks, task] }));
  }, []);

  const setDrafts = useCallback((drafts: Draft[]) => {
    setState((prev) => ({ ...prev, drafts }));
  }, []);

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
        case "ghostworker_draft": {
          const draftData = message.payload as {
            id: string;
            task_id: string;
            task_type: string;
            body: string;
            recipient?: string;
            channel?: string;
            subject?: string;
            cost_fet: number;
            timestamp: string;
          };
          const draft: Draft = {
            id: draftData.id,
            task_id: draftData.task_id,
            task_type: draftData.task_type as Draft["task_type"],
            body: draftData.body,
            recipient: draftData.recipient,
            channel: draftData.channel,
            subject: draftData.subject,
            cost_fet: typeof draftData.cost_fet === "string"
              ? parseFloat(draftData.cost_fet)
              : draftData.cost_fet,
            timestamp: draftData.timestamp,
          };
          addDraft(draft);
          addLogEntry(
            "GhostWorker",
            `New draft: ${draft.task_type} — awaiting review`,
            "ghostworker"
          );
          break;
        }
        case "ghost_worker_status": {
          const status = message.payload as {
            task_id: string;
            draft_id?: string;
            status: string;
            message: string;
          };
          // Remove draft from state on execution or rejection
          if (status.draft_id && (status.status === "executed" || status.status === "rejected")) {
            removeDraft(status.draft_id);
          }
          addLogEntry("GhostWorker", status.message, "ghostworker");
          break;
        }
        case "reminder": {
          const notification = message.payload as ReminderNotification;
          setState((prev) => ({ ...prev, activeReminder: notification }));
          addLogEntry(
            "Reminder Agent",
            `${notification.title}: ${notification.message}`,
            "info"
          );
          break;
        }
        case "agent_activity": {
          const activity = message.payload as {
            agent: string;
            message: string;
            type: AgentLogEntry["type"];
          };
          addLogEntry(activity.agent, activity.message, activity.type);
          break;
        }
        default:
          break;
      }
    },
    [applySwaps, addLogEntry, addDraft, removeDraft, state.tasks]
  );

  return {
    ...state,
    handleWSMessage,
    addLogEntry,
    addTask,
    addDraft,
    removeDraft,
    setDrafts,
    setTasks: (tasks: Task[]) => setState((prev) => ({ ...prev, tasks })),
    setBacklog: (backlog: Task[]) => setState((prev) => ({ ...prev, backlog })),
  };
}
