"use client";

import { useState, useCallback } from "react";
import ScheduleTimeline from "@/components/ScheduleTimeline";
import AgentActivityLog from "@/components/AgentActivityLog";
import TaskInputForm from "@/components/TaskInputForm";
import DraftReview from "@/components/DraftReview";
import type { Draft } from "@/components/DraftReview";
import { useScheduleStore } from "@/lib/useScheduleStore";
import { useWebSocket } from "@/lib/useWebSocket";
import { MOCK_TASKS } from "@/lib/mockData";
import { WS_URL } from "@/lib/constants";
import type { Priority, Task } from "@/types/schedule";

// Mock draft for demo purposes (will come from WebSocket in production)
const MOCK_DRAFTS: Draft[] = [
  {
    id: "draft-1",
    task_id: "task-6",
    task_type: "email_reply",
    recipient: "prof.martinez@stanford.edu",
    subject: "RE: Research Assistant Position",
    body: "Dear Professor Martinez,\n\nThank you for reaching out about the research assistant position. I'm very interested and would love to discuss further.\n\nI'm available this Thursday or Friday afternoon if you'd like to meet. Please let me know what works best for your schedule.\n\nBest regards,\nSarah",
    cost_fet: 0.001,
    timestamp: new Date().toISOString(),
  },
  {
    id: "draft-2",
    task_id: "task-7",
    task_type: "slack_message",
    channel: "cs229-study-group",
    body: "Hey everyone! Heads up — I need to shift our study session tomorrow to 3pm instead of 2pm. Same room. Let me know if that works for you all!",
    cost_fet: 0.001,
    timestamp: new Date().toISOString(),
  },
];

export default function Home() {
  const store = useScheduleStore(MOCK_TASKS);
  const [showTaskForm, setShowTaskForm] = useState(false);
  const [drafts, setDrafts] = useState<Draft[]>(MOCK_DRAFTS);

  const { status } = useWebSocket({
    url: WS_URL,
    onMessage: store.handleWSMessage,
  });

  const handleAddTask = useCallback(
    (taskData: {
      title: string;
      description: string;
      priority: Priority;
      estimated_duration: number;
      deadline: string;
      energy_cost: number;
    }) => {
      const now = new Date();
      const newTask: Task = {
        id: `task-${Date.now()}`,
        title: taskData.title,
        description: taskData.description,
        priority: taskData.priority,
        start_time: now.toISOString(),
        end_time: new Date(
          now.getTime() + taskData.estimated_duration * 60000
        ).toISOString(),
        energy_cost: taskData.energy_cost,
        estimated_duration: taskData.estimated_duration,
        status: "scheduled",
        delegatable: false,
      };
      store.setTasks([...store.tasks, newTask]);
      store.addLogEntry(
        "Scheduler Kernel",
        `New task added: "${taskData.title}" (${taskData.priority})`,
        "info"
      );
      setShowTaskForm(false);
    },
    [store]
  );

  const handleApproveDraft = useCallback(
    (draftId: string) => {
      const draft = drafts.find((d) => d.id === draftId);
      if (draft) {
        store.addLogEntry(
          "GhostWorker",
          `Approved & sending: ${draft.subject || draft.channel}`,
          "ghostworker"
        );
      }
      setDrafts((prev) => prev.filter((d) => d.id !== draftId));
    },
    [drafts, store]
  );

  const handleEditDraft = useCallback(
    (draftId: string, editedBody: string) => {
      store.addLogEntry(
        "GhostWorker",
        `Draft edited & sent`,
        "ghostworker"
      );
      setDrafts((prev) => prev.filter((d) => d.id !== draftId));
    },
    [store]
  );

  const handleRejectDraft = useCallback(
    (draftId: string) => {
      store.addLogEntry(
        "GhostWorker",
        `Draft rejected`,
        "ghostworker"
      );
      setDrafts((prev) => prev.filter((d) => d.id !== draftId));
    },
    [store]
  );

  return (
    <div className="flex h-screen flex-col">
      {/* Header */}
      <header className="flex items-center justify-between border-b border-zinc-800 px-6 py-3">
        <div className="flex items-center gap-3">
          <h1 className="text-lg font-bold tracking-tight">REWIND</h1>
          <span className="text-xs text-zinc-600">
            The Intelligent Life Scheduler
          </span>
        </div>
        <div className="flex items-center gap-4">
          <button
            onClick={() => setShowTaskForm(true)}
            className="rounded-lg border border-zinc-700 px-3 py-1.5 text-xs text-zinc-300 hover:bg-zinc-800 transition-colors"
          >
            + Add Task
          </button>
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

      {/* Main content — Split Screen */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left: Schedule Timeline */}
        <div className="flex-1 overflow-y-auto border-r border-zinc-800 p-4">
          <div className="mb-4">
            <h2 className="text-sm font-semibold text-zinc-300">
              Today&apos;s Schedule
            </h2>
            <p className="text-xs text-zinc-600">
              {new Date().toLocaleDateString("en-US", {
                weekday: "long",
                month: "long",
                day: "numeric",
              })}
            </p>
          </div>
          <ScheduleTimeline
            tasks={store.tasks}
            swappingTaskIds={store.swappingTaskIds}
            swapDirections={store.swapDirections}
          />
        </div>

        {/* Right: Drafts + Agent Activity Log */}
        <div className="w-[400px] shrink-0 overflow-y-auto p-4 space-y-4">
          {/* Pending drafts */}
          {drafts.length > 0 && (
            <div>
              <h2 className="text-sm font-semibold text-zinc-300 mb-3">
                Pending Drafts
                <span className="ml-2 text-[10px] font-normal text-cyan-500">
                  {drafts.length} awaiting review
                </span>
              </h2>
              <div className="space-y-3">
                {drafts.map((draft) => (
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
          <AgentActivityLog entries={store.agentLog} />
        </div>
      </div>

      {/* Task input modal */}
      {showTaskForm && (
        <TaskInputForm
          onSubmit={handleAddTask}
          onClose={() => setShowTaskForm(false)}
        />
      )}
    </div>
  );
}
