"use client";

import { useState } from "react";
import { API_URL } from "@/lib/constants";

type DemoStep = "idle" | "running" | "done" | "error";

interface StepState {
  status: DemoStep;
  label: string;
}

export default function DemoControls() {
  const [open, setOpen] = useState(false);
  const [steps, setSteps] = useState<Record<string, StepState>>({});
  const [autoRunning, setAutoRunning] = useState(false);

  const updateStep = (id: string, status: DemoStep, label: string) =>
    setSteps((prev) => ({ ...prev, [id]: { status, label } }));

  // ── Individual actions ────────────────────────────────────────────────

  async function resetDemo() {
    updateStep("reset", "running", "Resetting...");
    try {
      const res = await fetch(`${API_URL}/api/demo/reset`, { method: "POST" });
      if (!res.ok) throw new Error(`${res.status}`);
      updateStep("reset", "done", "Reset complete");
      // Reload the page to pick up fresh data
      setTimeout(() => window.location.reload(), 800);
    } catch {
      updateStep("reset", "error", "Reset failed");
    }
  }

  async function triggerDisruption(
    type: string,
    lostMin: number,
    affected: string[],
    source = "google_calendar"
  ) {
    const id = `disruption-${type}`;
    updateStep(id, "running", `Triggering ${type}...`);
    try {
      const res = await fetch(`${API_URL}/api/disruption`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          event_type: type,
          source,
          lost_minutes: lostMin,
          affected_task_ids: affected,
        }),
      });
      if (!res.ok) throw new Error(`${res.status}`);
      const data = await res.json();
      updateStep(
        id,
        "done",
        `${data.severity} — ${data.swaps?.length || 0} swaps`
      );
    } catch {
      updateStep(id, "error", `${type} failed`);
    }
  }

  async function setEnergy(level: number) {
    const id = `energy-${level}`;
    updateStep(id, "running", `Setting energy ${level}...`);
    try {
      const res = await fetch(`${API_URL}/api/energy`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ level }),
      });
      if (!res.ok) throw new Error(`${res.status}`);
      const data = await res.json();
      const delegated = data.delegated?.length || 0;
      updateStep(
        id,
        "done",
        `Energy → ${level}${delegated ? ` (${delegated} auto-delegated)` : ""}`
      );
    } catch {
      updateStep(id, "error", `Energy update failed`);
    }
  }

  async function triggerGhostWorker() {
    updateStep("ghostworker", "running", "GhostWorker drafting...");
    try {
      const res = await fetch(`${API_URL}/api/demo/ghostworker`, {
        method: "POST",
      });
      if (!res.ok) throw new Error(`${res.status}`);
      const data = await res.json();
      updateStep(
        "ghostworker",
        "done",
        `${data.drafts_created} drafts ready for review`
      );
    } catch {
      updateStep("ghostworker", "error", "GhostWorker failed");
    }
  }

  async function triggerPlanDay() {
    updateStep("plan", "running", "Planning day...");
    try {
      const res = await fetch(`${API_URL}/api/schedule/plan-day`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ available_hours: 8 }),
      });
      if (!res.ok) throw new Error(`${res.status}`);
      const data = await res.json();
      updateStep("plan", "done", `Planned ${data.planned} tasks`);
    } catch {
      updateStep("plan", "error", "Plan failed");
    }
  }

  // ── Auto-run full demo sequence ───────────────────────────────────────

  async function runFullDemo() {
    setAutoRunning(true);
    setSteps({});

    // Step 1: Reset
    updateStep("auto-1", "running", "1/6 Resetting demo data...");
    try {
      await fetch(`${API_URL}/api/demo/reset`, { method: "POST" });
      updateStep("auto-1", "done", "1/6 Demo reset");
    } catch {
      updateStep("auto-1", "error", "Reset failed");
      setAutoRunning(false);
      return;
    }
    await sleep(2000);

    // Step 2: Meeting overrun disruption
    updateStep("auto-2", "running", "2/6 Study group extended 90min...");
    try {
      const res = await fetch(`${API_URL}/api/disruption`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          event_type: "meeting_overrun",
          source: "google_calendar",
          lost_minutes: 90,
          affected_task_ids: ["task-2", "task-3", "task-4", "task-5"],
          metadata: { meeting_title: "Study Group — CS 229" },
        }),
      });
      const data = await res.json();
      updateStep(
        "auto-2",
        "done",
        `2/6 ${data.severity} disruption — ${data.swaps?.length || 0} swaps`
      );
    } catch {
      updateStep("auto-2", "error", "Disruption failed");
    }
    await sleep(3000);

    // Step 3: GhostWorker drafts busywork
    updateStep("auto-3", "running", "3/6 GhostWorker drafting busywork...");
    try {
      const res = await fetch(`${API_URL}/api/demo/ghostworker`, {
        method: "POST",
      });
      const data = await res.json();
      updateStep(
        "auto-3",
        "done",
        `3/6 ${data.drafts_created} drafts created (review in right panel)`
      );
    } catch {
      updateStep("auto-3", "error", "GhostWorker failed");
    }
    await sleep(4000);

    // Step 4: Energy drops
    updateStep("auto-4", "running", "4/6 Energy crashing to 1...");
    try {
      await fetch(`${API_URL}/api/energy`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ level: 1 }),
      });
      updateStep("auto-4", "done", "4/6 Energy → 1 (P3 tasks auto-delegated)");
    } catch {
      updateStep("auto-4", "error", "Energy update failed");
    }
    await sleep(3000);

    // Step 5: Meeting ended early — freed time
    updateStep(
      "auto-5",
      "running",
      "5/6 Office hours cancelled — 60min freed..."
    );
    try {
      const res = await fetch(`${API_URL}/api/disruption`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          event_type: "cancelled_meeting",
          source: "google_calendar",
          freed_minutes: 60,
          affected_task_ids: ["task-5"],
          metadata: { meeting_title: "Office Hours — Prof. Ng" },
        }),
      });
      const data = await res.json();
      updateStep(
        "auto-5",
        "done",
        `5/6 +60min freed — ${data.swaps?.length || 0} tasks swapped in`
      );
    } catch {
      updateStep("auto-5", "error", "Disruption failed");
    }
    await sleep(3000);

    // Step 6: Recovery — energy back up
    updateStep("auto-6", "running", "6/6 Energy recovering to 4...");
    try {
      await fetch(`${API_URL}/api/energy`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ level: 4 }),
      });
      updateStep("auto-6", "done", "6/6 Energy → 4. Demo complete!");
    } catch {
      updateStep("auto-6", "error", "Energy update failed");
    }

    setAutoRunning(false);
  }

  // ── Render ────────────────────────────────────────────────────────────

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="fixed bottom-20 left-4 z-50 rounded-lg border border-violet-500/40 bg-violet-500/10 px-3 py-2 text-xs font-medium text-violet-300 backdrop-blur-sm hover:bg-violet-500/20 transition-colors"
      >
        Demo Controls
      </button>
    );
  }

  return (
    <div className="fixed bottom-20 left-4 z-50 w-80 rounded-xl border border-zinc-700 bg-zinc-900/95 backdrop-blur-md shadow-2xl">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-zinc-800 px-4 py-2.5">
        <span className="text-xs font-semibold text-violet-300">
          Demo Controls
        </span>
        <button
          onClick={() => setOpen(false)}
          className="text-zinc-500 hover:text-zinc-300 text-sm"
        >
          x
        </button>
      </div>

      <div className="p-3 space-y-3">
        {/* Auto-run */}
        <button
          onClick={runFullDemo}
          disabled={autoRunning}
          className="w-full rounded-lg border border-violet-500/40 bg-violet-500/15 px-3 py-2.5 text-xs font-semibold text-violet-200 hover:bg-violet-500/25 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {autoRunning ? "Running Demo..." : "Run Full Demo Sequence"}
        </button>

        <div className="border-t border-zinc-800 pt-2" />

        {/* Manual triggers */}
        <p className="text-[10px] font-semibold text-zinc-500 uppercase tracking-wider">
          Manual Triggers
        </p>

        <div className="grid grid-cols-2 gap-2">
          <DemoBtn
            label="Meeting Overrun"
            sub="-90min lost"
            color="orange"
            onClick={() =>
              triggerDisruption("meeting_overrun", 90, [
                "task-2",
                "task-3",
                "task-4",
                "task-5",
              ])
            }
          />
          <DemoBtn
            label="Meeting Cancelled"
            sub="+60min freed"
            color="green"
            onClick={() =>
              triggerDisruption("cancelled_meeting", 0, ["task-5"])
            }
          />
          <DemoBtn
            label="Urgent Email"
            sub="P0 arrives"
            color="red"
            onClick={() =>
              triggerDisruption("new_urgent_email", 30, ["task-6"])
            }
          />
          <DemoBtn
            label="GhostWorker"
            sub="Draft emails + Slack"
            color="purple"
            onClick={triggerGhostWorker}
          />
        </div>

        {/* Plan Day (full width) */}
        <button
          onClick={triggerPlanDay}
          className="w-full rounded-lg border border-cyan-500/30 bg-cyan-500/10 px-3 py-2 text-xs font-medium text-cyan-300 hover:bg-cyan-500/20 transition-colors"
        >
          Plan Day (LTS Recompute)
        </button>

        {/* Energy slider */}
        <div>
          <p className="text-[10px] font-semibold text-zinc-500 uppercase tracking-wider mb-1.5">
            Energy Level
          </p>
          <div className="flex gap-1.5">
            {[1, 2, 3, 4, 5].map((lvl) => (
              <button
                key={lvl}
                onClick={() => setEnergy(lvl)}
                className={`flex-1 rounded-md border py-1.5 text-[11px] font-medium transition-colors ${
                  lvl <= 2
                    ? "border-red-500/30 bg-red-500/10 text-red-300 hover:bg-red-500/20"
                    : lvl <= 3
                      ? "border-amber-500/30 bg-amber-500/10 text-amber-300 hover:bg-amber-500/20"
                      : "border-green-500/30 bg-green-500/10 text-green-300 hover:bg-green-500/20"
                }`}
              >
                {lvl}
              </button>
            ))}
          </div>
        </div>

        {/* Reset */}
        <button
          onClick={resetDemo}
          className="w-full rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2 text-xs text-zinc-400 hover:text-zinc-200 hover:bg-zinc-700 transition-colors"
        >
          Reset Demo (re-seed Sarah&apos;s schedule)
        </button>

        {/* Step log */}
        {Object.keys(steps).length > 0 && (
          <div className="max-h-32 overflow-y-auto space-y-1 border-t border-zinc-800 pt-2">
            {Object.entries(steps).map(([id, step]) => (
              <div key={id} className="flex items-center gap-2 text-[10px]">
                <span
                  className={
                    step.status === "running"
                      ? "text-yellow-400"
                      : step.status === "done"
                        ? "text-green-400"
                        : step.status === "error"
                          ? "text-red-400"
                          : "text-zinc-500"
                  }
                >
                  {step.status === "running"
                    ? "..."
                    : step.status === "done"
                      ? "OK"
                      : step.status === "error"
                        ? "ERR"
                        : "—"}
                </span>
                <span className="text-zinc-400">{step.label}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Helpers ─────────────────────────────────────────────────────────────

function DemoBtn({
  label,
  sub,
  color,
  onClick,
}: {
  label: string;
  sub: string;
  color: "orange" | "green" | "red" | "blue" | "purple";
  onClick: () => void;
}) {
  const colorMap = {
    orange: "border-orange-500/30 bg-orange-500/10 text-orange-300 hover:bg-orange-500/20",
    green: "border-green-500/30 bg-green-500/10 text-green-300 hover:bg-green-500/20",
    red: "border-red-500/30 bg-red-500/10 text-red-300 hover:bg-red-500/20",
    blue: "border-blue-500/30 bg-blue-500/10 text-blue-300 hover:bg-blue-500/20",
    purple: "border-purple-500/30 bg-purple-500/10 text-purple-300 hover:bg-purple-500/20",
  };

  return (
    <button
      onClick={onClick}
      className={`rounded-lg border px-2.5 py-2 text-left transition-colors ${colorMap[color]}`}
    >
      <p className="text-[11px] font-medium">{label}</p>
      <p className="text-[9px] opacity-60">{sub}</p>
    </button>
  );
}

function sleep(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
