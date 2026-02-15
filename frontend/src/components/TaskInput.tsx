"use client";

import { useState } from "react";
import { API_URL } from "@/lib/constants";

const PRIORITY_OPTIONS = [
  { value: 0, label: "P0", color: "bg-red-500", activeColor: "bg-red-500 ring-red-400" },
  { value: 1, label: "P1", color: "bg-orange-500", activeColor: "bg-orange-500 ring-orange-400" },
  { value: 2, label: "P2", color: "bg-blue-500", activeColor: "bg-blue-500 ring-blue-400" },
  { value: 3, label: "P3", color: "bg-zinc-500", activeColor: "bg-zinc-500 ring-zinc-400" },
];

const DURATION_PRESETS = [
  { label: "15m", value: 15 },
  { label: "30m", value: 30 },
  { label: "1h", value: 60 },
  { label: "2h", value: 120 },
];

interface TaskInputProps {
  onTaskAdded?: () => void;
}

export default function TaskInput({ onTaskAdded }: TaskInputProps) {
  const [title, setTitle] = useState("");
  const [expanded, setExpanded] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  // Expanded fields
  const [description, setDescription] = useState("");
  const [priority, setPriority] = useState(2);
  const [duration, setDuration] = useState(30);
  const [energyCost, setEnergyCost] = useState(3);
  const [scheduledDate, setScheduledDate] = useState("");
  const [scheduledTime, setScheduledTime] = useState("");
  const [deadlineDate, setDeadlineDate] = useState("");
  const [deadlineTime, setDeadlineTime] = useState("");

  const resetForm = () => {
    setTitle("");
    setDescription("");
    setPriority(2);
    setDuration(30);
    setEnergyCost(3);
    setScheduledDate("");
    setScheduledTime("");
    setDeadlineDate("");
    setDeadlineTime("");
    setExpanded(false);
  };

  const combineDatetime = (date: string, time: string) => {
    if (!date) return "";
    // If no time provided, default to start of day
    const t = time || "09:00";
    return `${date}T${t}:00`;
  };

  const handleSubmit = async () => {
    if (!title.trim() || submitting) return;
    setSubmitting(true);

    try {
      const res = await fetch(`${API_URL}/api/tasks`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: title.trim(),
          description,
          priority,
          estimated_duration: duration,
          energy_cost: energyCost,
          preferred_start: combineDatetime(scheduledDate, scheduledTime),
          deadline: combineDatetime(deadlineDate, deadlineTime),
        }),
      });
      const data = await res.json();
      if (data.successful) {
        resetForm();
        onTaskAdded?.();
      }
    } catch {
      // WS will handle the update
    } finally {
      setSubmitting(false);
    }
  };

  const inputClass =
    "bg-zinc-900/50 rounded-lg border border-zinc-700 px-2 py-1 text-[10px] text-zinc-400 outline-none";

  return (
    <div className="rounded-xl border border-zinc-700 bg-zinc-800/50 p-3 mb-3">
      {/* Quick-add row */}
      <div className="flex items-center gap-2">
        <input
          type="text"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              handleSubmit();
            }
          }}
          placeholder="Add a task..."
          className="flex-1 bg-transparent text-sm text-zinc-200 placeholder:text-zinc-600 outline-none"
        />
        <button
          onClick={() => setExpanded(!expanded)}
          className="p-1 text-zinc-500 hover:text-zinc-300 transition-colors"
          title={expanded ? "Collapse" : "More options"}
        >
          <svg
            width="16"
            height="16"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            className={`transition-transform ${expanded ? "rotate-180" : ""}`}
          >
            <path d="M6 9l6 6 6-6" />
          </svg>
        </button>
        <button
          onClick={handleSubmit}
          disabled={!title.trim() || submitting}
          className="rounded-lg bg-blue-600 px-3 py-1 text-xs font-medium text-white hover:bg-blue-500 transition-colors disabled:opacity-40"
        >
          {submitting ? "..." : "Add"}
        </button>
      </div>

      {/* Expanded options */}
      {expanded && (
        <div className="mt-3 space-y-3 border-t border-zinc-700 pt-3">
          {/* Description */}
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Description (optional)"
            rows={2}
            className="w-full bg-zinc-900/50 rounded-lg border border-zinc-700 px-3 py-2 text-xs text-zinc-300 placeholder:text-zinc-600 outline-none resize-none"
          />

          {/* Priority */}
          <div className="flex items-center gap-2">
            <span className="text-[10px] text-zinc-500 w-14">Priority</span>
            <div className="flex gap-1.5">
              {PRIORITY_OPTIONS.map((p) => (
                <button
                  key={p.value}
                  onClick={() => setPriority(p.value)}
                  className={`px-2 py-0.5 rounded text-[10px] font-medium transition-all ${
                    priority === p.value
                      ? `${p.activeColor} text-white ring-1`
                      : "bg-zinc-800 text-zinc-500 hover:text-zinc-300"
                  }`}
                >
                  {p.label}
                </button>
              ))}
            </div>
          </div>

          {/* Duration */}
          <div className="flex items-center gap-2">
            <span className="text-[10px] text-zinc-500 w-14">Duration</span>
            <div className="flex gap-1.5">
              {DURATION_PRESETS.map((d) => (
                <button
                  key={d.value}
                  onClick={() => setDuration(d.value)}
                  className={`px-2 py-0.5 rounded text-[10px] transition-all ${
                    duration === d.value
                      ? "bg-blue-600 text-white"
                      : "bg-zinc-800 text-zinc-500 hover:text-zinc-300"
                  }`}
                >
                  {d.label}
                </button>
              ))}
            </div>
          </div>

          {/* Energy Cost */}
          <div className="flex items-center gap-2">
            <span className="text-[10px] text-zinc-500 w-14">Energy</span>
            <div className="flex gap-1">
              {[1, 2, 3, 4, 5].map((e) => (
                <button
                  key={e}
                  onClick={() => setEnergyCost(e)}
                  className={`h-3 w-3 rounded-full transition-all ${
                    e <= energyCost
                      ? "bg-amber-400"
                      : "bg-zinc-700 hover:bg-zinc-600"
                  }`}
                  title={`Energy: ${e}/5`}
                />
              ))}
              <span className="text-[10px] text-zinc-500 ml-1">{energyCost}/5</span>
            </div>
          </div>

          {/* Scheduled Time */}
          <div className="flex items-center gap-2">
            <span className="text-[10px] text-zinc-500 w-14">Scheduled</span>
            <input
              type="date"
              value={scheduledDate}
              onChange={(e) => setScheduledDate(e.target.value)}
              className={inputClass}
            />
            <input
              type="time"
              value={scheduledTime}
              onChange={(e) => setScheduledTime(e.target.value)}
              className={inputClass}
            />
            {(scheduledDate || scheduledTime) && (
              <button
                onClick={() => { setScheduledDate(""); setScheduledTime(""); }}
                className="text-[10px] text-zinc-600 hover:text-zinc-400"
              >
                clear
              </button>
            )}
          </div>

          {/* Deadline */}
          <div className="flex items-center gap-2">
            <span className="text-[10px] text-zinc-500 w-14">Deadline</span>
            <input
              type="date"
              value={deadlineDate}
              onChange={(e) => setDeadlineDate(e.target.value)}
              className={inputClass}
            />
            <input
              type="time"
              value={deadlineTime}
              onChange={(e) => setDeadlineTime(e.target.value)}
              className={inputClass}
            />
            {(deadlineDate || deadlineTime) && (
              <button
                onClick={() => { setDeadlineDate(""); setDeadlineTime(""); }}
                className="text-[10px] text-zinc-600 hover:text-zinc-400"
              >
                clear
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
