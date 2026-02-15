"use client";

import { useState } from "react";
import type { Priority } from "@/types/schedule";
import { PRIORITY_CONFIG } from "@/lib/constants";

interface TaskInputFormProps {
  onSubmit: (task: {
    title: string;
    description: string;
    priority: Priority;
    estimated_duration: number;
    deadline: string;
    energy_cost: number;
  }) => void;
  onClose: () => void;
}

export default function TaskInputForm({ onSubmit, onClose }: TaskInputFormProps) {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [priority, setPriority] = useState<Priority>("P2");
  const [duration, setDuration] = useState(30);
  const [deadline, setDeadline] = useState("");
  const [energyCost, setEnergyCost] = useState(2);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim()) return;
    onSubmit({
      title: title.trim(),
      description: description.trim(),
      priority,
      estimated_duration: duration,
      deadline,
      energy_cost: energyCost,
    });
    setTitle("");
    setDescription("");
    setPriority("P2");
    setDuration(30);
    setDeadline("");
    setEnergyCost(2);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <form
        onSubmit={handleSubmit}
        className="w-full max-w-md rounded-xl border border-zinc-800 bg-zinc-900 p-5 shadow-2xl"
      >
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-semibold text-zinc-200">Add Task</h3>
          <button
            type="button"
            onClick={onClose}
            className="text-zinc-500 hover:text-zinc-300 text-lg leading-none"
          >
            &times;
          </button>
        </div>

        {/* Title */}
        <input
          type="text"
          placeholder="Task title..."
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          className="w-full rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2 text-sm text-zinc-100 placeholder:text-zinc-600 focus:border-zinc-600 focus:outline-none mb-3"
          autoFocus
        />

        {/* Description */}
        <textarea
          placeholder="Description (optional)"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          rows={2}
          className="w-full rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2 text-sm text-zinc-100 placeholder:text-zinc-600 focus:border-zinc-600 focus:outline-none mb-3 resize-none"
        />

        {/* Priority */}
        <div className="mb-3">
          <label className="text-[11px] text-zinc-500 uppercase tracking-wider mb-1.5 block">
            Priority
          </label>
          <div className="flex gap-2">
            {(["P0", "P1", "P2", "P3"] as Priority[]).map((p) => {
              const config = PRIORITY_CONFIG[p];
              return (
                <button
                  key={p}
                  type="button"
                  onClick={() => setPriority(p)}
                  className={`flex-1 rounded-md border px-2 py-1.5 text-xs font-medium transition-colors ${
                    priority === p
                      ? `${config.bg} ${config.border} ${config.color}`
                      : "border-zinc-700 text-zinc-500 hover:border-zinc-600"
                  }`}
                >
                  {p}
                </button>
              );
            })}
          </div>
        </div>

        {/* Duration & Energy row */}
        <div className="flex gap-3 mb-3">
          <div className="flex-1">
            <label className="text-[11px] text-zinc-500 uppercase tracking-wider mb-1.5 block">
              Duration (min)
            </label>
            <input
              type="number"
              min={5}
              max={480}
              step={5}
              value={duration}
              onChange={(e) => setDuration(Number(e.target.value))}
              className="w-full rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2 text-sm text-zinc-100 focus:border-zinc-600 focus:outline-none"
            />
          </div>
          <div className="flex-1">
            <label className="text-[11px] text-zinc-500 uppercase tracking-wider mb-1.5 block">
              Energy Cost
            </label>
            <div className="flex gap-1 pt-1.5">
              {[1, 2, 3, 4, 5].map((level) => (
                <button
                  key={level}
                  type="button"
                  onClick={() => setEnergyCost(level)}
                  className={`h-6 flex-1 rounded transition-colors ${
                    level <= energyCost ? "bg-amber-400" : "bg-zinc-700"
                  }`}
                />
              ))}
            </div>
          </div>
        </div>

        {/* Deadline */}
        <div className="mb-4">
          <label className="text-[11px] text-zinc-500 uppercase tracking-wider mb-1.5 block">
            Deadline
          </label>
          <input
            type="datetime-local"
            value={deadline}
            onChange={(e) => setDeadline(e.target.value)}
            className="w-full rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2 text-sm text-zinc-100 focus:border-zinc-600 focus:outline-none [color-scheme:dark]"
          />
        </div>

        {/* Actions */}
        <div className="flex gap-2">
          <button
            type="button"
            onClick={onClose}
            className="flex-1 rounded-lg border border-zinc-700 px-3 py-2 text-sm text-zinc-400 hover:bg-zinc-800 transition-colors"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={!title.trim()}
            className="flex-1 rounded-lg bg-white px-3 py-2 text-sm font-medium text-zinc-900 hover:bg-zinc-200 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          >
            Add Task
          </button>
        </div>
      </form>
    </div>
  );
}
