"use client";

import type { AgentLogEntry } from "@/lib/useScheduleStore";

const TYPE_STYLES: Record<AgentLogEntry["type"], { dot: string; text: string }> = {
  info: { dot: "bg-zinc-500", text: "text-zinc-400" },
  disruption: { dot: "bg-red-500", text: "text-red-400" },
  swap: { dot: "bg-amber-500", text: "text-amber-400" },
  delegation: { dot: "bg-purple-500", text: "text-purple-400" },
  ghostworker: { dot: "bg-cyan-500", text: "text-cyan-400" },
};

function formatTimestamp(iso: string): string {
  return new Date(iso).toLocaleTimeString("en-US", {
    hour: "numeric",
    minute: "2-digit",
    second: "2-digit",
    hour12: true,
  });
}

interface AgentActivityLogProps {
  entries: AgentLogEntry[];
  onAction?: (actionId: string) => void;
}

export default function AgentActivityLog({ entries, onAction }: AgentActivityLogProps) {
  return (
    <div>
      <h2 className="text-sm font-semibold text-zinc-300 mb-3">
        Agent Activity
      </h2>

      {entries.length === 0 ? (
        <p className="text-xs text-zinc-600">
          No agent activity yet. Waiting for events...
        </p>
      ) : (
        <div className="space-y-2">
          {entries.map((entry) => {
            const style = TYPE_STYLES[entry.type];
            const isClickable = !!entry.actionId && !!onAction;

            return (
              <div
                key={entry.id}
                className={`flex gap-3 rounded-md bg-zinc-900 p-3 text-xs ${
                  isClickable
                    ? "cursor-pointer ring-1 ring-cyan-500/30 hover:ring-cyan-500/60 hover:bg-zinc-800/80 transition-all"
                    : ""
                }`}
                onClick={isClickable ? () => onAction(entry.actionId!) : undefined}
              >
                <div className={`mt-1 h-2 w-2 shrink-0 rounded-full ${style.dot} ${isClickable ? "animate-pulse" : ""}`} />
                <div className="min-w-0 flex-1">
                  <div className="flex items-center justify-between gap-2">
                    <span className={`font-medium ${style.text}`}>
                      {entry.agent}
                    </span>
                    <span className="text-zinc-600 tabular-nums shrink-0">
                      {formatTimestamp(entry.timestamp)}
                    </span>
                  </div>
                  <p className="mt-0.5 text-zinc-400 break-words">
                    {entry.message}
                  </p>
                  {isClickable && entry.actionLabel && (
                    <span className="mt-1.5 inline-block rounded-md bg-cyan-500/10 border border-cyan-500/30 px-2 py-0.5 text-[10px] font-medium text-cyan-400">
                      {entry.actionLabel}
                    </span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
