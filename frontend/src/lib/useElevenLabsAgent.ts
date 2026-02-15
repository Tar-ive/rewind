"use client";

import { useConversation } from "@elevenlabs/react";
import { useCallback, useState, useRef } from "react";
import { API_URL } from "@/lib/constants";

// ── Types ────────────────────────────────────────────────────────────────

export type AgentStatus = "disconnected" | "connecting" | "connected" | "speaking" | "listening";

export interface TranscriptEntry {
  id: string;
  role: "user" | "agent";
  text: string;
  timestamp: string;
}

interface UseElevenLabsAgentOptions {
  /** Current draft IDs so the agent can reference them */
  draftIds?: string[];
}

// ── Hook ─────────────────────────────────────────────────────────────────

export function useElevenLabsAgent(options: UseElevenLabsAgentOptions = {}) {
  const [agentStatus, setAgentStatus] = useState<AgentStatus>("disconnected");
  const [transcript, setTranscript] = useState<TranscriptEntry[]>([]);
  const [error, setError] = useState<string | null>(null);
  const draftIdsRef = useRef<string[]>(options.draftIds ?? []);
  draftIdsRef.current = options.draftIds ?? [];

  // ── Helper: add transcript entry ──────────────────────────────────────

  const addTranscript = useCallback(
    (role: "user" | "agent", text: string) => {
      setTranscript((prev) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          role,
          text,
          timestamp: new Date().toISOString(),
        },
      ]);
    },
    []
  );

  // ── Client tool implementations ───────────────────────────────────────

  const clientTools = {
    plan_day: async (params: { available_hours?: number }) => {
      try {
        const res = await fetch(`${API_URL}/api/schedule/plan-day`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            available_hours: params.available_hours ?? 8,
          }),
        });
        const data = await res.json();
        return `Planned ${data.planned} tasks for today.`;
      } catch {
        return "Failed to trigger daily planning.";
      }
    },

    get_schedule: async () => {
      try {
        const res = await fetch(`${API_URL}/api/schedule`);
        const data = await res.json();
        const summary = (data.tasks ?? [])
          .map(
            (t: { title: string; priority: string; status: string; estimated_duration: number }) =>
              `${t.priority} ${t.title} (${t.status}, ${t.estimated_duration}min)`
          )
          .join("; ");
        return summary || "No active tasks.";
      } catch {
        return "Failed to fetch schedule.";
      }
    },

    simulate_disruption: async (params: {
      event_type?: string;
      source?: string;
      freed_minutes?: number;
      lost_minutes?: number;
    }) => {
      try {
        const res = await fetch(`${API_URL}/api/disruption`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            event_type: params.event_type ?? "meeting_overrun",
            source: params.source ?? "voice_command",
            affected_task_ids: [],
            freed_minutes: params.freed_minutes,
            lost_minutes: params.lost_minutes,
          }),
        });
        const data = await res.json();
        return `Disruption processed: ${data.severity} severity. ${data.summary}`;
      } catch {
        return "Failed to simulate disruption.";
      }
    },

    update_energy: async (params: { level: number }) => {
      try {
        const level = Math.max(1, Math.min(5, params.level));
        const res = await fetch(`${API_URL}/api/energy`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ level }),
        });
        const data = await res.json();
        const delegated = data.delegated?.length ?? 0;
        return `Energy updated to ${data.energy_level}/5.${delegated > 0 ? ` ${delegated} tasks auto-delegated.` : ""}`;
      } catch {
        return "Failed to update energy level.";
      }
    },

    approve_draft: async (params: { draft_id: string }) => {
      try {
        const res = await fetch(
          `${API_URL}/api/ghostworker/drafts/${params.draft_id}/approve`,
          { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({}) }
        );
        const data = await res.json();
        return data.status === "approval_sent"
          ? `Draft ${params.draft_id} approved and sent.`
          : `Approval failed: ${JSON.stringify(data)}`;
      } catch {
        return "Failed to approve draft.";
      }
    },

    reject_draft: async (params: { draft_id: string }) => {
      try {
        await fetch(
          `${API_URL}/api/ghostworker/drafts/${params.draft_id}/reject`,
          { method: "POST" }
        );
        return `Draft ${params.draft_id} rejected.`;
      } catch {
        return "Failed to reject draft.";
      }
    },

    get_drafts: async () => {
      try {
        const res = await fetch(`${API_URL}/api/ghostworker/drafts`);
        const data = await res.json();
        if (!data.drafts || data.drafts.length === 0) return "No pending drafts.";
        const summary = data.drafts
          .map(
            (d: { id: string; task_type: string; subject?: string }) =>
              `${d.id}: ${d.task_type}${d.subject ? ` — ${d.subject}` : ""}`
          )
          .join("; ");
        return `${data.drafts.length} pending draft(s): ${summary}`;
      } catch {
        return "Failed to fetch drafts.";
      }
    },
  };

  // ── ElevenLabs conversation hook ──────────────────────────────────────

  const conversation = useConversation({
    onConnect: () => {
      setAgentStatus("connected");
      setError(null);
    },
    onDisconnect: () => {
      setAgentStatus("disconnected");
    },
    onMessage: (message) => {
      // Handle transcript messages from the agent
      if (message && typeof message === "object") {
        const msg = message as unknown as Record<string, unknown>;
        if (msg.type === "user_transcript" || msg.source === "user") {
          addTranscript("user", String(msg.message ?? msg.text ?? ""));
        } else if (msg.type === "agent_response" || msg.source === "ai") {
          addTranscript("agent", String(msg.message ?? msg.text ?? ""));
        }
      }
    },
    onError: (error) => {
      console.error("ElevenLabs error:", error);
      setError(typeof error === "string" ? error : "Voice agent error");
      setAgentStatus("disconnected");
    },
    clientTools,
  });

  // ── Start session ─────────────────────────────────────────────────────

  const startSession = useCallback(async () => {
    setAgentStatus("connecting");
    setError(null);
    setTranscript([]);

    try {
      // Get signed URL from our backend
      const res = await fetch(`${API_URL}/api/elevenlabs/signed-url`);
      const data = await res.json();

      if (data.error) {
        setError(data.error);
        setAgentStatus("disconnected");
        return;
      }

      // Start ElevenLabs conversation with signed URL
      await conversation.startSession({
        signedUrl: data.signed_url,
      });
    } catch (err) {
      console.error("Failed to start ElevenLabs session:", err);
      setError("Failed to connect to voice agent");
      setAgentStatus("disconnected");
    }
  }, [conversation]);

  // ── End session ───────────────────────────────────────────────────────

  const endSession = useCallback(async () => {
    try {
      await conversation.endSession();
    } catch {
      // Ignore errors on disconnect
    }
    setAgentStatus("disconnected");
  }, [conversation]);

  // ── Derived status based on conversation.isSpeaking ────────────────────

  const derivedStatus: AgentStatus =
    agentStatus === "connected"
      ? conversation.isSpeaking
        ? "speaking"
        : "listening"
      : agentStatus;

  return {
    status: derivedStatus,
    transcript,
    error,
    startSession,
    endSession,
    clearTranscript: () => setTranscript([]),
  };
}
