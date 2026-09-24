"use client";

import { useEffect, useState, useCallback } from "react";
import { API_URL } from "@/lib/constants";

// ── Service definitions ────────────────────────────────────────────────

interface ServiceConfig {
  toolkit: string;
  name: string;
  description: string;
  accent: string;
  connectedAccent: string;
  icon: React.ReactNode;
}

const SERVICES: ServiceConfig[] = [
  {
    toolkit: "calendar",
    name: "Google Calendar",
    description:
      "Sync calendar events, get proactive reminders about upcoming tasks and meetings.",
    accent: "border-blue-500/30 bg-blue-500/5",
    connectedAccent: "border-green-500/30 bg-green-500/5",
    icon: (
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#60a5fa" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <rect x="3" y="4" width="18" height="18" rx="2" />
        <path d="M16 2v4M8 2v4M3 10h18M8 14h.01M12 14h.01M16 14h.01M8 18h.01M12 18h.01" />
      </svg>
    ),
  },
  {
    toolkit: "gmail",
    name: "Gmail",
    description:
      "Read emails and let GhostWorker draft & send replies on your behalf.",
    accent: "border-red-500/30 bg-red-500/5",
    connectedAccent: "border-green-500/30 bg-green-500/5",
    icon: (
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#f87171" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <rect x="2" y="4" width="20" height="16" rx="2" />
        <path d="M22 7l-10 7L2 7" />
      </svg>
    ),
  },
  {
    toolkit: "slack",
    name: "Slack",
    description:
      "Send Slack messages autonomously when tasks are delegated to GhostWorker.",
    accent: "border-purple-500/30 bg-purple-500/5",
    connectedAccent: "border-green-500/30 bg-green-500/5",
    icon: (
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#a78bfa" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <path d="M14.5 2a2.5 2.5 0 0 0 0 5H17V4.5A2.5 2.5 0 0 0 14.5 2z" />
        <path d="M2 14.5a2.5 2.5 0 0 0 5 0V12H4.5A2.5 2.5 0 0 0 2 14.5z" />
        <path d="M22 9.5a2.5 2.5 0 0 0-5 0V12h2.5A2.5 2.5 0 0 0 22 9.5z" />
        <path d="M9.5 22a2.5 2.5 0 0 0 0-5H7v2.5A2.5 2.5 0 0 0 9.5 22z" />
      </svg>
    ),
  },
  {
    toolkit: "linkedin",
    name: "LinkedIn",
    description:
      "Monitor your professional network and auto-publish posts via GhostWorker.",
    accent: "border-cyan-500/30 bg-cyan-500/5",
    connectedAccent: "border-green-500/30 bg-green-500/5",
    icon: (
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#22d3ee" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <path d="M16 8a6 6 0 0 1 6 6v7h-4v-7a2 2 0 0 0-4 0v7h-4v-7a6 6 0 0 1 6-6z" />
        <rect x="2" y="9" width="4" height="12" />
        <circle cx="4" cy="4" r="2" />
      </svg>
    ),
  },
];

// Composio returns app slugs that differ from our toolkit keys
const COMPOSIO_APP_SLUGS: Record<string, string[]> = {
  calendar: ["googlecalendar"],
  gmail: ["gmail"],
  slack: ["slack"],
  linkedin: ["linkedin"],
};

// ── Types ──────────────────────────────────────────────────────────────

interface Connection {
  id: string;
  app: string;
  status: string;
  created_at?: string;
}

type UIStatus = "connected" | "disconnected" | "connecting" | "disconnecting";

interface ServiceState {
  toolkit: string;
  status: UIStatus;
  connections: Connection[]; // all active connections for this toolkit
}

// ── Component ──────────────────────────────────────────────────────────

