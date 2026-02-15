"use client";

import { useState, useRef, useEffect } from "react";
import {
  useElevenLabsAgent,
  type AgentStatus,
  type TranscriptEntry,
} from "@/lib/useElevenLabsAgent";

// ── Status config ────────────────────────────────────────────────────────

const STATUS_CONFIG: Record<
  AgentStatus,
  { label: string; ring: string; bg: string; pulse: boolean }
> = {
  disconnected: {
    label: "Start voice agent",
    ring: "ring-zinc-600",
    bg: "bg-zinc-800 hover:bg-zinc-700",
    pulse: false,
  },
  connecting: {
    label: "Connecting…",
    ring: "ring-yellow-500/50",
    bg: "bg-yellow-900/30",
    pulse: true,
  },
  connected: {
    label: "Connected",
    ring: "ring-green-500/50",
    bg: "bg-green-900/30",
    pulse: false,
  },
  listening: {
    label: "Listening…",
    ring: "ring-green-500",
    bg: "bg-green-900/40",
    pulse: true,
  },
  speaking: {
    label: "Agent speaking…",
    ring: "ring-cyan-500",
    bg: "bg-cyan-900/40",
    pulse: true,
  },
};

// ── Component ────────────────────────────────────────────────────────────

interface VoiceAgentProps {
  draftIds?: string[];
}

export default function VoiceAgent({ draftIds }: VoiceAgentProps) {
  const [isOpen, setIsOpen] = useState(false);
  const transcriptEndRef = useRef<HTMLDivElement>(null);

  const { status, transcript, error, startSession, endSession, clearTranscript } =
    useElevenLabsAgent({ draftIds });

  const config = STATUS_CONFIG[status];
  const isActive = status !== "disconnected";

  // Auto-scroll transcript
  useEffect(() => {
    transcriptEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [transcript]);

  const handleToggle = async () => {
    if (isActive) {
      await endSession();
    } else {
      await startSession();
    }
  };

  return (
    <>
      {/* ── Expanded panel ─────────────────────────────────────────────── */}
      {isOpen && (
        <div className="fixed bottom-20 right-6 z-50 w-80 max-h-[60vh] flex flex-col rounded-2xl border border-zinc-800 bg-zinc-950 shadow-2xl shadow-black/50 overflow-hidden">
          {/* Header */}
          <div className="flex items-center justify-between border-b border-zinc-800 px-4 py-3">
            <div className="flex items-center gap-2">
              <div
                className={`h-2 w-2 rounded-full ${
                  isActive ? "bg-green-500" : "bg-zinc-600"
                } ${config.pulse ? "animate-pulse" : ""}`}
              />
              <span className="text-xs font-medium text-zinc-300">
                Voice Agent
              </span>
              <span className="text-[10px] text-zinc-600">{config.label}</span>
            </div>
            <button
              onClick={() => setIsOpen(false)}
              className="text-zinc-500 hover:text-zinc-300 transition-colors"
              aria-label="Minimize"
            >
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                <path
                  d="M3 7h8"
                  stroke="currentColor"
                  strokeWidth="1.5"
                  strokeLinecap="round"
                />
              </svg>
            </button>
          </div>

          {/* Transcript */}
          <div className="flex-1 overflow-y-auto p-3 space-y-2 min-h-[120px] max-h-[40vh]">
            {transcript.length === 0 && !error && (
              <p className="text-xs text-zinc-600 text-center py-8">
                {isActive
                  ? "Listening… say something to your Rewind agent."
                  : "Click the mic button to start a voice conversation."}
              </p>
            )}

            {error && (
              <div className="rounded-lg border border-red-500/20 bg-red-500/5 px-3 py-2">
                <p className="text-xs text-red-400">{error}</p>
              </div>
            )}

            {transcript.map((entry) => (
              <TranscriptBubble key={entry.id} entry={entry} />
            ))}
            <div ref={transcriptEndRef} />
          </div>

          {/* Actions */}
          <div className="flex items-center gap-2 border-t border-zinc-800 px-4 py-3">
            <button
              onClick={handleToggle}
              className={`flex-1 rounded-lg px-3 py-2 text-xs font-medium transition-colors ${
                isActive
                  ? "bg-red-600 hover:bg-red-500 text-white"
                  : "bg-green-600 hover:bg-green-500 text-white"
              }`}
            >
              {isActive ? "End Conversation" : "Start Conversation"}
            </button>
            {transcript.length > 0 && (
              <button
                onClick={clearTranscript}
                className="rounded-lg border border-zinc-700 px-3 py-2 text-xs text-zinc-500 hover:text-zinc-300 transition-colors"
              >
                Clear
              </button>
            )}
          </div>
        </div>
      )}

      {/* ── Floating mic button ────────────────────────────────────────── */}
      <button
        onClick={() => {
          if (!isOpen) {
            setIsOpen(true);
          } else if (!isActive) {
            // If panel open but not active, toggle panel
            setIsOpen(false);
          } else {
            // If active, bring panel up
            setIsOpen(true);
          }
        }}
        className={`fixed bottom-6 right-6 z-50 flex h-14 w-14 items-center justify-center rounded-full shadow-lg transition-all ring-2 ${config.ring} ${config.bg}`}
        aria-label={config.label}
        title={config.label}
      >
        {/* Pulse ring animation when active */}
        {isActive && (
          <span className="absolute inset-0 rounded-full animate-ping opacity-20 bg-green-500" />
        )}

        {/* Mic icon */}
        <svg
          width="22"
          height="22"
          viewBox="0 0 24 24"
          fill="none"
          className={`relative z-10 ${
            isActive ? "text-white" : "text-zinc-400"
          }`}
        >
          {isActive ? (
            // Active mic icon (filled)
            <>
              <path
                d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3Z"
                fill="currentColor"
              />
              <path
                d="M19 10v2a7 7 0 0 1-14 0v-2"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
              />
              <path
                d="M12 19v4m-4 0h8"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
              />
            </>
          ) : (
            // Idle mic icon (outline)
            <>
              <path
                d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3Z"
                stroke="currentColor"
                strokeWidth="2"
              />
              <path
                d="M19 10v2a7 7 0 0 1-14 0v-2"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
              />
              <path
                d="M12 19v4m-4 0h8"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
              />
            </>
          )}
        </svg>
      </button>
    </>
  );
}

// ── Transcript bubble ───────────────────────────────────────────────────

function TranscriptBubble({ entry }: { entry: TranscriptEntry }) {
  const isUser = entry.role === "user";

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[85%] rounded-xl px-3 py-2 text-xs leading-relaxed ${
          isUser
            ? "bg-blue-600/20 text-blue-200 rounded-br-sm"
            : "bg-zinc-800 text-zinc-300 rounded-bl-sm"
        }`}
      >
        <span className="block text-[10px] font-medium mb-0.5 opacity-60">
          {isUser ? "You" : "Rewind Agent"}
        </span>
        {entry.text}
      </div>
    </div>
  );
}
