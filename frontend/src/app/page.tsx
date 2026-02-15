"use client";

import { useCallback, useEffect, useState } from "react";
import AgentActivityLog from "@/components/AgentActivityLog";
import DraftReview from "@/components/DraftReview";
import TaskInput from "@/components/TaskInput";
import VoiceAgent from "@/components/VoiceAgent";
import DemoControls from "@/components/DemoControls";
import type { Draft } from "@/components/DraftReview";
import { useScheduleStore } from "@/lib/useScheduleStore";
import { useWebSocket } from "@/lib/useWebSocket";
import { WS_URL, API_URL } from "@/lib/constants";
import { PRIORITY_CONFIG } from "@/lib/constants";
import type { Task } from "@/types/schedule";

const SEVERITY_COLORS = {
  minor: "text-yellow-400",
  major: "text-orange-400",
  critical: "text-red-400",
};

export default function Home() {
  const store = useScheduleStore([]);
  const [backlogOpen, setBacklogOpen] = useState(true);

  const { status } = useWebSocket({
    url: WS_URL,
    onMessage: store.handleWSMessage,
  });

  // Load real schedule + backlog + drafts from backend on mount
  useEffect(() => {
    async function loadSchedule() {
      try {
        const res = await fetch(`${API_URL}/api/schedule`);
        const data = await res.json();
        if (data.tasks?.length) store.setTasks(data.tasks);
        if (data.backlog?.length) store.setBacklog(data.backlog);
      } catch {
        // WS will populate tasks
      }
    }
    loadSchedule();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Fetch existing pending drafts on mount
  useEffect(() => {
    async function fetchDrafts() {
      try {
        const res = await fetch(`${API_URL}/api/ghostworker/drafts`);
        if (res.ok) {
          const data = await res.json();
          if (data.drafts && data.drafts.length > 0) {
            const parsed: Draft[] = data.drafts.map((d: Record<string, string>) => ({
              id: d.id,
              task_id: d.task_id,
              task_type: d.task_type as Draft["task_type"],
              body: d.body,
              recipient: d.recipient || undefined,
              channel: d.channel || undefined,
              subject: d.subject || undefined,
              cost_fet: parseFloat(d.cost_fet) || 0.001,
              timestamp: d.timestamp,
            }));
            store.setDrafts(parsed);
          }
        }
      } catch {
        // Server may not be running yet — drafts will arrive via WebSocket
      }
    }
    fetchDrafts();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleApproveDraft = useCallback(
    async (draftId: string) => {
      const draft = store.drafts.find((d) => d.id === draftId);
      if (draft) {
        store.addLogEntry(
          "GhostWorker",
          `Approved & sending: ${draft.subject || draft.channel || draft.task_type}`,
          "ghostworker"
        );

        // For email drafts, open Gmail compose in a new tab for visual demo
        if (draft.task_type === "email_reply" && draft.recipient) {
          const gmailUrl = `https://mail.google.com/mail/?view=cm&to=${encodeURIComponent(draft.recipient)}&su=${encodeURIComponent(draft.subject || "")}&body=${encodeURIComponent(draft.body)}`;
          window.open(gmailUrl, "_blank");
        }
      }
      try {
        await fetch(`${API_URL}/api/ghostworker/drafts/${draftId}/approve`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({}),
        });
      } catch {
        store.addLogEntry("GhostWorker", "Failed to send approval", "ghostworker");
      }
      store.removeDraft(draftId);
    },
    [store]
  );

  const handleEditDraft = useCallback(
    async (draftId: string, editedBody: string) => {
      const draft = store.drafts.find((d) => d.id === draftId);
      store.addLogEntry("GhostWorker", "Draft edited & sent", "ghostworker");

      // For email drafts, open Gmail compose with edited body
      if (draft && draft.task_type === "email_reply" && draft.recipient) {
        const gmailUrl = `https://mail.google.com/mail/?view=cm&to=${encodeURIComponent(draft.recipient)}&su=${encodeURIComponent(draft.subject || "")}&body=${encodeURIComponent(editedBody)}`;
        window.open(gmailUrl, "_blank");
      }

      try {
        await fetch(`${API_URL}/api/ghostworker/drafts/${draftId}/approve`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ edited_body: editedBody }),
        });
      } catch {
        store.addLogEntry("GhostWorker", "Failed to send edited draft", "ghostworker");
      }
      store.removeDraft(draftId);
    },
    [store]
  );

  const handleRejectDraft = useCallback(
    async (draftId: string) => {
      store.addLogEntry("GhostWorker", "Draft rejected", "ghostworker");
      try {
        await fetch(`${API_URL}/api/ghostworker/drafts/${draftId}/reject`, {
          method: "POST",
        });
      } catch {
        store.addLogEntry("GhostWorker", "Failed to send rejection", "ghostworker");
      }
      store.removeDraft(draftId);
    },
    [store]
  );

  const handleAgentAction = useCallback(
    async (actionId: string) => {
      // actionId format: "delegate:task-6"
      if (actionId.startsWith("delegate:")) {
        const taskId = actionId.replace("delegate:", "");
        store.addLogEntry(
          "Scheduler Kernel",
          `Delegating ${taskId} to GhostWorker...`,
          "delegation"
        );
        try {
          const res = await fetch(`${API_URL}/api/demo/ghostworker/${taskId}`, {
            method: "POST",
          });
          if (!res.ok) throw new Error(`${res.status}`);
        } catch {
          store.addLogEntry("GhostWorker", `Failed to delegate ${taskId}`, "ghostworker");
        }
      }
    },
    [store]
  );

  // Split tasks and sort by start time
  const activeTasks = store.tasks
    .filter((t) => t.status === "scheduled" || t.status === "in_progress")
    .sort((a, b) => {
      if (!a.start_time) return 1;
      if (!b.start_time) return -1;
      return new Date(a.start_time).getTime() - new Date(b.start_time).getTime();
    });
  const delegatedTasks = store.tasks.filter((t) => t.status === "delegated");
  const draftIds = store.drafts.map((d) => d.id);

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <header className="flex items-center justify-end border-b border-zinc-800 px-6 py-3">
        <div className="flex items-center gap-4">
          {store.energy && (
            <div className="flex items-center gap-2 text-xs text-zinc-400">
              <span>Energy</span>
              <div className="flex gap-0.5">
                {Array.from({ length: 5 }, (_, i) => (
                  <div
                    key={i}
                    className={`h-2 w-4 rounded-sm ${
                      i < store.energy!.level
                        ? "bg-amber-400"
                        : "bg-zinc-700"
                    }`}
                  />
                ))}
              </div>
            </div>
          )}
          <div className="flex items-center gap-1.5">
            <div
              className={`h-2 w-2 rounded-full ${
                status === "connected"
                  ? "bg-green-500"
                  : status === "connecting"
                    ? "bg-yellow-500 animate-pulse"
                    : "bg-zinc-600"
              }`}
            />
            <span className="text-xs text-zinc-600">
              {status === "connected" ? "Live" : status}
            </span>
          </div>
        </div>
      </header>

      {/* Main content */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left: Tasks */}
        <div className="flex-1 overflow-y-auto border-r border-zinc-800 p-4 space-y-4">
          {/* Disruption banner */}
          {store.lastDisruption && (
            <div
              className={`rounded-lg border px-4 py-3 ${
                store.lastDisruption.severity === "critical"
                  ? "border-red-500/30 bg-red-500/5"
                  : store.lastDisruption.severity === "major"
                    ? "border-orange-500/30 bg-orange-500/5"
                    : "border-yellow-500/30 bg-yellow-500/5"
              }`}
            >
              <div className="flex items-center gap-2 mb-1">
                <span
                  className={`text-xs font-semibold uppercase ${
                    SEVERITY_COLORS[store.lastDisruption.severity]
                  }`}
                >
                  {store.lastDisruption.severity} disruption
                </span>
                <span className="text-xs text-zinc-500">
                  {store.lastDisruption.freed_minutes > 0
                    ? `+${store.lastDisruption.freed_minutes}min gained`
                    : `${store.lastDisruption.freed_minutes}min lost`}
                </span>
              </div>
              <p className="text-xs text-zinc-400">
                {store.lastDisruption.context_summary}
              </p>
            </div>
          )}

          {/* Task input */}
          <TaskInput />

          {/* ── Today's Tasks ──────────────────────────────────────────── */}
          <div>
            <h2 className="text-sm font-semibold text-zinc-300 mb-3">
              Today
              <span className="ml-2 text-[10px] font-normal text-zinc-500">
                {activeTasks.length} scheduled
                {delegatedTasks.length > 0 &&
                  ` / ${delegatedTasks.length} delegated`}
              </span>
            </h2>
            <div className="space-y-2">
              {activeTasks.map((task) => (
                <ActiveTaskRow
                  key={task.id}
                  task={task}
                  isSwapping={store.swappingTaskIds.has(task.id)}
                  swapDirection={store.swapDirections.get(task.id)}
                />
              ))}
              {activeTasks.length === 0 && (
                <p className="text-xs text-zinc-600 py-4 text-center">
                  No active tasks. Trigger daily planning to populate.
                </p>
              )}
            </div>
          </div>

          {/* Delegated tasks */}
          {delegatedTasks.length > 0 && (
            <div>
              <h2 className="text-sm font-semibold text-zinc-300 mb-3">
                Delegated to GhostWorker
              </h2>
              <div className="space-y-2">
                {delegatedTasks.map((task) => (
                  <div
                    key={task.id}
                    className="flex items-center gap-3 rounded-lg border border-zinc-800 bg-zinc-900/50 px-3 py-2"
                  >
                    <span className="text-[10px] font-medium text-cyan-400 bg-cyan-500/10 px-1.5 py-0.5 rounded">
                      GW
                    </span>
                    <span className="text-xs text-zinc-300 flex-1">
                      {task.title}
                    </span>
                    <span className="text-[10px] text-zinc-500">
                      {task.task_type}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* ── Backlog / Long-term Tasks ──────────────────────────────── */}
          <div>
            <button
              onClick={() => setBacklogOpen(!backlogOpen)}
              className="flex items-center gap-2 text-sm font-semibold text-zinc-300 mb-3 hover:text-zinc-100 transition-colors"
            >
              <svg
                width="12"
                height="12"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                className={`transition-transform ${backlogOpen ? "rotate-90" : ""}`}
              >
                <path d="M9 18l6-6-6-6" />
              </svg>
              Backlog
              <span className="text-[10px] font-normal text-zinc-500">
                {store.backlog.length} tasks
              </span>
            </button>
            {backlogOpen && (
              <div className="space-y-1.5">
                {store.backlog.map((task) => (
                  <BacklogTaskRow key={task.id} task={task} />
                ))}
                {store.backlog.length === 0 && (
                  <p className="text-xs text-zinc-600 py-3 text-center">
                    No backlog tasks. LTS/MTS will pull from here when scheduling.
                  </p>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Right: Drafts + Agent Activity Log */}
        <div className="w-[420px] shrink-0 overflow-y-auto p-4 space-y-4">
          {/* Pending drafts */}
          {store.drafts.length > 0 && (
            <div>
              <h2 className="text-sm font-semibold text-zinc-300 mb-3">
                Pending Drafts
                <span className="ml-2 text-[10px] font-normal text-cyan-500">
                  {store.drafts.length} awaiting review
                </span>
              </h2>
              <div className="space-y-3">
                {store.drafts.map((draft) => (
                  <DraftReview
                    key={draft.id}
                    draft={draft}
                    onApprove={handleApproveDraft}
                    onEdit={handleEditDraft}
                    onReject={handleRejectDraft}
                  />
                ))}
              </div>
            </div>
          )}

          {/* Agent activity log */}
          <AgentActivityLog entries={store.agentLog} onAction={handleAgentAction} />
        </div>
      </div>

      {/* Voice Agent — floating mic */}
      <VoiceAgent draftIds={draftIds} />

      {/* Demo Controls — floating panel */}
      <DemoControls />
    </div>
  );
}

function ActiveTaskRow({
  task,
  isSwapping,
  swapDirection,
}: {
  task: Task;
  isSwapping: boolean;
  swapDirection?: "in" | "out";
}) {
  const config = PRIORITY_CONFIG[task.priority];

  return (
    <div
      className={`flex items-center gap-3 rounded-lg border px-3 py-2.5 transition-all ${
        config.border
      } ${config.bg} ${
        isSwapping
          ? swapDirection === "in"
            ? "animate-[slide-in-right_0.5s_ease-out]"
            : "animate-[slide-out-left_0.5s_ease-out]"
          : ""
      }`}
    >
      {/* Priority badge */}
      <span
        className={`text-[10px] font-bold ${config.color} min-w-[20px]`}
      >
        {task.priority}
      </span>

      {/* Task info */}
      <div className="flex-1 min-w-0">
        <p className="text-xs text-zinc-200 truncate">{task.title}</p>
        {task.description && (
          <p className="text-[10px] text-zinc-500 truncate">
            {task.description}
          </p>
        )}
      </div>

      {/* Time */}
      {task.start_time && (
        <span className="text-[10px] text-zinc-500 whitespace-nowrap">
          {new Date(task.start_time).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}
        </span>
      )}

      {/* Duration */}
      <span className="text-[10px] text-zinc-500 whitespace-nowrap">
        {task.estimated_duration}min
      </span>

      {/* Energy dots */}
      <div className="flex gap-0.5">
        {Array.from({ length: 5 }, (_, i) => (
          <div
            key={i}
            className={`h-1.5 w-1.5 rounded-full ${
              i < task.energy_cost ? "bg-amber-400" : "bg-zinc-700"
            }`}
          />
        ))}
      </div>

      {/* Status */}
      {task.status === "in_progress" && (
        <span className="text-[10px] text-green-400">active</span>
      )}
    </div>
  );
}

function BacklogTaskRow({ task }: { task: Task }) {
  const config = PRIORITY_CONFIG[task.priority];

  return (
    <div
      className={`flex items-center gap-3 rounded-lg border border-zinc-800/50 bg-zinc-900/30 px-3 py-2 transition-all`}
    >
      <span className={`text-[10px] font-bold ${config.color} min-w-[20px]`}>
        {task.priority}
      </span>
      <span className="text-xs text-zinc-400 flex-1 truncate">
        {task.title}
      </span>
      <span className="text-[10px] text-zinc-600 whitespace-nowrap">
        {task.estimated_duration}min
      </span>
    </div>
  );
}