export default function IntegrationsPage() {
  const [services, setServices] = useState<ServiceState[]>(
    SERVICES.map((s) => ({ toolkit: s.toolkit, status: "disconnected", connections: [] }))
  );
  const [loading, setLoading] = useState(true);

  const fetchStatus = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/auth/status`);
      const data = await res.json();
      const connections: Connection[] = data.connections ?? [];

      setServices(
        SERVICES.map((s) => {
          const slugs = COMPOSIO_APP_SLUGS[s.toolkit] ?? [s.toolkit];
          const matching = connections.filter(
            (c) => slugs.includes(c.app) && c.status === "ACTIVE"
          );
          return {
            toolkit: s.toolkit,
            status: matching.length > 0 ? "connected" : "disconnected",
            connections: matching,
          };
        })
      );
    } catch {
      // Keep current state on error
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchStatus();
  }, [fetchStatus]);

  // Re-fetch when tab regains focus (user returning from OAuth)
  useEffect(() => {
    const handleVisibility = () => {
      if (document.visibilityState === "visible") fetchStatus();
    };
    document.addEventListener("visibilitychange", handleVisibility);
    return () => document.removeEventListener("visibilitychange", handleVisibility);
  }, [fetchStatus]);

  const handleConnect = async (toolkit: string) => {
    setServices((prev) =>
      prev.map((s) => (s.toolkit === toolkit ? { ...s, status: "connecting" } : s))
    );

    try {
      const callbackUrl = `${window.location.origin}/auth/callback`;
      const res = await fetch(`${API_URL}/api/auth/connect`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ toolkit, callback_url: callbackUrl }),
      });
      const data = await res.json();

      if (data.redirect_url) {
        window.open(data.redirect_url, "_blank");
      } else {
        const errMsg = data.error || "No redirect URL returned";
        alert(`Connection failed: ${errMsg}`);
        await fetchStatus();
      }
    } catch (err) {
      console.error("Failed to initiate connection:", err);
      setServices((prev) =>
        prev.map((s) =>
          s.toolkit === toolkit ? { ...s, status: "disconnected" } : s
        )
      );
    }
  };

  const handleDisconnect = async (toolkit: string) => {
    const svc = services.find((s) => s.toolkit === toolkit);
    if (!svc || svc.connections.length === 0) return;

    setServices((prev) =>
      prev.map((s) => (s.toolkit === toolkit ? { ...s, status: "disconnecting" } : s))
    );

    try {
      // Disconnect all connections for this toolkit
      await Promise.all(
        svc.connections.map((conn) =>
          fetch(`${API_URL}/api/auth/disconnect`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ connection_id: conn.id }),
          })
        )
      );
      // Refresh status
      await fetchStatus();
    } catch (err) {
      console.error("Failed to disconnect:", err);
      await fetchStatus();
    }
  };

  function formatDate(iso?: string) {
    if (!iso) return "";
    return new Date(iso).toLocaleDateString([], {
      month: "short",
      day: "numeric",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <header className="border-b border-zinc-800 px-6 py-5">
        <h1 className="text-lg font-semibold text-white">Integrations</h1>
        <p className="mt-1 text-sm text-zinc-500">
          Connect your accounts to enable GhostWorker automation, calendar sync,
          and proactive reminders.
        </p>
      </header>

      {/* Cards grid */}
      <div className="flex-1 overflow-y-auto p-6">
        {loading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {Array.from({ length: 4 }, (_, i) => (
              <div
                key={i}
                className="h-36 animate-pulse rounded-xl border border-zinc-800 bg-zinc-800/50"
              />
            ))}
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {SERVICES.map((svc) => {
              const state = services.find((s) => s.toolkit === svc.toolkit)!;
              const isConnected = state.status === "connected";
              const isConnecting = state.status === "connecting";
              const isDisconnecting = state.status === "disconnecting";

              return (
                <div
                  key={svc.toolkit}
                  className={`rounded-xl border p-5 transition-colors ${
                    isConnected ? svc.connectedAccent : svc.accent
                  }`}
                >
                  {/* Top row */}
                  <div className="flex items-start justify-between">
                    <div className="flex items-center gap-3">
                      <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-zinc-800/80">
                        {svc.icon}
                      </div>
                      <div>
                        <h3 className="text-sm font-semibold text-white">
                          {svc.name}
                        </h3>
                        <div className="flex items-center gap-1.5 mt-0.5">
                          <div
                            className={`h-1.5 w-1.5 rounded-full ${
                              isConnected ? "bg-green-500" : "bg-zinc-600"
                            }`}
                          />
                          <span
                            className={`text-[10px] ${
                              isConnected ? "text-green-400" : "text-zinc-500"
                            }`}
                          >
                            {isConnected
                              ? `Connected (${state.connections.length})`
                              : "Not connected"}
                          </span>
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Description */}
                  <p className="mt-3 text-xs text-zinc-400 leading-relaxed">
                    {svc.description}
                  </p>

                  {/* Connection details */}
                  {isConnected && state.connections.length > 0 && (
                    <div className="mt-3 space-y-1">
                      {state.connections.map((conn) => (
                        <div
                          key={conn.id}
                          className="flex items-center justify-between text-[10px] text-zinc-500 bg-zinc-800/50 rounded-lg px-2.5 py-1.5"
                        >
                          <span className="font-mono">{conn.id}</span>
                          {conn.created_at && (
                            <span>{formatDate(conn.created_at)}</span>
                          )}
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Actions */}
                  <div className="mt-4 flex gap-2">
                    {isConnected ? (
                      <>
                        <button
                          className="rounded-lg border border-red-500/30 px-3 py-1.5 text-xs text-red-400 hover:bg-red-500/10 transition-colors disabled:opacity-50"
                          onClick={() => handleDisconnect(svc.toolkit)}
                          disabled={isDisconnecting}
                        >
                          {isDisconnecting ? (
                            <span className="flex items-center gap-1.5">
                              <Spinner />
                              Disconnecting...
                            </span>
                          ) : (
                            "Disconnect"
                          )}
                        </button>
                        <button
                          className="rounded-lg border border-zinc-700 px-3 py-1.5 text-xs text-zinc-400 hover:bg-zinc-800 transition-colors"
                          onClick={() => handleConnect(svc.toolkit)}
                        >
                          Reconnect
                        </button>
                      </>
                    ) : (
                      <button
                        className="rounded-lg bg-blue-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-blue-500 transition-colors disabled:opacity-50"
                        onClick={() => handleConnect(svc.toolkit)}
                        disabled={isConnecting}
                      >
                        {isConnecting ? (
                          <span className="flex items-center gap-1.5">
                            <Spinner />
                            Connecting...
                          </span>
                        ) : (
                          "Connect"
                        )}
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {/* Info section */}
        <div className="mt-8 rounded-xl border border-zinc-800 bg-zinc-900/50 p-5">
          <h3 className="text-sm font-semibold text-zinc-300 mb-2">
            How integrations work
          </h3>
          <ul className="space-y-2 text-xs text-zinc-500 leading-relaxed">
            <li className="flex gap-2">
              <span className="text-cyan-400 shrink-0">1.</span>
              Connect your accounts above via secure OAuth.
            </li>
            <li className="flex gap-2">
              <span className="text-cyan-400 shrink-0">2.</span>
              When your energy is low, the system auto-delegates P3 tasks to
              GhostWorker.
            </li>
            <li className="flex gap-2">
              <span className="text-cyan-400 shrink-0">3.</span>
              GhostWorker drafts emails, Slack messages, and calendar updates
              for your approval.
            </li>
            <li className="flex gap-2">
              <span className="text-cyan-400 shrink-0">4.</span>
              Approve via voice or dashboard — GhostWorker executes through
              your connected accounts.
            </li>
          </ul>
        </div>
      </div>
    </div>
  );
}

function Spinner() {
  return (
    <svg className="h-3 w-3 animate-spin" viewBox="0 0 24 24" fill="none">
      <circle
        cx="12" cy="12" r="10"
        stroke="currentColor" strokeWidth="3"
        className="opacity-25"
      />
      <path
        d="M4 12a8 8 0 018-8"
        stroke="currentColor" strokeWidth="3" strokeLinecap="round"
      />
    </svg>
  );
}
